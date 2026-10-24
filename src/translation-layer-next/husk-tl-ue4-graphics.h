/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_UE4_GRAPHICS_H
#define HUSK_TL_UE4_GRAPHICS_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Set before starting the engine; one engine is loaded for the process's lifetime. */
void husk_ue4_set_sharp_graphics(bool enabled);
/* Select before MoltenVK loads. 0 driver default, 1 asynchronous (experimental). */
void husk_ue4_set_submission_mode(int mode);
/* Launch-time quality budget. percent=0 selects a conservative display-class
 * budget; explicit 65/75/85/100 percentages remain available for comparisons.
 * No device model claims, runtime calibration, or guaranteed FPS. */
double tl_ue4_resolution_fraction(int width, int height, bool tablet, int percent);
bool tl_ue4_sharp_graphics_enabled(void);
/* Resolution hooks preserve the selected launch size. fps accepts 30 or 60 (default).
 * Thermal values follow NSProcessInfo: nominal=0, fair=1, serious=2, critical=3. */
void husk_ue4_set_efficiency(bool enabled, int fps);
bool tl_ue4_efficiency_enabled(void);
int tl_ue4_effective_frame_limit(int thermal_state);
int64_t tl_ue4_frame_delay_ns(int64_t now, int fps, int64_t *deadline);
/* Caller frees the result. Preserves the developer's TL_UE4_CMDLINE arguments. */
char *tl_ue4_graphics_command_line(const char *base);
/* Startup text read through NDK assets or an existing external command file.
 * NULL means leave the original alone. Returned text is owned by the caller. */
char *tl_ue4_graphics_command_asset(const char *name, const void *data, size_t length);
char *tl_ue4_graphics_command_file(const char *path);
/* Installs/removes only Husk's marked block. Returns false on any I/O failure.
 * Both Android base paths are supplied because Shipping and Development builds
 * choose different roots. Never writes to the APK or to character saves. */
bool tl_ue4_graphics_prepare(const char *internal_dir, const char *external_dir, const char *project);
#endif
