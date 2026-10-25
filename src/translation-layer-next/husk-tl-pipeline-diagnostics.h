/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_PIPELINE_DIAGNOSTICS_H
#define HUSK_TL_PIPELINE_DIAGNOSTICS_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
/* Layouts of Vulkan 1.0 structs used by this observer, 64-bit guest/host ABI.
 * Shader-state signatures are PARTIAL groups, never replay keys or cache hits.
 * Layout/render-pass compatibility, extensions and some fixed state are absent. */
typedef struct { uint32_t id, offset; size_t size; } tl_pi_map;
typedef struct { uint32_t count; const tl_pi_map *entries; size_t size; const void *data; } tl_pi_specialization;
typedef struct { uint32_t type; const void *next; uint32_t flags, stage; uint64_t module; const char *name; const tl_pi_specialization *specialization; } tl_pi_stage;
typedef struct { uint32_t type; const void *next; uint32_t flags; size_t size; const void *code; } tl_pi_module_ci;
typedef struct {
    uint32_t type; const void *next; uint32_t flags, count; const tl_pi_stage *stages;
    const void *vertex, *assembly, *tessellation, *viewport, *raster, *multisample, *depth, *blend, *dynamic;
    uint64_t layout, renderpass; uint32_t subpass; uint64_t base; int32_t base_index;
} tl_pi_graphics;
typedef struct { uint32_t type; const void *next; uint32_t flags; tl_pi_stage stage; uint64_t layout, base; int32_t base_index; } tl_pi_compute;
typedef struct { uint64_t id[4]; unsigned known[4], sampled, count; } tl_pi_request;
void husk_ue4_set_pipeline_diagnostics(bool enabled);
void tl_pi_shader(void *device, uint64_t module, const tl_pi_module_ci *ci);
void tl_pi_forget_shader(void *device, uint64_t module);
void tl_pi_forget_device(void *device);
tl_pi_request tl_pi_identify(bool compute, void *device, uint32_t count, const void *ci);
void tl_pi_completed(tl_pi_request request, bool compute, uint64_t elapsed_ns, uint64_t finished_ns, bool cache, int result, const void *ci);
void tl_pi_report(void);
#endif
