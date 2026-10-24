/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "husk-tl-thread-policy.h"
#include <stdatomic.h>
#include <stdbool.h>
#include <string.h>

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

void husk_ue4_set_thread_policy(int mode)
{
    atomic_store(&requested_mode, mode >= 0 && mode <= 2 ? mode : 0);
}
void tl_thread_policy_activate(const char *project)
{
    int mode = project && !strcmp(project, "Dungeons") ? atomic_load(&requested_mode) : 0;
    atomic_store(&active_mode, mode);
    atomic_store(&log_events, 0);
    if (mode) tl_log_line("thread-policy: %s for Dungeons; named NP workers capped at Default and BP workers at Utility only in Balanced; no core affinity",
                         mode == 2 ? "Balanced (experimental)" : "Observe Only");
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
} state;

void tl_thread_policy_named(const char *name)
{
    int mode = atomic_load(&active_mode);
    if (!mode || !name || !*name) return;
    int before_relative = 0;
    qos_class_t before = QOS_CLASS_UNSPECIFIED;
    int query_result = pthread_get_qos_class_np(pthread_self(), &before, &before_relative);
    if (query_result) {
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
    /* Never raise a thread's original QoS. Restore before every reclassification
     * and stop if restoration failed, retaining that fact for a later retry. */
    if (!result && mode == 2 && role && state.original != QOS_CLASS_UNSPECIFIED && state.original > cap) {
        result = pthread_set_qos_class_self_np(cap, state.relative);
        if (!result) state.changed = true;
    }
    int after_relative = 0;
    qos_class_t after = QOS_CLASS_UNSPECIFIED;
    query_result = pthread_get_qos_class_np(pthread_self(), &after, &after_relative);
    if (atomic_fetch_add(&log_events, 1) < 128)
        tl_log_line("thread-policy: name='%s' role=%s mode=%d requested QoS %#x/%d -> %#x/%d rc=%d after_query_rc=%d; core placement not measured",
                    name, role == 1 ? "normal-worker" : role == 2 ? "background-worker" : "preserve",
                    mode, (unsigned)before, before_relative, (unsigned)after, after_relative, result, query_result);
}
#else
void tl_thread_policy_named(const char *name) { (void)name; }
#endif
