/* SPDX-License-Identifier: GPL-2.0-or-later */
#if !defined(__APPLE__) && !defined(_POSIX_C_SOURCE)
#define _POSIX_C_SOURCE 200809L
#endif
#include "husk-tl-component-profile.h"
#include <pthread.h>
#include <stdatomic.h>
#include <string.h>
#include <time.h>
#define CP_EVERY 64u
atomic_bool tl_cp_gate;
static atomic_uint_fast64_t epoch,dropped,boundary,clock_errors;
static pthread_mutex_t mu=PTHREAD_MUTEX_INITIALIZER;
static tl_cp_row counters[TL_CP_COUNT];
static bool requested,running,excluded;
static _Thread_local uint32_t ticks[TL_CP_COUNT];
static bool clock_ns(clockid_t clock,uint64_t *out){
 struct timespec t;if(clock_gettime(clock,&t)||t.tv_sec<0||t.tv_nsec<0||t.tv_nsec>=1000000000)return false;
 *out=(uint64_t)t.tv_sec*1000000000ULL+(uint64_t)t.tv_nsec;return true;
}
void tl_cp_start(bool value){
 atomic_store(&tl_cp_gate,false);pthread_mutex_lock(&mu);atomic_fetch_add(&epoch,1);
 atomic_store(&tl_cp_gate,false);requested=value;running=true;excluded=true;memset(counters,0,sizeof(counters));
 atomic_store(&dropped,0);atomic_store(&boundary,0);atomic_store(&clock_errors,0);pthread_mutex_unlock(&mu);
}
void tl_cp_exclude(bool value){
 atomic_store(&tl_cp_gate,false);pthread_mutex_lock(&mu);
 if(excluded!=value){excluded=value;atomic_fetch_add(&epoch,1);}
 bool gate=requested&&running&&!excluded;atomic_store(&tl_cp_gate,gate);pthread_mutex_unlock(&mu);
}
void tl_cp_stop(void){atomic_store(&tl_cp_gate,false);pthread_mutex_lock(&mu);atomic_store(&tl_cp_gate,false);running=false;atomic_fetch_add(&epoch,1);pthread_mutex_unlock(&mu);}
tl_cp_ticket tl_cp_begin(uint32_t kind){
 tl_cp_ticket t={0};if(kind>=TL_CP_COUNT||!atomic_load_explicit(&tl_cp_gate,memory_order_relaxed))return t;
 if((ticks[kind]++&(CP_EVERY-1u))!=0)return t;
 t.epoch=atomic_load(&epoch);t.kind=kind;
 if(!clock_ns(CLOCK_MONOTONIC,&t.wall)||!clock_ns(CLOCK_THREAD_CPUTIME_ID,&t.cpu)){atomic_fetch_add(&clock_errors,1);return (tl_cp_ticket){0};}
 if(!atomic_load(&tl_cp_gate)||t.epoch!=atomic_load(&epoch)){atomic_fetch_add(&boundary,1);return (tl_cp_ticket){0};}
 t.active=true;return t;
}
void tl_cp_end(tl_cp_ticket t){
 if(!t.active||t.kind>=TL_CP_COUNT)return;
 uint64_t cpu,wall;
 if(!clock_ns(CLOCK_THREAD_CPUTIME_ID,&cpu)||!clock_ns(CLOCK_MONOTONIC,&wall)||wall<t.wall||cpu<t.cpu){atomic_fetch_add(&clock_errors,1);return;}
 if(pthread_mutex_trylock(&mu)){atomic_fetch_add(&dropped,1);return;}
 if(t.epoch!=atomic_load(&epoch)||!requested||!running||excluded){pthread_mutex_unlock(&mu);atomic_fetch_add(&boundary,1);return;}
 tl_cp_row *r=counters+t.kind;cpu-=t.cpu;wall-=t.wall;r->kind=t.kind;r->samples++;r->wall_ns+=wall;r->cpu_ns+=cpu;
 if(wall>r->worst_wall_ns)r->worst_wall_ns=wall;
 if(cpu>r->worst_cpu_ns)r->worst_cpu_ns=cpu;
 pthread_mutex_unlock(&mu);
}
uint32_t tl_cp_snapshot(tl_cp_row *rows,uint32_t capacity,tl_cp_stats *s){
 pthread_mutex_lock(&mu);uint32_t n=0;
 if(s)*s=(tl_cp_stats){.epoch=atomic_load(&epoch),.dropped=atomic_load(&dropped),.boundary_dropped=atomic_load(&boundary),.clock_errors=atomic_load(&clock_errors),.sample_every=CP_EVERY,.requested=requested,.running=running,.excluded=excluded};
 if(rows)for(unsigned i=0;i<TL_CP_COUNT&&n<capacity;i++)if(counters[i].samples)rows[n++]=counters[i];
 pthread_mutex_unlock(&mu);return n;
}
