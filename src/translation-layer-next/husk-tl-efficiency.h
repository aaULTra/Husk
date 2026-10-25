/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_EFFICIENCY_H
#define HUSK_TL_EFFICIENCY_H
#include <stdbool.h>
#include <stdint.h>
/* Observer only: never changes graphics, pacing, queues or worker policy. */
enum { TL_EM_ACQUIRE, TL_EM_SUBMIT, TL_EM_PRESENT, TL_EM_SLEEP,
       TL_EM_GRAPHICS, TL_EM_COMPUTE, TL_EM_STAGES };
typedef struct {
    uint64_t intervals, above20, above33, above50, discontinuities;
    double interval_seconds, p50_ms, p95_ms, p99_ms, worst_ms;
    uint64_t host_calls[TL_EM_STAGES], host_ns[TL_EM_STAGES];
    uint64_t slow_pipeline_calls, worst_pipeline_ns, dropped;
    uint64_t dropped_frames, dropped_host, dropped_events, lost_frame_ns, lost_frame_max_ns;
    uint64_t guest_yield_calls;
    uint32_t width, height;
} tl_em_stats;
typedef struct { double monotonic_seconds; char text[512]; } tl_em_event;
void tl_em_start(void);
void tl_em_stop(void);
void tl_em_exclude(bool excluded);
void tl_em_frame(int64_t monotonic_ns);
void tl_em_guest_yield(void);
void tl_em_host(unsigned stage, uint64_t ns);
void tl_em_size(uint32_t width, uint32_t height);
void tl_em_log(const char *line);
bool tl_em_pop(tl_em_event *out);
/* Window snapshots drain only the window; total snapshots are nondestructive. */
void tl_em_snapshot(bool total, tl_em_stats *out);
double tl_em_clock(void);
/* Supported per-process Mach information. Invalid fields remain -1. */
typedef struct { double cpu_seconds; int64_t footprint_bytes, peak_bytes, jetsam_bytes; } tl_em_process;
void tl_em_process_sample(bool memory, tl_em_process *out);
#endif
