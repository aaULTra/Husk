/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "husk-tl-thread-policy.h"
#include <stdatomic.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <pthread.h>
#include <errno.h>

#if defined(__APPLE__) || defined(HUSK_THREAD_POLICY_TEST)
#include <pthread.h>
#if defined(HUSK_THREAD_POLICY_TEST)
#include "husk-thread-policy-test-api.h"
#else
#include <pthread/qos.h>
#endif
#endif

void tl_log_line(const char *fmt, ...);
static atomic_int requested_mode, active_mode;
static atomic_uint log_events;
static atomic_uint revision;
static atomic_int fast_workers = 1, capacity_cpus;
static atomic_bool trial_active;
static pthread_mutex_t controller_mu = PTHREAD_MUTEX_INITIALIZER;
static int64_t stable_ns, cooldown_until, last_sample;
static int previous_power = -1;
static const char *last_reason;
static int64_t reason_at;

#define WORKER_RECORDS 64
static pthread_mutex_t observation_mu = PTHREAD_MUTEX_INITIALIZER;
static tl_worker_observation worker_records[WORKER_RECORDS];
static atomic_uint_fast64_t admissions, rollbacks, caps, restores, query_failures, set_failures, observation_drops;
#if defined(__APPLE__) || defined(HUSK_THREAD_POLICY_TEST)
static atomic_uint_fast64_t next_identity;
#endif
#if defined(__APPLE__) || defined(HUSK_THREAD_POLICY_TEST)
static _Thread_local uint64_t observation_identity;
#endif
#if defined(__APPLE__) || defined(HUSK_THREAD_POLICY_TEST)
static void observe_worker(const char *name, unsigned role, unsigned mode, unsigned rev,
                           unsigned before, unsigned after, int query_result, int set_result, bool changed) {
    if (!observation_identity) observation_identity = atomic_fetch_add(&next_identity, 1) + 1;
    if (pthread_mutex_trylock(&observation_mu)) { atomic_fetch_add(&observation_drops,1); return; }
    unsigned slot=WORKER_RECORDS;
    for(unsigned i=0;i<WORKER_RECORDS;i++) {
        if(worker_records[i].identity==observation_identity){slot=i;break;}
        if(!worker_records[i].identity&&slot==WORKER_RECORDS)slot=i;
    }
    if(slot<WORKER_RECORDS){
        struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);
        tl_worker_observation *v=&worker_records[slot];
        *v=(tl_worker_observation){.identity=observation_identity,.observed_monotonic=t.tv_sec+t.tv_nsec/1e9,
             .role=role,.mode=mode,.revision=rev,.before_qos=before,.after_qos=after,
             .query_result=query_result,.set_result=set_result,.changed=changed};
        snprintf(v->name,sizeof(v->name),"%s",name);
    }else atomic_fetch_add(&observation_drops,1);
    pthread_mutex_unlock(&observation_mu);
}
#endif
uint32_t tl_thread_policy_observations(tl_worker_observation *out,uint32_t capacity) {
    if(!out||!capacity)return 0;
    pthread_mutex_lock(&observation_mu);uint32_t n=0;
    for(unsigned i=0;i<WORKER_RECORDS&&n<capacity;i++)if(worker_records[i].identity)out[n++]=worker_records[i];
    pthread_mutex_unlock(&observation_mu);return n;
}
void tl_thread_policy_summary(tl_worker_summary *out) {
    memset(out,0,sizeof(*out));pthread_mutex_lock(&controller_mu);
    out->requested_mode=atomic_load(&requested_mode);out->active_mode=atomic_load(&active_mode);
    out->revision=atomic_load(&revision);out->capacity_hint=atomic_load(&capacity_cpus);
    out->fast_worker_budget=atomic_load(&fast_workers);out->trial_requested=atomic_load(&trial_active);
    out->admissions=atomic_load(&admissions);out->rollback_requests=atomic_load(&rollbacks);
    out->caps_applied=atomic_load(&caps);out->restores_applied=atomic_load(&restores);
    out->query_failures=atomic_load(&query_failures);out->set_failures=atomic_load(&set_failures);
    out->dropped_observations=atomic_load(&observation_drops);out->stable_seconds=stable_ns/1e9;
    struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);double now=t.tv_sec+t.tv_nsec/1e9;
    out->cooldown_remaining_seconds=cooldown_until/1e9>now?cooldown_until/1e9-now:0;
    const char *reason=out->active_mode!=3?"Adaptive not selected":out->trial_requested?"trial requested; check worker observations":last_reason?last_reason:"waiting for cadence sample";
    snprintf(out->waiting_reason,sizeof(out->waiting_reason),"%s",reason);
    pthread_mutex_unlock(&controller_mu);
}

