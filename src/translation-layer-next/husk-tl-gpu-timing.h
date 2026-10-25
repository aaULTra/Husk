/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_GPU_TIMING_H
#define HUSK_TL_GPU_TIMING_H
#include <stdbool.h>
#include <stdint.h>
/* Sample only known game queues: one media-clock second every ten seconds.
 * These are command-buffer timestamps, not per-frame or device utilisation. */
typedef struct { uint64_t session, epoch, queue; double begin, end; } tl_gput_ticket;
typedef struct { double gpu_start, gpu_end, completed, sample_start, sample_end; uint64_t queue; } tl_gput_record;
typedef struct {
    uint64_t attached, completed, invalid, errors, outside, dropped, pending, stale;
    uint32_t registered_queues, hooked_queues, hook_failures;
    bool requested, running;
    double media_origin;
} tl_gput_stats;
void tl_gput_begin(bool requested, double media_time);
void tl_gput_exclude(bool excluded);
void tl_gput_end(void);
bool tl_gput_active(void);
bool tl_gput_capture(double media_time, uint64_t queue, tl_gput_ticket *out);
void tl_gput_complete(tl_gput_ticket ticket, double start, double end, double completed, bool success);
bool tl_gput_pop(tl_gput_record *out);
void tl_gput_snapshot(tl_gput_stats *out);
void tl_gput_queue_state(uint32_t registered, uint32_t hooked, uint32_t failed);
/* ObjC adapter, never transfers ownership of Vulkan/Metal objects. */
void tl_gput_native_start(bool requested);
void tl_gput_native_register(void *device, void *metal_queue);
void tl_gput_native_forget(void *device);
#endif
