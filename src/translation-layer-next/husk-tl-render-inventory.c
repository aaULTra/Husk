/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "husk-tl-render-inventory.h"
#include <stdatomic.h>
#include <pthread.h>
#include <string.h>
#include <stddef.h>
#define GROUPS 256
static atomic_bool requested,active;
static atomic_uint_fast64_t dropped;
static pthread_mutex_t mu=PTHREAD_MUTEX_INITIALIZER;
static tl_ri_group groups[GROUPS];
static uint32_t length;
static uint64_t images,areas;
/* Vulkan 64-bit ABI. No pNext, handles or padding are interpreted as identity. */
typedef struct {uint32_t type;const void *next;uint32_t flags,image_type,format,width,height,depth,mips,layers,samples,tiling,usage;} image_info;
typedef struct {uint32_t type;const void *next;uint64_t renderpass,framebuffer;int32_t x,y;uint32_t width,height;} begin_info;
_Static_assert(offsetof(image_info,width)==28&&offsetof(image_info,usage)==56&&offsetof(begin_info,width)==40,"Vulkan image/render-area ABI");
void husk_ue4_set_render_inventory(bool value){atomic_store(&requested,value);}
void tl_ri_activate(const char *project){
 atomic_store(&active,false);pthread_mutex_lock(&mu);
 memset(groups,0,sizeof(groups));length=0;images=areas=0;atomic_store(&dropped,0);
 atomic_store(&active,atomic_load(&requested)&&project&&!strcmp(project,"Dungeons"));pthread_mutex_unlock(&mu);
}
bool tl_ri_active(void){return atomic_load_explicit(&active,memory_order_relaxed);}
static void record(tl_ri_group value){
 if(!value.width||!value.height)return;
 if(pthread_mutex_trylock(&mu)){atomic_fetch_add(&dropped,1);return;}
 if(!atomic_load(&active)){pthread_mutex_unlock(&mu);return;}
 if(value.kind==0)images++;else areas++;
 unsigned i=0;
 for(;i<length;i++)if(groups[i].kind==value.kind&&groups[i].width==value.width&&groups[i].height==value.height&&groups[i].depth==value.depth&&groups[i].format==value.format&&groups[i].usage==value.usage&&groups[i].samples==value.samples)break;
 if(i<length)groups[i].count++;
 else if(length<GROUPS){value.count=1;groups[length++]=value;}
 else atomic_fetch_add(&dropped,1);
 pthread_mutex_unlock(&mu);
}
void tl_ri_image(const void *raw){
 if(!atomic_load_explicit(&active,memory_order_relaxed)||!raw)return;
 const image_info *p=raw;if(p->type!=14)return;
 record((tl_ri_group){.kind=0,.width=p->width,.height=p->height,.depth=p->depth,.format=p->format,.usage=p->usage,.samples=p->samples});
}
void tl_ri_render_area(const void *raw){
 if(!atomic_load_explicit(&active,memory_order_relaxed)||!raw)return;
 const begin_info *p=raw;if(p->type!=43)return;
 record((tl_ri_group){.kind=1,.width=p->width,.height=p->height,.depth=1});
}
uint32_t tl_ri_snapshot(tl_ri_group *out,uint32_t capacity,tl_ri_stats *stats){
 pthread_mutex_lock(&mu);
 if(stats)*stats=(tl_ri_stats){atomic_load(&requested),atomic_load(&active),images,areas,atomic_load(&dropped)};
 uint32_t n=out?(capacity<length?capacity:length):0;if(n)memcpy(out,groups,n*sizeof(*out));
 pthread_mutex_unlock(&mu);return n;
}