void husk_ue4_set_worker_capacity(int cpu_count)
{
    /* Total CPU capacity hint, not a P/E core detector or placement request. */
    atomic_store(&capacity_cpus, cpu_count > 0 ? cpu_count : 0);
    atomic_store(&fast_workers, cpu_count >= 10 ? 2 : 1);
}
int tl_thread_policy_fast_worker_budget(void) { return atomic_load(&fast_workers); }
bool tl_thread_policy_trial_active(void) { return atomic_load(&trial_active); }
static void set_trial(bool enabled, const char *reason)
{
    if (atomic_exchange(&trial_active, enabled) != enabled) {
        atomic_fetch_add(&revision, 1);
        atomic_fetch_add(enabled ? &admissions : &rollbacks, 1);
        tl_log_line("thread-policy adaptive: requested %s, reason %s, normal worker budget %d; applied at worker self checkpoints; no core affinity or energy measurement",
                    enabled ? "extra Utility caps" : "Balanced baseline", reason, atomic_load(&fast_workers));
    }
}
void tl_thread_policy_suspend(void)
{
    if (atomic_load(&active_mode) != 3) return;
    pthread_mutex_lock(&controller_mu);
    set_trial(false, "pause or power/thermal change"); stable_ns = last_sample = 0; last_reason = NULL;
    pthread_mutex_unlock(&controller_mu);
}
void tl_thread_policy_frame(int64_t now, int64_t interval_ns)
{
    static _Thread_local unsigned misses;
    if (atomic_load(&active_mode) != 3 || !atomic_load(&trial_active)) { misses = 0; return; }
    if (interval_ns <= 20500000LL) { misses = 0; return; }
    if (++misses < 6 && interval_ns <= 50000000LL) return;
    if (pthread_mutex_trylock(&controller_mu)) return;
    set_trial(false, "frame spike"); cooldown_until = now + 60000000000LL; stable_ns = 0; misses = 0;
    pthread_mutex_unlock(&controller_mu);
}
void tl_thread_policy_pipeline_completed(int64_t now, int64_t elapsed_ns)
{
    if (elapsed_ns <= TL_WORKER_PIPELINE_MAX_NS || atomic_load(&active_mode) != 3 ||
        !atomic_load(&trial_active) || pthread_mutex_trylock(&controller_mu)) return;
    set_trial(false, "expensive pipeline call"); cooldown_until = now + 60000000000LL; stable_ns = 0;
    pthread_mutex_unlock(&controller_mu);
}
void tl_thread_policy_sample(int64_t now, int64_t span, double fps, double p95_ms,
                            double max_frame_ms, int thermal, bool low_power,
                            uint64_t pipeline_ns, uint64_t pipeline_max_ns, unsigned pipeline_inflight)
{
    if (atomic_load(&active_mode) != 3 || pthread_mutex_trylock(&controller_mu)) return;
    bool transition = previous_power >= 0 && previous_power != (int)low_power;
    previous_power = low_power;
    bool discontinuity = last_sample && (now <= last_sample || now - last_sample > 15000000000LL);
    last_sample = now;
    bool valid = span >= 8000000000LL && span <= 15000000000LL && !discontinuity;
    const char *reason = !valid ? "sample gap/loading" : transition ? "LPM transition" :
        thermal != 0 ? "thermal pressure" : pipeline_inflight ? "pipeline in flight" :
        pipeline_max_ns > TL_WORKER_PIPELINE_MAX_NS || pipeline_ns > (uint64_t)span / 200 ? "pipeline cost" :
        !(fps >= 59.0 && p95_ms > 0 && p95_ms <= 20.5 && max_frame_ms > 0 && max_frame_ms <= 50) ? "frame cadence" : NULL;
    /* Small measured pipeline work is allowed; cadence does not prove headroom. */
    bool healthy = !reason;
    if (atomic_load(&trial_active)) {
        if (!healthy) { set_trial(false, reason); cooldown_until = now + 60000000000LL; stable_ns = 0; }
    } else if (healthy && now >= cooldown_until) {
        stable_ns += span;
        if (stable_ns >= 20000000000LL) { set_trial(true, "healthy cadence and bounded pipeline cost"); stable_ns = 0; }
    } else stable_ns = 0;
    if (!atomic_load(&trial_active)) {
        if (!reason) reason = now < cooldown_until ? "cooldown" : "collecting healthy cadence";
        if (!last_reason || strcmp(last_reason, reason) || now - reason_at >= 30000000000LL) {
            tl_log_line("thread-policy adaptive: waiting: %s; stable %.1f/20 s, pipeline total %.3f ms max %.3f ms in-flight %u; heuristic limits 2 ms/call and 0.5%%/window",
                        reason, stable_ns / 1e9, pipeline_ns / 1e6, pipeline_max_ns / 1e6, pipeline_inflight);
            last_reason = reason; reason_at = now;
        }
    } else last_reason = NULL;
    pthread_mutex_unlock(&controller_mu);
}

