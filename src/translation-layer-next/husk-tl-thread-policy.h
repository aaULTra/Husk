/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_THREAD_POLICY_H
#define HUSK_TL_THREAD_POLICY_H
/* Configure before UE4 startup. 0=unchanged, 1=observe, 2=balanced caps,
 * 3=device-aware caps (reserve up to two normal task-graph workers at original QoS).
 * Activation is restricted to the exact UE4 project Dungeons. */
void husk_ue4_set_thread_policy(int mode);
void tl_thread_policy_activate(const char *project);
void tl_thread_policy_named(const char *name);
/* Portable classifier: 0=preserve, 1=normal worker, 2=background worker. */
int tl_thread_policy_role(const char *name);
#endif
