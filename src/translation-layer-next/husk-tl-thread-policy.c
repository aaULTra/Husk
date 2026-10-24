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

void husk_ue4_set_worker_capacity(int cpu_count)
{
    /* Total CPU capacity hint, not a P/E core detector or placement request. */
    atomic_store(&capacity_cpus, cpu_count > 0 ? cpu_count : 0);
    atomic_store(&fast_workers, cpu_count >= 10 ? 2 : 1);
}
int tl_thread_policy_fast_worker_budget(void) { return atomic_load(&fast_workers); }
bool tl_thread_policy_trial_active(void) { return atomic_load(&trial_active); }
static void set_trial(bool enabled)
{
    if (atomic_exchange(&trial_active, enabled) != enabled) {
        atomic_fetch_add(&revision, 1);
        tl_log_line("thread-policy adaptive: requested %s, normal worker budget %d; applied at worker self checkpoints; no core affinity or energy measurement",
                    enabled ? "extra Utility caps" : "Balanced baseline", atomic_load(&fast_workers));
    }
}
void tl_thread_policy_suspend(void)
{
    if (atomic_load(&active_mode) != 3) return;
    pthread_mutex_lock(&controller_mu);
    set_trial(false); stable_ns = last_sample = 0;
    pthread_mutex_unlock(&controller_mu);
}
void tl_thread_policy_frame(int64_t now, int64_t interval_ns)
{
    static _Thread_local unsigned misses;
    if (atomic_load(&active_mode) != 3 || !atomic_load(&trial_active)) { misses = 0; return; }
    if (interval_ns <= 20500000LL) { misses = 0; return; }
    if (++misses < 6 && interval_ns <= 50000000LL) return;
    if (pthread_mutex_trylock(&controller_mu)) return;
    set_trial(false); cooldown_until = now + 60000000000LL; stable_ns = 0; misses = 0;
    pthread_mutex_unlock(&controller_mu);
}
void tl_thread_policy_sample(int64_t now, int64_t span, double fps, double p95_ms,
                            int thermal, bool low_power, bool pipeline_work)
{
    if (atomic_load(&active_mode) != 3 || pthread_mutex_trylock(&controller_mu)) return;
    bool transition = previous_power >= 0 && previous_power != (int)low_power;
    previous_power = low_power;
    bool discontinuity = last_sample && (now <= last_sample || now - last_sample > 15000000000LL);
    last_sample = now;
    bool valid = span >= 8000000000LL && span <= 15000000000LL && !discontinuity;
    /* Healthy cadence admits an experiment; it does not prove CPU headroom. */
    bool healthy = valid && !transition && thermal == 0 && !pipeline_work && fps >= 59.0 && p95_ms > 0 && p95_ms <= 20.5;
    if (atomic_load(&trial_active)) {
        if (!healthy) { set_trial(false); cooldown_until = now + 60000000000LL; stable_ns = 0; }
    } else if (healthy && now >= cooldown_until) {
        stable_ns += span;
        if (stable_ns >= 20000000000LL) { set_trial(true); stable_ns = 0; }
    } else stable_ns = 0;
    pthread_mutex_unlock(&controller_mu);
}

void husk_ue4_set_thread_policy(int mode)
{
    atomic_store(&requested_mode, mode >= 0 && mode <= 3 ? mode : 0);
}
void tl_thread_policy_activate(const char *project)
{
    int mode = project && !strcmp(project, "Dungeons") ? atomic_load(&requested_mode) : 0;
    atomic_store(&active_mode, mode);
    atomic_store(&log_events, 0);
    atomic_store(&trial_active, false); atomic_fetch_add(&revision, 1);
    stable_ns = cooldown_until = last_sample = 0; previous_power = -1;
    if (mode == 3) tl_log_line("thread-policy adaptive: runtime CPU count %d, reserved normal-worker budget %d; total-capacity heuristic, not detected P/E topology", atomic_load(&capacity_cpus), atomic_load(&fast_workers));
    if (mode) tl_log_line("thread-policy: %s for Dungeons; normal Default and background Utility baseline; extra caps only in admitted Adaptive trials; no core affinity",
                         mode == 3 ? "Adaptive Trial (experimental)" : mode == 2 ? "Balanced (experimental)" : "Observe Only");
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
        if (!result) state.changed = false;
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
        if (!result) state.changed = true;
    }
    int after_relative = 0;
    qos_class_t after = QOS_CLASS_UNSPECIFIED;
    query_result = pthread_get_qos_class_np(pthread_self(), &after, &after_relative);
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
