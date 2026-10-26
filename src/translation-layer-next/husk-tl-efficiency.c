/* SPDX-License-Identifier: GPL-2.0-or-later */
#define _POSIX_C_SOURCE 200809L
#include "husk-tl-efficiency.h"
#include <stdatomic.h>
#include <pthread.h>
#include <string.h>
#include <time.h>
#include <stdio.h>
#ifdef __APPLE__
#include <TargetConditionals.h>
#include <mach/mach.h>
#include <mach/task_info.h>
#include <mach/mach_time.h>
#include <mach/thread_info.h>
#if TARGET_OS_IOS
#include <os/proc.h>
#endif
#endif
/* 0.1 ms histogram through 1 second; overflow uses the exact maximum as a
 * conservative percentile bound. Counts/max/total retain multi-second hitches. */
#define BINS 10001
#define EVENTS 256
typedef struct { tl_em_stats s; uint64_t bins[BINS]; } aggregate;
static aggregate total_stats, window_stats;
static pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;
static atomic_bool enabled, frame_excluded,cpu_work_enabled;
static tl_em_work_stats submit_work;
static atomic_uint_fast64_t work_drops;
static atomic_uint_fast64_t sync_counts[TL_SYNC_COUNT];
static atomic_uint_fast64_t dropped_host, dropped_events, dropped_frames, lost_ns, lost_max;
static atomic_uint_fast64_t session, epoch, guest_yields;
/* Present producers never take the reporting mutex or build a histogram.
 * One serialized enqueue writer, one reporting consumer. Release/acquire cursor
 * publication keeps slot contents valid without waiting on the render path. */
#define FRAMES 8192
static struct { uint64_t ns, session; } frames[FRAMES];
static atomic_uint_fast64_t frame_write, frame_read;
static atomic_flag frame_writer = ATOMIC_FLAG_INIT;
static bool excluded;
static uint32_t width, height;
static tl_em_event events[EVENTS];
static unsigned head, length;

double tl_em_clock(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}
static bool enter(atomic_uint_fast64_t *loss) {
    if (!atomic_load_explicit(&enabled, memory_order_relaxed)) return false;
    if (pthread_mutex_trylock(&mu)) {
        atomic_fetch_add(loss, 1); return false;
    }
    if (!atomic_load(&enabled)) { pthread_mutex_unlock(&mu); return false; }
    return true;
}
static void drain_frames(void);
void tl_em_start(void) {
    pthread_mutex_lock(&mu);memset(&submit_work,0,sizeof(submit_work));atomic_store(&work_drops,0);
    for(unsigned i=0;i<TL_SYNC_COUNT;i++)atomic_store(&sync_counts[i],0);
    memset(&total_stats, 0, sizeof(total_stats)); memset(&window_stats, 0, sizeof(window_stats));
    head = length = 0; excluded = true;
    atomic_store(&enabled, false); atomic_fetch_add(&session, 1); atomic_fetch_add(&epoch, 1);
    drain_frames();
    atomic_store(&frame_excluded, true);
    atomic_store(&dropped_host, 0); atomic_store(&dropped_events, 0); atomic_store(&dropped_frames, 0);
    atomic_store(&lost_ns, 0); atomic_store(&lost_max, 0); atomic_store(&guest_yields, 0);
    atomic_store(&enabled, true);
    pthread_mutex_unlock(&mu);
}
void tl_em_stop(void) {
    pthread_mutex_lock(&mu); atomic_store(&enabled, false); atomic_fetch_add(&epoch, 1); pthread_mutex_unlock(&mu);
}
void tl_em_exclude(bool value) {
    pthread_mutex_lock(&mu); excluded = value;
    atomic_store(&frame_excluded, value); atomic_fetch_add(&epoch, 1);
    pthread_mutex_unlock(&mu);
}
void tl_em_size(uint32_t w, uint32_t h) {
    pthread_mutex_lock(&mu); width = w; height = h; pthread_mutex_unlock(&mu);
}
static void interval(aggregate *a, uint64_t ns) {
    double ms = ns / 1e6;
    unsigned bin = ns >= 1000000000ULL ? BINS - 1 : (unsigned)((ns + 99999) / 100000);
    a->bins[bin]++; a->s.intervals++; a->s.interval_seconds += ns / 1e9;
    a->s.above20 += ns > 20000000; a->s.above33 += ns > 33333333;
    a->s.above50 += ns > 50000000;
    if (ms > a->s.worst_ms) a->s.worst_ms = ms;
}
static void lost_interval(uint64_t ns) {
    atomic_fetch_add(&dropped_frames, 1); atomic_fetch_add(&lost_ns, ns);
    uint_fast64_t old = atomic_load(&lost_max);
    while (ns > old && !atomic_compare_exchange_weak(&lost_max, &old, ns)) {}
}
void tl_em_frame(int64_t now) {
    static _Thread_local int64_t previous;
    static _Thread_local uint64_t seen_epoch;
    if (!atomic_load_explicit(&enabled, memory_order_relaxed)) return;
    uint64_t run = atomic_load(&session), current_epoch = atomic_load(&epoch);
    if (seen_epoch != current_epoch) { previous = 0; seen_epoch = current_epoch; }
    if (atomic_load(&frame_excluded)) { previous = 0; return; }
    int64_t before = previous; previous = now;
    if (!before) return;
    uint64_t ns = now > before ? (uint64_t)(now - before) : 0;
    if (atomic_flag_test_and_set_explicit(&frame_writer, memory_order_acquire)) { lost_interval(ns); return; }
    uint64_t write = atomic_load_explicit(&frame_write, memory_order_relaxed);
    uint64_t read = atomic_load_explicit(&frame_read, memory_order_acquire);
    if (run == atomic_load(&session) && current_epoch == atomic_load(&epoch) && atomic_load(&enabled)) {
        if (write - read == FRAMES) lost_interval(ns);
        else {
            frames[write % FRAMES].ns = ns; frames[write % FRAMES].session = run;
            atomic_store_explicit(&frame_write, write + 1, memory_order_release);
        }
    }
    atomic_flag_clear_explicit(&frame_writer, memory_order_release);
}
/* Called only by the reporting consumer under mu. Old-session records are
 * discarded by tag rather than resetting a live producer's cursors. */
