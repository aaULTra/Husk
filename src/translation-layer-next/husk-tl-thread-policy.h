/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_THREAD_POLICY_H
#define HUSK_TL_THREAD_POLICY_H
#include <stdint.h>
#include <stdbool.h>
/* Configure before UE4 startup. 0=unchanged, 1=observe, 2=balanced caps, 3=adaptive trial.
 * Activation is restricted to the exact UE4 project Dungeons. */
void husk_ue4_set_thread_policy(int mode);
void tl_thread_policy_activate(const char *project);
void tl_thread_policy_named(const char *name);
void husk_ue4_set_worker_capacity(int cpu_count);
/* Cadence-only experiment guard; not job-deadline or GPU attribution. */
void tl_thread_policy_sample(int64_t now, int64_t span, double fps, double p95_ms,
                            int thermal, bool low_power, bool pipeline_work);
void tl_thread_policy_suspend(void);
void tl_thread_policy_frame(int64_t now, int64_t interval_ns);
void tl_thread_policy_checkpoint(void);
int tl_thread_policy_fast_worker_budget(void);
bool tl_thread_policy_trial_active(void);
/* Portable classifier: 0=preserve, 1=normal worker, 2=background worker. */
int tl_thread_policy_role(const char *name);
#endif
