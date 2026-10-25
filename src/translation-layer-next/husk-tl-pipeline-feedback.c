/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "husk-tl-pipeline-feedback.h"
#include "husk-tl-pipeline-diagnostics.h"
#include <pthread.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#define FEEDBACK_TYPE 1000192000u
#define MAX_BATCH 64
#define MAX_STAGES 16
static const char extension_name[]="VK_EXT_pipeline_creation_feedback";
static pthread_mutex_t mu=PTHREAD_MUTEX_INITIALIZER;
static atomic_bool requested,active;
static struct {void *device;} devices[8];
static tl_pf_stats stats;
_Static_assert(sizeof(tl_pf_device_info)==72&&offsetof(tl_pf_device_info,extCount)==48&&sizeof(tl_pf_feedback)==16&&sizeof(tl_pf_info)==40,"Vulkan feedback/device ABI");
void husk_ue4_set_pipeline_feedback(bool value){atomic_store(&requested,value);}
void tl_pf_activate(const char *project){
 atomic_store(&active,false);pthread_mutex_lock(&mu);memset(devices,0,sizeof(devices));memset(&stats,0,sizeof(stats));
 atomic_store(&active,atomic_load(&requested)&&project&&!strcmp(project,"Dungeons"));pthread_mutex_unlock(&mu);
}
static void register_device(void *device,bool enabled){
 if(!device||!enabled)return;
 pthread_mutex_lock(&mu);unsigned i=0;for(;i<8;i++)if(devices[i].device==device||!devices[i].device)break;
 if(i<8){if(!devices[i].device)stats.enabled_devices++;devices[i].device=device;}else stats.declined_devices++;
 pthread_mutex_unlock(&mu);
}
void tl_pf_forget_device(void *device){pthread_mutex_lock(&mu);for(unsigned i=0;i<8;i++)if(devices[i].device==device){devices[i].device=NULL;stats.enabled_devices--;}pthread_mutex_unlock(&mu);}
static bool advertised(void *physical,tl_pf_enum_fn enumerate){
 uint32_t count=0;if(!enumerate||enumerate(physical,NULL,&count,NULL)!=0||!count||count>1024)return false;
 tl_pf_extension *ext=calloc(count,sizeof(*ext));if(!ext)return false;
 uint32_t capacity=count;int result=enumerate(physical,NULL,&count,ext);bool found=false;
 if(result==0&&count<=capacity)for(unsigned i=0;i<count;i++)if(!strncmp(ext[i].name,extension_name,sizeof(extension_name)))found=true;
 free(ext);return found;
}
int tl_pf_create_device(void *physical,const tl_pf_device_info *info,const void *alloc,void **out,tl_pf_create_fn create,tl_pf_enum_fn enumerate){
 if(!create)return -3;
 if(!atomic_load(&active)||!info)return create(physical,info,alloc,out);
 bool guest=false;
 if(info->extCount>1024||(info->extCount&&!info->exts)){pthread_mutex_lock(&mu);stats.declined_devices++;pthread_mutex_unlock(&mu);return create(physical,info,alloc,out);}
 for(unsigned i=0;i<info->extCount;i++)if(info->exts[i]&&!strcmp(info->exts[i],extension_name))guest=true;
 if(guest){int r=create(physical,info,alloc,out);if(!r&&out&&*out){register_device(*out,true);pthread_mutex_lock(&mu);stats.guest_enabled_devices++;pthread_mutex_unlock(&mu);}return r;}
 if(!advertised(physical,enumerate)){pthread_mutex_lock(&mu);stats.unsupported_devices++;pthread_mutex_unlock(&mu);return create(physical,info,alloc,out);}
 const char **names=calloc(info->extCount+1,sizeof(*names));
 if(!names){pthread_mutex_lock(&mu);stats.declined_devices++;pthread_mutex_unlock(&mu);return create(physical,info,alloc,out);}
 for(unsigned i=0;i<info->extCount;i++){names[i]=info->exts[i];}
 names[info->extCount]=extension_name;
 tl_pf_device_info copy=*info;copy.extCount++;copy.exts=names;
 int result=create(physical,&copy,alloc,out);free(names);
 if(result==-7){pthread_mutex_lock(&mu);stats.declined_devices++;pthread_mutex_unlock(&mu);return create(physical,info,alloc,out);}
 if(!result&&out&&*out){register_device(*out,true);pthread_mutex_lock(&mu);stats.appended_devices++;pthread_mutex_unlock(&mu);}
 return result;
}
static bool has_feedback(const void *chain,bool *bounded){
 typedef struct node{uint32_t type;const struct node *next;}node;
 const node *p=chain;for(unsigned i=0;p&&i<32;i++,p=p->next)if(p->type==FEEDBACK_TYPE)return true;
 if(p){*bounded=false;}
 return false;
}
const void *tl_pf_prepare(bool compute,void *device,uint32_t count,const void *infos,tl_pf_batch *batch){
 *batch=(tl_pf_batch){.info=infos};if(!atomic_load_explicit(&active,memory_order_relaxed))return infos;
 pthread_mutex_lock(&mu);bool enabled=false;for(unsigned i=0;i<8;i++)if(devices[i].device==device&&device)enabled=true;pthread_mutex_unlock(&mu);
 if(!enabled||!infos||!count||count>MAX_BATCH){pthread_mutex_lock(&mu);stats.skipped_batches++;pthread_mutex_unlock(&mu);return infos;}
 size_t info_size=compute?sizeof(tl_pi_compute):sizeof(tl_pi_graphics);
 unsigned char *storage=calloc(count,info_size+sizeof(tl_pf_info)+sizeof(tl_pf_feedback)*(MAX_STAGES+1));if(!storage){pthread_mutex_lock(&mu);stats.skipped_batches++;pthread_mutex_unlock(&mu);return infos;}
 tl_pi_graphics *graphics=(tl_pi_graphics *)storage;tl_pi_compute *computes=(tl_pi_compute *)storage;
 tl_pf_info *feedback=(tl_pf_info *)(storage+count*info_size);
 tl_pf_feedback *pipeline=(tl_pf_feedback *)(feedback+count);
 tl_pf_feedback (*stages_out)[MAX_STAGES]=(void *)(pipeline+count);
 memcpy(storage,infos,count*info_size);
 uint32_t injected=0,passive=0;
 for(unsigned i=0;i<count;i++){
  const void *chain=compute?computes[i].next:graphics[i].next;bool bounded=true;
  if(has_feedback(chain,&bounded)){passive++;continue;}
  uint32_t stages=compute?1:graphics[i].count;
  uint32_t type=compute?computes[i].type:graphics[i].type;
  if(!bounded||!stages||stages>MAX_STAGES||type!=(compute?29u:28u))continue;
  feedback[i]=(tl_pf_info){FEEDBACK_TYPE,chain,&pipeline[i],stages,stages_out[i]};
  if(compute)computes[i].next=&feedback[i];else graphics[i].next=&feedback[i];injected++;
 }
 pthread_mutex_lock(&mu);stats.injected_pipelines+=injected;stats.passive_pipelines+=passive;if(!injected)stats.skipped_batches++;pthread_mutex_unlock(&mu);
 if(!injected){free(storage);return infos;}
 batch->storage=storage;batch->injected=injected;batch->info=storage;return batch->info;
}
void tl_pf_release(tl_pf_batch *batch){free(batch->storage);*batch=(tl_pf_batch){0};}
void tl_pf_snapshot(tl_pf_stats *out){pthread_mutex_lock(&mu);*out=stats;out->requested=atomic_load(&requested);out->active=atomic_load(&active);pthread_mutex_unlock(&mu);}