static void drain_frames(void) {
    uint64_t read = atomic_load_explicit(&frame_read, memory_order_relaxed);
    uint64_t write = atomic_load_explicit(&frame_write, memory_order_acquire);
    uint64_t run = atomic_load(&session);
    while (read != write) {
        if (frames[read % FRAMES].session == run) {
            if (frames[read % FRAMES].ns) {
                interval(&total_stats, frames[read % FRAMES].ns);
                interval(&window_stats, frames[read % FRAMES].ns);
            } else { total_stats.s.discontinuities++; window_stats.s.discontinuities++; }
        }
        read++;
    }
    atomic_store_explicit(&frame_read, read, memory_order_release);
}
/* M8 observation only: no backoff, clocks, sleeps or thread-policy changes. */
void tl_em_guest_yield(void) {
    if (atomic_load_explicit(&enabled, memory_order_relaxed) && !atomic_load(&frame_excluded))
        atomic_fetch_add_explicit(&guest_yields, 1, memory_order_relaxed);
}
void tl_em_host(unsigned stage, uint64_t ns) {
    if (stage >= TL_EM_STAGES || !enter(&dropped_host)) return;
    if (!excluded) {
        aggregate *a[] = { &total_stats, &window_stats };
        for (unsigned i = 0; i < 2; i++) {
            a[i]->s.host_calls[stage]++; a[i]->s.host_ns[stage] += ns;
            if (stage >= TL_EM_GRAPHICS) {
                a[i]->s.slow_pipeline_calls += ns >= 16666667;
                if (ns > a[i]->s.worst_pipeline_ns) a[i]->s.worst_pipeline_ns = ns;
            }
        }
    }
    pthread_mutex_unlock(&mu);
}
void tl_em_log(const char *line) {
    if (!atomic_load(&enabled) || !line) return;
    if (strncmp(line, "[M4/M6 present-clock]", 21) && strncmp(line, "thread-policy", 13) && strncmp(line, "ue4 cache store:", 16) &&
        strncmp(line, "ue4 cache:", 10) && strncmp(line, "ue4 pipeline", 12) &&
        strncmp(line, "ue4 submission:", 15) && strncmp(line, "ue4 timing:", 11) && strncmp(line, "vulkan: vkCreateSwapchain", 25) && strncmp(line, "vulkan: sizing", 14)) return;
    if (!enter(&dropped_events)) return;
    if (length == EVENTS) atomic_fetch_add(&dropped_events, 1);
    else {
        tl_em_event *e = &events[(head + length++) % EVENTS];
        e->monotonic_seconds = tl_em_clock(); snprintf(e->text, sizeof(e->text), "%s", line);
    }
    pthread_mutex_unlock(&mu);
}
bool tl_em_pop(tl_em_event *out) {
    pthread_mutex_lock(&mu);
    bool found = length > 0;
    if (found) { *out = events[head]; head = (head + 1) % EVENTS; length--; }
    pthread_mutex_unlock(&mu); return found;
}
static double percentile(const aggregate *a, unsigned p) {
    if (!a->s.intervals) return 0;
    uint64_t rank = (a->s.intervals * p + 99) / 100, n = 0;
    for (unsigned i = 0; i < BINS; i++) if ((n += a->bins[i]) >= rank)
        return i == BINS - 1 ? a->s.worst_ms : i / 10.0;
    return a->s.worst_ms;
}
void tl_em_snapshot(bool total, tl_em_stats *out) {
    aggregate copy;
    pthread_mutex_lock(&mu);
    drain_frames();
    copy = total ? total_stats : window_stats;
    if (!total) memset(&window_stats, 0, sizeof(window_stats));
    copy.s.dropped_frames = atomic_load(&dropped_frames);
    copy.s.dropped_host = atomic_load(&dropped_host); copy.s.dropped_events = atomic_load(&dropped_events);
    copy.s.lost_frame_ns = atomic_load(&lost_ns); copy.s.lost_frame_max_ns = atomic_load(&lost_max);
    copy.s.dropped = copy.s.dropped_frames + copy.s.dropped_host + copy.s.dropped_events;
    copy.s.guest_yield_calls = atomic_load(&guest_yields);
    copy.s.width = width; copy.s.height = height;
    pthread_mutex_unlock(&mu);
    copy.s.p50_ms = percentile(&copy, 50); copy.s.p95_ms = percentile(&copy, 95); copy.s.p99_ms = percentile(&copy, 99);
    *out = copy.s;
}
void tl_em_process_sample(bool memory, tl_em_process *out) {
    (void)memory;
    *out = (tl_em_process){ -1, -1, -1, -1 };
#ifdef __APPLE__
    /* TASK_ABSOLUTETIME_INFO includes live and terminated threads. It does not
     * enumerate threads or perturb their QoS. */
    task_absolutetime_info_data_t cpu;
    mach_msg_type_number_t count = TASK_ABSOLUTETIME_INFO_COUNT;
    if (task_info(mach_task_self(), TASK_ABSOLUTETIME_INFO, (task_info_t)&cpu, &count) == KERN_SUCCESS) {
        mach_timebase_info_data_t base; mach_timebase_info(&base);
        out->cpu_seconds = ((double)cpu.total_user + cpu.total_system) * base.numer / base.denom / 1e9;
    }
    if (memory) {
        task_vm_info_data_t vm; count = TASK_VM_INFO_COUNT;
        if (task_info(mach_task_self(), TASK_VM_INFO, (task_info_t)&vm, &count) == KERN_SUCCESS) {
            out->footprint_bytes = (int64_t)vm.phys_footprint;
            /* phys_footprint peak is not supplied by this interface. */
        }
#if TARGET_OS_IOS
        out->jetsam_bytes = (int64_t)os_proc_available_memory();
#endif
    }
#endif
}

