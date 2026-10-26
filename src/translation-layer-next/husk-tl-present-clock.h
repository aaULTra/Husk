/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_PRESENT_CLOCK_H
#define HUSK_TL_PRESENT_CLOCK_H
#include <stdint.h>
#include <stdbool.h>
typedef struct {uint64_t guest_ns,media_ns,uncertainty_ns;} tl_pt_clock;
typedef struct {uint32_t type;const void *next;} tl_pt_base;
typedef struct {uint32_t id;uint64_t time;} tl_pt_time;
typedef struct {uint32_t type;const void *next;uint32_t count;const tl_pt_time *times;} tl_pt_times;
typedef struct {uint32_t type;const void *next;uint32_t wait_count;const uint64_t *waits;uint32_t count;const uint64_t *swaps;const uint32_t *indices;int32_t *results;} tl_pt_info;
typedef union {uint64_t alignment;unsigned char bytes[64];} tl_pt_node;
typedef struct {tl_pt_info info;tl_pt_node nodes[16];tl_pt_time times[8];} tl_pt_copy;
typedef struct {uint32_t id;uint64_t desired,actual,earliest,margin;} tl_pt_past;
typedef struct {uint64_t sequence,raw_actual,guest_actual,desired,earliest,margin,observed_guest_ns,observed_media_ns,uncertainty_ns;uint32_t id;} tl_pt_record;
typedef struct {
 bool requested,monitoring;
 uint64_t presents,timing_requests,mapped,expired,far_future,invalid_clock,unsupported,feedback_calls,feedback_records,record_overwrites,record_contention;
 int64_t latest_offset_ns;uint64_t latest_uncertainty_ns;
} tl_pt_stats;
void husk_ue4_set_clock_presentation(bool enabled);
bool tl_pt_requested(void);
bool tl_pt_monitoring(void);
bool tl_pt_clock_valid(tl_pt_clock clock);
void tl_pt_monitor(bool enabled);
/* Stack-owned copies are valid through the native API call. Never writes input. */
bool tl_pt_prepare(const void *input,tl_pt_copy *storage,tl_pt_clock clock,const void **output);
void tl_pt_feedback(tl_pt_past *rows,uint32_t count,tl_pt_clock clock);
void tl_pt_snapshot(tl_pt_stats *out);
uint32_t tl_pt_records(tl_pt_record *out,uint32_t capacity);
#endif
