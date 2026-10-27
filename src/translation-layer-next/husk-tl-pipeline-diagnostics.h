/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_PIPELINE_DIAGNOSTICS_H
#define HUSK_TL_PIPELINE_DIAGNOSTICS_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
/* Layouts of Vulkan 1.0 structs used by this observer, 64-bit guest/host ABI.
 * Versioned diagnostic groups, never replay keys or cache hits. full_core means
 * tracked recognised core fields; unsupported extensions/missing objects remain
 * partial. This is not a minimal Vulkan render-pass compatibility key. */
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
enum { TL_PI_SHADER_STATE=1, TL_PI_FIXED_STATE=2, TL_PI_LAYOUT_STATE=4,
       TL_PI_RENDER_STATE=8, TL_PI_BASE_STATE=16, TL_PI_UNSUPPORTED=1u<<16,
       TL_PI_MISSING_OBJECT=1u<<17 };
enum { TL_PI_SAMPLER=1, TL_PI_DESCRIPTOR_LAYOUT, TL_PI_PIPELINE_LAYOUT,
       TL_PI_RENDER_PASS, TL_PI_PIPELINE };
typedef struct { uint64_t id[4], shader_hashes[4]; unsigned known[4], sampled, count, shader_stages; uint32_t stage_bits[4], coverage[4], full_core[4]; } tl_pi_request;
void husk_ue4_set_pipeline_diagnostics(bool enabled);
bool tl_pi_active(void);
void tl_pi_shader(void *device, uint64_t module, const tl_pi_module_ci *ci);
void tl_pi_forget_shader(void *device, uint64_t module);
void tl_pi_forget_device(void *device);
void tl_pi_object(unsigned kind,void *device,uint64_t handle,const void *ci);
void tl_pi_forget_object(unsigned kind,void *device,uint64_t handle);
void tl_pi_pipeline_objects(tl_pi_request request,void *device,const uint64_t *handles);
tl_pi_request tl_pi_identify(bool compute, void *device, uint32_t count, const void *ci);
void tl_pi_completed(tl_pi_request request, bool compute, uint64_t elapsed_ns, uint64_t finished_ns, bool cache, int result, const void *ci);
void tl_pi_report(void);
/* Lifetime since game launch; one group per batch's first sampled partial key.
 * Durations may overlap. This cannot reconstruct pipelines or prove cache hits. */
typedef struct { uint64_t signature, calls, slow_calls, total_ns, worst_ns, valid_feedback, application_hits, stage_feedback_valid, stage_application_hits; uint64_t shader_hashes[4]; uint32_t stage_bits[4], shader_stages, last_stage_valid_mask, last_stage_hit_mask; uint32_t coverage,full_core; uint64_t full_core_calls; } tl_pi_group;
uint32_t tl_pi_copy_groups(tl_pi_group *out, uint32_t capacity);
/* Process-lifetime observer work/coverage, not driver cache or energy metrics. */
typedef struct {
 uint32_t enabled,shader_capacity,shader_live,object_capacity,object_live;
 uint64_t shader_lookup_probes,shader_capacity_drops,object_capacity_drops;
 uint64_t missing_shader_references,missing_object_references,incomplete_object_references;
} tl_pi_registry_stats;
void tl_pi_registry_snapshot(tl_pi_registry_stats *out);

#endif
