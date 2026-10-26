/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_COMPONENT_PROFILE_H
#define HUSK_TL_COMPONENT_PROFILE_H
#include <stdbool.h>
#include <stdint.h>
enum {TL_CP_ACQUIRE,TL_CP_SUBMIT,TL_CP_PRESENT,TL_CP_GRAPHICS,TL_CP_COMPUTE,
      TL_CP_JNI,TL_CP_FUTEX_WAIT,TL_CP_FUTEX_WAKE,TL_CP_ONCE_SLOW,TL_CP_COUNT};
typedef struct {uint64_t epoch,wall,cpu;uint32_t kind;bool active;} tl_cp_ticket;
typedef struct {uint32_t kind,reserved;uint64_t samples,wall_ns,cpu_ns,worst_wall_ns,worst_cpu_ns;} tl_cp_row;
typedef struct {uint64_t epoch,dropped,boundary_dropped,clock_errors;uint32_t sample_every;bool requested,running,excluded;} tl_cp_stats;
void tl_cp_start(bool requested);
void tl_cp_exclude(bool excluded);
void tl_cp_stop(void);
tl_cp_ticket tl_cp_begin(uint32_t kind);
void tl_cp_end(tl_cp_ticket ticket);
uint32_t tl_cp_snapshot(tl_cp_row *rows,uint32_t capacity,tl_cp_stats *stats);
#endif
