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
/* Conservative host-cost/cadence heuristics, not job-deadline or GPU attribution.
 * Permit <=2 ms individual pipeline calls and <=0.5% aggregate host pipeline
 * time in a healthy window; these are trial guards, not measured optima. */
#define TL_WORKER_PIPELINE_MAX_NS 2000000LL
void tl_thread_policy_sample(int64_t now, int64_t span, double fps, double p95_ms,
                            double max_frame_ms, int thermal, bool low_power,
                            uint64_t pipeline_ns, uint64_t pipeline_max_ns, unsigned pipeline_inflight);
void tl_thread_policy_pipeline_completed(int64_t now, int64_t elapsed_ns);
void tl_thread_policy_suspend(void);
void tl_thread_policy_frame(int64_t now, int64_t interval_ns);
void tl_thread_policy_checkpoint(void);
int tl_thread_policy_fast_worker_budget(void);
bool tl_thread_policy_trial_active(void);
/* Portable classifier: 0=preserve, 1=normal worker, 2=background worker. */
int tl_thread_policy_role(const char *name);
#endif
