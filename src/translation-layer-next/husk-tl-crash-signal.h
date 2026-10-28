/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_CRASH_SIGNAL_H
#define HUSK_TL_CRASH_SIGNAL_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
int husk_crash_install(int log_fd,int native_fd);
void husk_crash_native_sink(int fd);
/* Pre-opened durable Files-app crash marker; only write(2) and fsync(2) in signal context. */
void husk_crash_report_sink(int fd);
/* Low-volume fork-specific launch checkpoints, appended to the same durable log. */
void husk_crash_stage(const char *stage);
/* Immutable bounded guest image ranges, published outside a signal handler. */
void husk_crash_note_image(const char *name,uintptr_t bias,uintptr_t begin,uintptr_t end);
#ifdef __cplusplus
}
#endif
#endif
