/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "husk-tl-gpu-timing.h"
#include <math.h>
#include <pthread.h>
#include <stdatomic.h>
#include <string.h>
#define RECORDS 1024
#define SAMPLE_BUDGET 256
static pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;
static atomic_bool active;
static atomic_uint_fast64_t dropped;
static tl_gput_stats stats;
static uint64_t generation, epoch;
static atomic_uint_fast64_t published_generation;
static bool excluded = true;
static double origin, budget_window = -1;
static unsigned budget, head, length;
static tl_gput_record records[RECORDS];
void tl_gput_queue_state(uint32_t registered, uint32_t hooked, uint32_t failed) {
    pthread_mutex_lock(&mu);
    stats.registered_queues=registered;stats.hooked_queues=hooked;stats.hook_failures=failed;
    pthread_mutex_unlock(&mu);
}
void tl_gput_begin(bool requested, double now) {
    atomic_store(&active,false);pthread_mutex_lock(&mu);
    uint32_t r=stats.registered_queues,h=stats.hooked_queues,f=stats.hook_failures;
    memset(&stats,0,sizeof(stats));stats.registered_queues=r;stats.hooked_queues=h;stats.hook_failures=f;
    stats.requested=requested;stats.running=requested;generation++;epoch++;excluded=true;
    origin=now;stats.media_origin=now;atomic_store(&published_generation,generation);budget_window=-1;budget=head=length=0;atomic_store(&dropped,0);
    atomic_store(&active,requested);pthread_mutex_unlock(&mu);
}
void tl_gput_exclude(bool value) {pthread_mutex_lock(&mu);if(excluded!=value){excluded=value;epoch++;}pthread_mutex_unlock(&mu);}
void tl_gput_end(void) {atomic_store(&active,false);pthread_mutex_lock(&mu);stats.running=false;epoch++;pthread_mutex_unlock(&mu);}
bool tl_gput_active(void) {return atomic_load_explicit(&active,memory_order_relaxed);}
bool tl_gput_capture(double now, uint64_t queue, tl_gput_ticket *out) {
    if(!tl_gput_active())return false;
    if(pthread_mutex_trylock(&mu)){atomic_fetch_add(&dropped,1);return false;}
    bool ok=false;
    if(stats.running&&!excluded&&isfinite(now)&&now>=origin&&queue){
        double window=floor((now-origin)/10)*10+origin;
        if(now<window+1){
            if(window!=budget_window){budget_window=window;budget=0;}
            if(budget<SAMPLE_BUDGET){budget++;stats.attached++;stats.pending++;*out=(tl_gput_ticket){generation,epoch,queue,window,window+1};ok=true;}
            else atomic_fetch_add(&dropped,1);
        }
    }
    pthread_mutex_unlock(&mu);return ok;
}
void tl_gput_complete(tl_gput_ticket t,double start,double end,double completed,bool success){
    /* Completion handlers never wait for the consumer. A contended completion
     * is disclosed as lost; pending then conservatively includes unresolved work. */
    if(t.session!=atomic_load(&published_generation))return;
    if(pthread_mutex_trylock(&mu)){atomic_fetch_add(&dropped,1);return;}
    if(t.session!=generation){pthread_mutex_unlock(&mu);return;}
    if(stats.pending)stats.pending--;
    if(!stats.running||excluded||t.epoch!=epoch){stats.stale++;}
    else if(!success){stats.errors++;}
    else if(!isfinite(start)||!isfinite(end)||!isfinite(completed)||start<=0||end<=start||end>completed+0.05||start<t.begin-10){stats.invalid++;}
    else if(end<=t.begin||start>=t.end){stats.outside++;}
    else if(length==RECORDS){atomic_fetch_add(&dropped,1);}
    else {records[(head+length++)%RECORDS]=(tl_gput_record){start,end,completed,t.begin,t.end,t.queue};stats.completed++;}
    pthread_mutex_unlock(&mu);
}
bool tl_gput_pop(tl_gput_record *out){pthread_mutex_lock(&mu);bool ok=length>0;if(ok){*out=records[head];head=(head+1)%RECORDS;length--;}pthread_mutex_unlock(&mu);return ok;}
void tl_gput_snapshot(tl_gput_stats *out){pthread_mutex_lock(&mu);*out=stats;out->dropped=atomic_load(&dropped);pthread_mutex_unlock(&mu);}