void tl_em_cpu_work_enable(bool value){atomic_store(&cpu_work_enabled,value);}
static uint64_t cpu_work_clock(void){struct timespec t;if(clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t))return 0;return(uint64_t)t.tv_sec*1000000000ULL+t.tv_nsec;}
bool tl_em_work_begin(tl_em_work_ticket *out){
 if(!out||!atomic_load_explicit(&cpu_work_enabled,memory_order_relaxed)||!atomic_load(&enabled)||atomic_load(&frame_excluded))return false;
 *out=(tl_em_work_ticket){.session=atomic_load(&session),.epoch=atomic_load(&epoch),.cpu_ns=cpu_work_clock(),.wall_ns=(uint64_t)(tl_em_clock()*1e9)};
 return out->cpu_ns!=0;
}
void tl_em_work_end(tl_em_work_ticket t){
 uint64_t cpu=cpu_work_clock(),wall=(uint64_t)(tl_em_clock()*1e9);
 if(pthread_mutex_trylock(&mu)){atomic_fetch_add(&work_drops,1);return;}
 if(!atomic_load(&enabled)||atomic_load(&frame_excluded)||t.session!=atomic_load(&session)||t.epoch!=atomic_load(&epoch)||!t.cpu_ns||cpu<t.cpu_ns||wall<t.wall_ns)atomic_fetch_add(&work_drops,1);
 else {submit_work.calls++;submit_work.cpu_ns+=cpu-t.cpu_ns;submit_work.wall_ns+=wall-t.wall_ns;}
 pthread_mutex_unlock(&mu);
}
void tl_em_work_snapshot(tl_em_work_stats *out){if(!out)return;pthread_mutex_lock(&mu);*out=submit_work;out->dropped=atomic_load(&work_drops);pthread_mutex_unlock(&mu);}
uint32_t tl_em_thread_sample(tl_em_thread *out,uint32_t capacity,tl_em_thread_stats *stats){
 tl_em_thread_stats s={.result=-1};uint32_t returned=0;
#ifdef __APPLE__
 if(!out||!capacity){if(stats)*stats=s;return 0;}
 thread_act_array_t threads=NULL;mach_msg_type_number_t count=0;
 s.result=task_threads(mach_task_self(),&threads,&count);
 if(s.result!=KERN_SUCCESS){if(stats)*stats=s;return 0;}
 s.enumerated=count;s.scanned=count<256?count:256;s.truncated=count>s.scanned;
 for(uint32_t i=0;i<count;i++){
  if(i<s.scanned&&returned<capacity){
   thread_basic_info_data_t info;thread_identifier_info_data_t identity;
   mach_msg_type_number_t n=THREAD_BASIC_INFO_COUNT;int status=thread_info(threads[i],THREAD_BASIC_INFO,(thread_info_t)&info,&n);
   n=THREAD_IDENTIFIER_INFO_COUNT;int id_status=thread_info(threads[i],THREAD_IDENTIFIER_INFO,(thread_info_t)&identity,&n);
   if(status==KERN_SUCCESS&&id_status==KERN_SUCCESS){
    tl_em_thread *row=&out[returned++];memset(row,0,sizeof(*row));row->identity=identity.thread_id;
    row->user_seconds=info.user_time.seconds+info.user_time.microseconds/1e6;row->system_seconds=info.system_time.seconds+info.system_time.microseconds/1e6;row->run_state=info.run_state;
    thread_extended_info_data_t ext;n=THREAD_EXTENDED_INFO_COUNT;
    if(thread_info(threads[i],THREAD_EXTENDED_INFO,(thread_info_t)&ext,&n)==KERN_SUCCESS){memcpy(row->name,ext.pth_name,sizeof(row->name)-1);}
   }else s.failures++;
  }else if(i<s.scanned)s.truncated=true;
  mach_port_deallocate(mach_task_self(),threads[i]);
 }
 vm_deallocate(mach_task_self(),(vm_address_t)threads,(vm_size_t)count*sizeof(*threads));
#else
 (void)out;(void)capacity;
#endif
 s.returned=returned;if(stats)*stats=s;return returned;
}

void tl_em_sync_event(unsigned kind){
 if(kind<TL_SYNC_COUNT&&atomic_load_explicit(&cpu_work_enabled,memory_order_relaxed)&&atomic_load(&enabled)&&!atomic_load(&frame_excluded))atomic_fetch_add_explicit(&sync_counts[kind],1,memory_order_relaxed);
}
void tl_em_sync_snapshot(tl_em_sync_stats *out){
 if(!out)return;
 memset(out,0,sizeof(*out));out->requested=atomic_load(&cpu_work_enabled);
 for(unsigned i=0;i<TL_SYNC_COUNT;i++)out->counts[i]=atomic_load(&sync_counts[i]);
}
