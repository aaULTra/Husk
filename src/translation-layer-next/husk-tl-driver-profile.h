/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_DRIVER_PROFILE_H
#define HUSK_TL_DRIVER_PROFILE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
/* Opt-in host driver activity counters, NOT GPU execution timestamps.
 * Configure before loading Metal/MoltenVK. */
void husk_ue4_set_driver_profiling(bool enabled);
void tl_dp_set_api(int (*get_statistics)(void *, void *, size_t *), const char *version);
void tl_dp_device(void *device);
void tl_dp_forget(void *device);
void tl_dp_report(void);
typedef struct {uint32_t phase,new_calls,total_calls;bool reset,estimated_total_valid,values_valid;double lifetime_average_ms,latest_ms,lifetime_max_ms,estimated_new_total_ms;} tl_dp_phase;
typedef struct {uint64_t serial,previous_query_ns,queried_ns;uint32_t invalid_values;bool requested,compatible,available;} tl_dp_info;
/* Copy the most recent already-collected query. Never queries the driver or
 * consumes another reporting window; caller uses fields with explicit scope. */
uint32_t tl_dp_copy(tl_dp_phase *out,uint32_t capacity,tl_dp_info *info);
const char *tl_dp_name(uint32_t phase);
#endif
