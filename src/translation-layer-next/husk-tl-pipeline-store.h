/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_PIPELINE_STORE_H
#define HUSK_TL_PIPELINE_STORE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef struct {
    uint32_t type;
    const void *next;
    uint32_t flags;
    size_t size;
    const void *data;
} tl_pc_create_info;
typedef struct {
    int (*create)(void *, const void *, const void *, uint64_t *);
    int (*data)(void *, uint64_t, size_t *, void *);
    int (*merge)(void *, uint64_t, uint32_t, const uint64_t *);
    void (*destroy)(void *, uint64_t, const void *);
} tl_pc_api;
void tl_pc_set_api(tl_pc_api api);
void tl_pc_configure(const char *directory);
void tl_pc_device(void *device, uint32_t vendor, uint32_t id, const uint8_t uuid[16]);
/* Locks share access between normal pipeline/cache calls. Checkpoints alone
 * take exclusive access, preserving parallel pipeline creation in gameplay. */
bool tl_pc_enter(void);
void tl_pc_leave(bool locked);
void tl_pc_track(void *device, uint64_t cache);
void tl_pc_untrack(void *device, uint64_t cache);
void tl_pc_forget_device(void *device, void (*destroy)(void *, const void *), const void *alloc);
void *tl_pc_load(void *device, size_t *size);
void tl_pc_discard(void *device);
void tl_pc_checkpoint_async(void);
/* Synchronous entry point for portable tests; runtime uses the async path. */
void tl_pc_checkpoint(void);
#endif
