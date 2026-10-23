/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_UE4_GRAPHICS_H
#define HUSK_TL_UE4_GRAPHICS_H
#include <stdbool.h>
#include <stddef.h>

/* Set before starting the engine; one engine is loaded for the process's lifetime. */
void husk_ue4_set_sharp_graphics(bool enabled);
bool tl_ue4_sharp_graphics_enabled(void);
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