void husk_ue4_set_thread_policy(int mode)
{
    atomic_store(&requested_mode, mode >= 0 && mode <= 3 ? mode : 0);
}
void tl_thread_policy_activate(const char *project)
{
    int mode = project && !strcmp(project, "Dungeons") ? atomic_load(&requested_mode) : 0;
    pthread_mutex_lock(&controller_mu);
    atomic_store(&active_mode, mode);
    atomic_store(&admissions,0);atomic_store(&rollbacks,0);atomic_store(&caps,0);atomic_store(&restores,0);
    atomic_store(&query_failures,0);atomic_store(&set_failures,0);atomic_store(&observation_drops,0);
    pthread_mutex_lock(&observation_mu);memset(worker_records,0,sizeof(worker_records));pthread_mutex_unlock(&observation_mu);
    atomic_store(&log_events, 0);
    atomic_store(&trial_active, false); atomic_fetch_add(&revision, 1);
    stable_ns = cooldown_until = last_sample = 0; previous_power = -1;
    last_reason = NULL; reason_at = 0;
    if (mode == 3) tl_log_line("thread-policy adaptive: runtime CPU count %d, reserved normal-worker budget %d; total-capacity heuristic, not detected P/E topology", atomic_load(&capacity_cpus), atomic_load(&fast_workers));
    if (mode) tl_log_line("thread-policy: %s for Dungeons; normal Default and background Utility baseline; extra caps only in admitted Adaptive trials; no core affinity",
                         mode == 3 ? "Adaptive Trial (experimental)" : mode == 2 ? "Balanced (experimental)" : "Observe Only");
    pthread_mutex_unlock(&controller_mu);
}

static bool pool_name(const char *name, const char *prefix)
{
    size_t n = strlen(prefix);
    if (strncmp(name, prefix, n)) return false;
    const char *p = name + n;
    if (!*p) return true;
    if (*p++ != ' ' || *p < '0' || *p > '9') return false;
    while (*p >= '0' && *p <= '9') ++p;
    return !*p;
}
int tl_thread_policy_role(const char *name)
{
    if (!name) return 0;
    if (pool_name(name, "TaskGraphThreadNP") || pool_name(name, "TaskGraphNP")) return 1;
    if (pool_name(name, "TaskGraphThreadBP") || pool_name(name, "TaskGraphBP")) return 2;
    return 0;
}

#if defined(__APPLE__) || defined(HUSK_THREAD_POLICY_TEST)
/* A renamed worker must not leave a critical/new role stuck at its old cap.
 * Preserve the pre-policy requested class and relative priority per thread.
 * Unspecified QoS cannot be faithfully restored with the public setter, so
 * those threads are observed without modification. */
