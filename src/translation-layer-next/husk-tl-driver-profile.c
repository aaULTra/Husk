/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifdef __APPLE__
#define _DARWIN_C_SOURCE 1
#else
#define _POSIX_C_SOURCE 200809L
#endif
#include "husk-tl-driver-profile.h"
#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* MoltenVK v1.4.2 private API 43: 11 shader, 3 cache, 9 queue, 1 memory
 * trackers in this order. Require the complete exact-size ABI; never read a
 * short/prefix result. Source: KhronosGroup/MoltenVK v1.4.2 mvk_private_api.h. */
typedef struct {
    uint32_t count;
    double latest, previous, average, minimum, maximum;
} tracker;
typedef struct { tracker values[24]; } statistics;
_Static_assert(sizeof(tracker) == 48 && offsetof(tracker, latest) == 8 && sizeof(statistics) == 1152,
               "MoltenVK 1.4.2 performance ABI requires 64-bit double alignment");

static bool enabled, compatible, known_version;
static void *profile_device;
static int (*get_stats)(void *, void *, size_t *);
static uint32_t previous_counts[24];
static pthread_mutex_t profile_mu = PTHREAD_MUTEX_INITIALIZER;
void tl_log_line(const char *fmt, ...);

void husk_ue4_set_driver_profiling(bool on)
{
    enabled = on; /* launch-time setting, before engine threads */
    if (!on) return;
    setenv("MVK_CONFIG_PERFORMANCE_TRACKING", "1", 1);
    setenv("MVK_CONFIG_PERFORMANCE_LOGGING_FRAME_COUNT", "0", 1);
    tl_log_line("ue4 driver profile: requested opt-in MoltenVK activity tracking; diagnostic overhead, not a performance mode; restart required to disable");
}
void tl_dp_set_api(int (*api)(void *, void *, size_t *), const char *version)
{
    get_stats = api; known_version = version && !strcmp(version, "1.4.2");
}
void tl_dp_device(void *device)
{
    if (!enabled || !device) return;
    pthread_mutex_lock(&profile_mu);
    if (!profile_device) {
        profile_device = device; compatible = false;
        memset(previous_counts, 0, sizeof(previous_counts));
        size_t size = 0;
        int result = get_stats && known_version ? get_stats(device, NULL, &size) : -7;
        compatible = (result == 0 || result == 5) && size == sizeof(statistics);
        tl_log_line("ue4 driver profile: statistics ABI %s, result %d, bytes %zu expected %zu; bundled MoltenVK 1.4.2/private API 43; one device sampled",
                    compatible ? "accepted" : "unavailable/mismatched", result, size, sizeof(statistics));
    } else if (profile_device != device) {
        tl_log_line("ue4 driver profile: additional device not sampled; counters remain scoped to the first live device");
    }
    pthread_mutex_unlock(&profile_mu);
}
void tl_dp_forget(void *device)
{
    if (!enabled) return;
    /* Serialize only this short host query with teardown, never GPU completion. */
    pthread_mutex_lock(&profile_mu);
    if (profile_device == device) { profile_device = NULL; compatible = false; }
    pthread_mutex_unlock(&profile_mu);
}
void tl_dp_report(void)
{
    if (!enabled || pthread_mutex_trylock(&profile_mu)) return;
    if (!profile_device || !compatible) { pthread_mutex_unlock(&profile_mu); return; }
    statistics stats = {0}; size_t size = sizeof(stats);
    int result = get_stats(profile_device, &stats, &size);
    if (result || size != sizeof(stats)) {
        compatible = false;
        pthread_mutex_unlock(&profile_mu);
        tl_log_line("ue4 driver profile: stopped after incomplete statistics read result %d, bytes %zu; no prefix interpretation", result, size);
        return;
    }
    static const char *const names[24] = {
        "shader-hash", "SPIR-V-to-MSL", "Metal-library-compile", "Metal-library-load",
        "MSL-compress", "MSL-decompress", "shader-library-cache-retrieval", "Metal-function-retrieval",
        "Metal-function-specialization", "Metal-pipeline-compile", "GLSL-to-SPIR-V",
        "cache-size", "cache-write", "cache-read", "command-buffer-retrieval", "command-encoding",
        "submit-to-encoding-wait", "submit-and-encoding", "commit-to-completion-callback-latency",
        "drawable-retrieval", "present-to-encoding-wait", "commit-to-presentation-callback-latency",
        "presentation-interval", "GPU-memory-KiB"
    };
    /* Copy results and counts under lifetime protection, then release before
     * log I/O. Counters are cumulative; nested activities must not be summed. */
    uint32_t previous[24]; memcpy(previous, previous_counts, sizeof(previous));
    for (unsigned i = 0; i < 24; ++i) previous_counts[i] = stats.values[i].count;
    pthread_mutex_unlock(&profile_mu);
    tl_log_line("ue4 driver profile: cumulative host/activity statistics; new=count since previous sample, avg/max=lifetime, last=latest event; activities overlap; callback latency is NOT pure GPU execution, energy or a CPU/GPU bottleneck verdict");
    bool emitted = false;
    for (unsigned i = 0; i < 23; ++i) {
        tracker t = stats.values[i];
        if (t.count == previous[i]) continue;
        if (!isfinite(t.average) || !isfinite(t.latest) || !isfinite(t.maximum) ||
            t.average < 0 || t.latest < 0 || t.maximum < 0) continue;
        bool reset = t.count < previous[i];
        uint32_t added = reset ? t.count : t.count - previous[i];
        emitted = true;
        tl_log_line("ue4 driver phase: %s new %u total %u, avg %.3f ms last %.3f ms max %.3f ms%s",
                    names[i], added, t.count, t.average, t.latest, t.maximum, reset ? " (counter reset/wrap)" : "");
    }
    if (!emitted) tl_log_line("ue4 driver profile: no new validated activities; ABI acceptance alone does not establish active tracking");
}
