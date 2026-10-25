/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_PIPELINE_FEEDBACK_H
#define HUSK_TL_PIPELINE_FEEDBACK_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef struct {uint32_t sType;const void *pNext;uint32_t flags,queueCount;const void *queues;uint32_t layerCount;const char *const *layers;uint32_t extCount;const char *const *exts;const uint32_t *features;} tl_pf_device_info;
typedef struct {char name[256];uint32_t specVersion;} tl_pf_extension;
typedef int (*tl_pf_create_fn)(void *,const tl_pf_device_info *,const void *,void **);
typedef int (*tl_pf_enum_fn)(void *,const char *,uint32_t *,tl_pf_extension *);
typedef struct {uint32_t flags;uint64_t duration;} tl_pf_feedback;
typedef struct {uint32_t type;const void *next;tl_pf_feedback *pipeline;uint32_t count;tl_pf_feedback *stages;} tl_pf_info;
typedef struct {void *storage;const void *info;uint32_t injected;} tl_pf_batch;
typedef struct {bool requested,active;uint32_t enabled_devices;uint64_t appended_devices,guest_enabled_devices,unsupported_devices,declined_devices,injected_pipelines,passive_pipelines,skipped_batches;} tl_pf_stats;
void husk_ue4_set_pipeline_feedback(bool value);
void tl_pf_activate(const char *project);
int tl_pf_create_device(void *physical,const tl_pf_device_info *info,const void *alloc,void **out,tl_pf_create_fn create,tl_pf_enum_fn enumerate);
void tl_pf_forget_device(void *device);
/* Copies top-level original infos only; never modifies guest memory, flags,
 * shader state, nested structures or pipeline order. Valid until release. */
const void *tl_pf_prepare(bool compute,void *device,uint32_t count,const void *infos,tl_pf_batch *batch);
void tl_pf_release(tl_pf_batch *batch);
void tl_pf_snapshot(tl_pf_stats *out);
#endif
