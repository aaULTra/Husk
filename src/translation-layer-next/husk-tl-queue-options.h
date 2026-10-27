/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_QUEUE_OPTIONS_H
#define HUSK_TL_QUEUE_OPTIONS_H
#include <stdbool.h>
#include <stdint.h>
/* Launch only. -1/0 preserve driver/environment defaults. Prefill3 is excluded:
 * this guest integration cannot guarantee an autorelease pool per recording thread. */
void husk_ue4_set_queue_options(int prefill,int command_buffer_limit);
void tl_queue_options_environment(void);
void tl_queue_options_observe(int result,const uint32_t *prefix,uint32_t bytes);
typedef struct {int32_t requested_prefill;uint32_t requested_limit;bool applied,observed;int32_t environment_error,query_result;uint32_t actual_synchronous,actual_prefill,actual_limit;} tl_queue_options_stats;
void tl_queue_options_snapshot(tl_queue_options_stats *out);
#endif
