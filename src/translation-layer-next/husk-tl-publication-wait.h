/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_PUBLICATION_WAIT_H
#define HUSK_TL_PUBLICATION_WAIT_H
#include <stdbool.h>
#include <stdint.h>
/* Experimental launch-time replacement for active initialisation polling.
 * No guest object representation, affinity or ready fast-path change. */
void husk_ue4_set_initialization_parking(bool enabled);
bool tl_publication_parking(void);
void tl_publication_wait(const void *address,bool (*pending)(const void *));
void tl_publication_notify(const void *address);
typedef struct {bool requested;uint64_t waits,wakeups,fallbacks;} tl_publication_stats;
void tl_publication_snapshot(tl_publication_stats *out);
#endif
