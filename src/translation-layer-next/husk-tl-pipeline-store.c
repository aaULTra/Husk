/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifdef __APPLE__
#define _DARWIN_C_SOURCE 1
#else
#define _POSIX_C_SOURCE 200809L
#endif
#include "husk-tl-pipeline-store.h"
#include <pthread.h>
#ifdef __APPLE__
#include <pthread/qos.h>
#endif
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>

_Static_assert(offsetof(tl_pc_create_info, size) == 24 && offsetof(tl_pc_create_info, data) == 32, "Vulkan 64-bit cache ABI");
#define MAX_DEVICES 8
#define MAX_CACHES 64
#define MAX_BYTES (32u * 1024u * 1024u)
static struct device {
    void *handle;
    uint8_t header[32];
    uint64_t caches[MAX_CACHES];
    unsigned count;
} devices[MAX_DEVICES];
static char directory[768];
static tl_pc_api api;
static pthread_rwlock_t access_lock = PTHREAD_RWLOCK_INITIALIZER;
static pthread_mutex_t metadata_lock = PTHREAD_MUTEX_INITIALIZER;
static atomic_bool saving;
void tl_log_line(const char *fmt, ...);

void tl_pc_set_api(tl_pc_api value) { api = value; } /* before engine threads */
void tl_pc_configure(const char *path)
{
    if (!path || strlen(path) >= sizeof(directory) || !api.create || !api.data || !api.merge || !api.destroy) return;
    if (mkdir(path, 0700) && access(path, W_OK)) return;
    struct stat root;
    if (stat(path, &root) || !S_ISDIR(root.st_mode)) return;
    snprintf(directory, sizeof(directory), "%s", path);
    tl_log_line("ue4 cache store: enabled; compatible data restored on launch, checkpoints on pause; no first-use warm-up guarantee");
}
bool tl_pc_enter(void)
{
    if (!directory[0]) return false;
    pthread_rwlock_rdlock(&access_lock);
    return true;
}
void tl_pc_leave(bool locked) { if (locked) pthread_rwlock_unlock(&access_lock); }
static struct device *find(void *handle)
{
    for (unsigned i = 0; i < MAX_DEVICES; ++i) if (devices[i].handle == handle) return &devices[i];
    return NULL;
}
void tl_pc_device(void *handle, uint32_t vendor, uint32_t id, const uint8_t uuid[16])
{
    if (!directory[0] || !handle) return;
    pthread_mutex_lock(&metadata_lock);
    struct device *d = find(handle);
    if (!d) for (unsigned i = 0; i < MAX_DEVICES; ++i) if (!devices[i].handle) { d = &devices[i]; break; }
    if (d) {
        memset(d, 0, sizeof(*d)); d->handle = handle;
        uint32_t header[] = {32, 1, vendor, id};
        memcpy(d->header, header, 16); memcpy(d->header + 16, uuid, 16);
    }
    pthread_mutex_unlock(&metadata_lock);
}
static bool path_for(void *handle, char path[1024], uint8_t header[32])
{
    bool found = false;
    pthread_mutex_lock(&metadata_lock);
    struct device *d = find(handle);
    if (d) { memcpy(header, d->header, 32); found = true; }
    pthread_mutex_unlock(&metadata_lock);
    if (!found || !directory[0]) return false;
    char key[65];
    for (unsigned i = 0; i < 32; ++i) snprintf(key + i * 2, 3, "%02x", header[i]);
    snprintf(path, 1024, "%s/%s.bin", directory, key);
    return true;
}
static uint64_t checksum(const void *raw, size_t size)
{
    const uint8_t *data = raw; uint64_t hash = 14695981039346656037ULL;
    for (size_t i = 0; i < size; ++i) { hash ^= data[i]; hash *= 1099511628211ULL; }
    return hash;
}
void *tl_pc_load(void *handle, size_t *size)
{
    *size = 0;
    char path[1024]; uint8_t header[32];
    if (!path_for(handle, path, header)) return NULL;
    int fd = open(path, O_RDONLY | O_NOFOLLOW);
    if (fd < 0) return NULL;
    struct stat st;
    if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_size <= 40 || st.st_size > MAX_BYTES + 8) { close(fd); return NULL; }
    size_t length = (size_t)st.st_size - 8, got = 0;
    uint8_t *data = malloc(length);
    if (!data) { close(fd); return NULL; }
    while (got < length) {
        ssize_t n = read(fd, data + got, length - got);
        if (n <= 0) break;
        got += (size_t)n;
    }
    uint64_t stored_checksum = 0;
    ssize_t footer = read(fd, &stored_checksum, sizeof(stored_checksum));
    close(fd);
    if (got != length || footer != 8 || checksum(data, length) != stored_checksum || memcmp(data, header, 32)) { free(data); return NULL; }
    *size = length;
    tl_log_line("ue4 cache store: loaded %zu compatible bytes; cache hit still depends on shader/config keys", length);
    return data;
}
void tl_pc_discard(void *handle)
{
    char path[1024]; uint8_t header[32];
    if (path_for(handle, path, header)) unlink(path);
}
/* These metadata operations run inside a caller's shared access scope. */
void tl_pc_track(void *handle, uint64_t cache)
{
    if (!directory[0]) return;
    pthread_mutex_lock(&metadata_lock);
    struct device *d = find(handle);
    if (d && d->count < MAX_CACHES) d->caches[d->count++] = cache;
    pthread_mutex_unlock(&metadata_lock);
}
void tl_pc_untrack(void *handle, uint64_t cache)
{
    pthread_mutex_lock(&metadata_lock);
    struct device *d = find(handle);
    if (d) for (unsigned i = 0; i < d->count; ++i) if (d->caches[i] == cache) {
        d->caches[i] = d->caches[--d->count]; break;
    }
    pthread_mutex_unlock(&metadata_lock);
}
void tl_pc_forget_device(void *handle, void (*destroy)(void *, const void *), const void *alloc)
{
    pthread_rwlock_wrlock(&access_lock);
    pthread_mutex_lock(&metadata_lock);
    struct device *d = find(handle);
    if (d) memset(d, 0, sizeof(*d));
    pthread_mutex_unlock(&metadata_lock);
    if (destroy) destroy(handle, alloc);
    pthread_rwlock_unlock(&access_lock);
}
static bool write_blob(const char *path, const void *data, size_t size)
{
    char temp[1100]; snprintf(temp, sizeof(temp), "%s.tmp-XXXXXX", path);
    int fd = mkstemp(temp);
    if (fd < 0) return false;
    size_t done = 0;
    while (done < size) {
        ssize_t n = write(fd, (const uint8_t *)data + done, size - done);
        if (n <= 0) break;
        done += (size_t)n;
    }
    uint64_t hash = checksum(data, size);
    ssize_t footer = done == size ? write(fd, &hash, sizeof(hash)) : -1;
    int result = close(fd);
    if (done == size && footer == 8 && !result && !rename(temp, path)) return true;
    unlink(temp); return false;
}
void tl_pc_checkpoint(void)
{
    if (!directory[0]) return;
    for (unsigned i = 0; i < MAX_DEVICES; ++i) {
        void *data = NULL; size_t size = 0; char path[1024]; uint8_t header[32];
        pthread_rwlock_wrlock(&access_lock);
        /* Exclusive access prevents pipeline creation, merging, destruction or
         * device teardown while the native cache is copied. Normal gameplay
         * retains parallel shared access. Disk I/O is outside this lock. */
        pthread_mutex_lock(&metadata_lock);
        struct device d = devices[i];
        pthread_mutex_unlock(&metadata_lock);
        uint64_t combined = 0;
        tl_pc_create_info info = {.type = 17}; /* VK_STRUCTURE_TYPE_PIPELINE_CACHE_CREATE_INFO */
        if (d.handle && d.count && path_for(d.handle, path, header) &&
            !api.create(d.handle, &info, NULL, &combined)) {
            if (!api.merge(d.handle, combined, d.count, d.caches) &&
                !api.data(d.handle, combined, &size, NULL) && size > 32 && size <= MAX_BYTES) {
                size_t allocated = size;
                data = malloc(allocated);
                if (data && (api.data(d.handle, combined, &size, data) || size > allocated || size <= 32 || memcmp(data, header, 32))) {
                    free(data); data = NULL;
                }
            }
            api.destroy(d.handle, combined, NULL);
        }
        pthread_rwlock_unlock(&access_lock);
        if (data) {
            bool saved = write_blob(path, data, size);
            tl_log_line("ue4 cache store: pause checkpoint %s (%zu bytes)", saved ? "saved" : "failed", size);
            free(data);
        }
    }
}
static void *save_worker(void *unused)
{
    (void)unused;
#ifdef __APPLE__
    pthread_set_qos_class_self_np(QOS_CLASS_UTILITY, 0);
#endif
    tl_pc_checkpoint(); atomic_store(&saving, false); return NULL;
}
void tl_pc_checkpoint_async(void)
{
    if (!directory[0] || atomic_exchange(&saving, true)) return;
    pthread_t thread;
    if (pthread_create(&thread, NULL, save_worker, NULL)) { atomic_store(&saving, false); return; }
    pthread_detach(thread);
}