static _Thread_local struct {
    bool changed;
    qos_class_t original;
    int relative;
    char name[64];
    unsigned seen_revision;
    int64_t retry_after;
} state;
static int64_t policy_now(void)
{
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (int64_t)t.tv_sec * 1000000000LL + t.tv_nsec;
}
static int normal_index(const char *name)
{
    const char *p = name + (!strncmp(name, "TaskGraphThreadNP", 17) ? 17 : 11);
    if (*p++ != ' ' || !*p) return -1;
    char *end; long index = strtol(p, &end, 10);
    return !*end && index >= 0 && index < 100000 ? (int)index : -1;
}
void tl_thread_policy_checkpoint(void)
{
    if (atomic_load(&active_mode) != 3 || !state.name[0] || state.seen_revision == atomic_load(&revision)) return;
    int saved_errno = errno;
    if (state.retry_after && policy_now() < state.retry_after) { errno = saved_errno; return; }
    tl_thread_policy_named(state.name);
    errno = saved_errno;
}

void tl_thread_policy_named(const char *name)
{
    int mode = atomic_load(&active_mode);
    if (!mode || !name || !*name) return;
    if (name != state.name) {
        if (strlen(name) < sizeof(state.name)) snprintf(state.name, sizeof(state.name), "%s", name);
        else state.name[0] = 0;
    }
    unsigned target_revision = atomic_load(&revision);
    int before_relative = 0;
    qos_class_t before = QOS_CLASS_UNSPECIFIED;
    int query_result = pthread_get_qos_class_np(pthread_self(), &before, &before_relative);
    if (query_result) {
        atomic_fetch_add(&query_failures,1);
        observe_worker(name,tl_thread_policy_role(name),mode,target_revision,0,0,query_result,0,state.changed);
        state.retry_after = policy_now() + 1000000000LL;
        if (atomic_fetch_add(&log_events, 1) < 128)
            tl_log_line("thread-policy: name='%s' mode=%d initial QoS query failed rc=%d; policy unchanged",
                        name, mode, query_result);
        return;
    }
    if (!state.changed) {
        state.original = before;
        state.relative = before_relative;
    }
    int result = 0;
    if (state.changed) {
        result = pthread_set_qos_class_self_np(state.original, state.relative);
        if (!result) { state.changed = false; atomic_fetch_add(&restores,1); }
        else atomic_fetch_add(&set_failures,1);
    }
    int role = tl_thread_policy_role(name);
    qos_class_t cap = role == 1 ? QOS_CLASS_DEFAULT : QOS_CLASS_UTILITY;
    if (mode == 3 && role == 1 && atomic_load(&trial_active)) {
        int index = normal_index(name);
        if (index >= atomic_load(&fast_workers)) cap = QOS_CLASS_UTILITY;
    }
    /* Never raise a thread's original QoS. Restore before every reclassification
     * and stop if restoration failed, retaining that fact for a later retry. */
    if (!result && (mode == 2 || mode == 3) && role && state.original != QOS_CLASS_UNSPECIFIED && state.original > cap) {
        result = pthread_set_qos_class_self_np(cap, state.relative);
        if (!result) { state.changed = true; atomic_fetch_add(&caps,1); }
        else atomic_fetch_add(&set_failures,1);
    }
    int after_relative = 0;
    qos_class_t after = QOS_CLASS_UNSPECIFIED;
    query_result = pthread_get_qos_class_np(pthread_self(), &after, &after_relative);
    if (query_result) atomic_fetch_add(&query_failures,1);
    observe_worker(name,role,mode,target_revision,before,after,query_result,result,state.changed);
    if (!result && !query_result) { state.seen_revision = target_revision; state.retry_after = 0; }
    else state.retry_after = policy_now() + 1000000000LL;
    if (atomic_fetch_add(&log_events, 1) < 128)
        tl_log_line("thread-policy: name='%s' role=%s mode=%d requested QoS %#x/%d -> %#x/%d rc=%d after_query_rc=%d; core placement not measured",
                    name, role == 1 ? "normal-worker" : role == 2 ? "background-worker" : "preserve",
                    mode, (unsigned)before, before_relative, (unsigned)after, after_relative, result, query_result);
}
#else
void tl_thread_policy_named(const char *name) { (void)name; }
void tl_thread_policy_checkpoint(void) {}
#endif
