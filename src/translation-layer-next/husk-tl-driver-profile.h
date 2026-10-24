/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_DRIVER_PROFILE_H
#define HUSK_TL_DRIVER_PROFILE_H
#include <stdbool.h>
#include <stddef.h>
/* Opt-in host driver activity counters, NOT GPU execution timestamps.
 * Configure before loading Metal/MoltenVK. */
void husk_ue4_set_driver_profiling(bool enabled);
void tl_dp_set_api(int (*get_statistics)(void *, void *, size_t *), const char *version);
void tl_dp_device(void *device);
void tl_dp_forget(void *device);
void tl_dp_report(void);
#endif
