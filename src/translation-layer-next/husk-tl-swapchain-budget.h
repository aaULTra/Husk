/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_SWAPCHAIN_BUDGET_H
#define HUSK_TL_SWAPCHAIN_BUDGET_H
#include <stdbool.h>
#include <stdint.h>
/* Core LP64 ABI only; no retained caller descriptors or changed pNext chains. */
typedef struct {uint32_t type;const void *next;uint32_t flags;uint64_t surface;uint32_t min_images,format,color_space,width,height,layers,usage,sharing,queue_count;const uint32_t *queues;uint32_t transform,alpha,present_mode,clipped;uint64_t old_swapchain;} tl_sb_create;
typedef struct {uint32_t min_images,max_images,current_width,current_height,min_width,min_height,max_width,max_height,max_layers,transforms,current_transform,alpha,usage;} tl_sb_caps;
typedef int(*tl_sb_query)(void*,uint64_t,tl_sb_caps*);
typedef struct {uint32_t requested,original_min,selected_min,surface_min,surface_max,returned_images;bool attempted,eligible,override_applied,images_complete,create_completed;int32_t caps_result,create_result,images_result;uint64_t create_calls,override_calls,rejections,device_capacity_drops,generation;} tl_sb_stats;
void husk_ue4_set_swapchain_images(int images);
void tl_sb_device(void *physical,void *device);
void tl_sb_forget(void *device);
const void *tl_sb_prepare(void *device,const void *original,tl_sb_query query,tl_sb_create *copy,uint64_t *ticket);
void tl_sb_created(void *device,uint64_t swapchain,int result,uint64_t ticket);
void tl_sb_images(void *device,uint64_t swapchain,int result,uint32_t count,bool count_only);
void tl_sb_snapshot(tl_sb_stats *out);
#endif
