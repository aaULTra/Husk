/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_DISPLAY_H
#define HUSK_TL_DISPLAY_H
#include <stdint.h>
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
#define TL_DISPLAY_BINS 512u
#define TL_DISPLAY_CAPACITY 256u
typedef struct {uint32_t version,size,enabled,excluded;uint64_t include_after_media_ns;} tl_display_config;
typedef struct {
 uint64_t sequence,swapchain_generation,raw_drawable_ns,effective_driver_ns,begin_driver_ns,observed_media_ns;
 uint32_t google_id,source; /* 1 drawable presentedTime,2 driver fallback estimate */
} tl_display_record;
typedef struct {
 uint32_t version,size,enabled,excluded,retained,capacity;
 uint64_t epoch,attempts,direct_events,estimated_events,invalid_events,boundary_events,contention_drops,overwrites;
 uint64_t intervals,interval_ns,worst_interval_ns,above20,above33,above50;
 uint64_t histogram[TL_DISPLAY_BINS];
} tl_display_stats;
void tl_vk_display_driver(void *library);
void tl_vk_display_monitor(bool enabled);
void tl_vk_display_exclude(bool excluded);
bool tl_vk_display_snapshot(tl_display_stats*,tl_display_record*,uint32_t capacity,uint32_t *copied);
#ifdef __cplusplus
}
#endif
#endif
