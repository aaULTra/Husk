/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "husk-tl-swapchain-budget.h"
#include <pthread.h>
#include <stddef.h>
#include <string.h>
_Static_assert(sizeof(tl_sb_create)==104&&offsetof(tl_sb_create,min_images)==32&&offsetof(tl_sb_create,queues)==72&&sizeof(tl_sb_caps)==52,"Vulkan swapchain LP64 ABI");
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static struct {void *device,*physical;} devices[16];
static tl_sb_stats stats={.caps_result=-1,.create_result=-1,.images_result=-1};
static bool frozen;static void *last_device;static uint64_t last_swapchain;
void husk_ue4_set_swapchain_images(int images){pthread_mutex_lock(&lock);if(!frozen)stats.requested=images==2||images==3?(uint32_t)images:0;pthread_mutex_unlock(&lock);}
void tl_sb_device(void *physical,void *device){
 if(!physical||!device)return;
 pthread_mutex_lock(&lock);frozen=true;unsigned slot=16;
 for(unsigned i=0;i<16;i++){if(devices[i].device==device){slot=i;break;}if(!devices[i].device&&slot==16)slot=i;}
 if(slot<16){devices[slot].device=device;devices[slot].physical=physical;}else stats.device_capacity_drops++;
 pthread_mutex_unlock(&lock);
}
void tl_sb_forget(void *device){pthread_mutex_lock(&lock);for(unsigned i=0;i<16;i++)if(devices[i].device==device)devices[i].device=NULL;if(last_device==device){last_device=NULL;last_swapchain=0;stats.images_complete=false;}pthread_mutex_unlock(&lock);}
const void *tl_sb_prepare(void *device,const void *original,tl_sb_query query,tl_sb_create *copy,uint64_t *ticket){
 if(!original||!copy)return original;
 const tl_sb_create *ci=original;void *physical=NULL;unsigned request;
 pthread_mutex_lock(&lock);frozen=true;request=stats.requested;stats.create_calls++;uint64_t generation=++stats.generation;if(ticket)*ticket=generation;last_device=NULL;last_swapchain=0;
 stats.original_min=stats.selected_min=ci->min_images;stats.attempted=request!=0;stats.eligible=false;stats.override_applied=false;stats.images_complete=false;stats.returned_images=0;stats.caps_result=-1;stats.surface_min=stats.surface_max=0;stats.create_result=-1;stats.images_result=-1;stats.create_completed=false;
 for(unsigned i=0;i<16;i++)if(devices[i].device==device){physical=devices[i].physical;break;}
 pthread_mutex_unlock(&lock);
 if(!request)return original;
 /* Extended/shared/deferred swapchains may have additional constraints. Do not
  * guess them; decline while preserving every original API argument. */
 tl_sb_caps caps={0};bool core=ci->type==1000001000u&&!ci->next&&!ci->flags&&ci->layers==1;
 int result=core&&query&&physical?query(physical,ci->surface,&caps):-1;
 bool eligible=result==0&&caps.min_images>0&&(caps.max_images==0||caps.max_images>=caps.min_images)&&request>=caps.min_images&&(caps.max_images==0||request<=caps.max_images);
 if(eligible){*copy=*ci;copy->min_images=request;}
 pthread_mutex_lock(&lock);if(stats.generation==generation){stats.caps_result=result;stats.surface_min=caps.min_images;stats.surface_max=caps.max_images;stats.eligible=eligible;
 if(eligible){stats.selected_min=request;stats.override_applied=request!=ci->min_images;if(stats.override_applied)stats.override_calls++;}else stats.rejections++;}
 pthread_mutex_unlock(&lock);return eligible?copy:original;
}
void tl_sb_created(void *device,uint64_t swapchain,int result,uint64_t ticket){pthread_mutex_lock(&lock);if(stats.generation==ticket){stats.create_result=result;stats.create_completed=true;if(result==0&&swapchain){last_device=device;last_swapchain=swapchain;}}pthread_mutex_unlock(&lock);}
void tl_sb_images(void *device,uint64_t swapchain,int result,uint32_t count,bool count_only){
 (void)count_only;pthread_mutex_lock(&lock);
 if(device==last_device&&swapchain==last_swapchain){stats.images_result=result;stats.returned_images=(result==0||result==5)?count:0;stats.images_complete=result==0&&count>0;}
 pthread_mutex_unlock(&lock);
}
void tl_sb_snapshot(tl_sb_stats *out){if(out){pthread_mutex_lock(&lock);*out=stats;pthread_mutex_unlock(&lock);}}
