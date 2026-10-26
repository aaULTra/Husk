/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "husk-tl-present-clock.h"
#include <stdatomic.h>
#include <stddef.h>
#include <string.h>
#include <pthread.h>
#define TIMES 1000092000u
_Static_assert(sizeof(tl_pt_info)==64&&offsetof(tl_pt_info,next)==8&&offsetof(tl_pt_info,count)==32,"VkPresentInfoKHR LP64 ABI");
_Static_assert(sizeof(tl_pt_times)==32&&sizeof(tl_pt_time)==16&&sizeof(tl_pt_past)==40,"VK_GOOGLE_display_timing LP64 ABI");
static atomic_bool requested,monitoring,feedback_only;
enum{PRESENTS,REQUESTS,MAPPED,EXPIRED,FUTURE,CLOCK_BAD,UNSUPPORTED,FEEDBACK_CALLS,FEEDBACK_ROWS,OVERWRITES,CONTENTION,COUNTERS};
static atomic_uint_fast64_t counters[COUNTERS];
static atomic_int_fast64_t latest_offset;
static atomic_uint_fast64_t latest_uncertainty;
static pthread_mutex_t history_mu=PTHREAD_MUTEX_INITIALIZER;
static tl_pt_record history[256];static uint32_t head,length;static uint64_t sequence;
static void note(unsigned kind,uint64_t n){if(atomic_load_explicit(&monitoring,memory_order_relaxed))atomic_fetch_add_explicit(&counters[kind],n,memory_order_relaxed);}
void husk_ue4_set_clock_presentation(bool value){atomic_store(&requested,value);}
void husk_ue4_set_feedback_clock(bool value){atomic_store(&feedback_only,value);}
bool tl_pt_feedback_requested(void){return atomic_load(&requested)||atomic_load(&feedback_only);}
bool tl_pt_requested(void){return atomic_load_explicit(&requested,memory_order_relaxed);}
bool tl_pt_monitoring(void){return atomic_load_explicit(&monitoring,memory_order_relaxed);}
bool tl_pt_clock_valid(tl_pt_clock c){return c.guest_ns>0&&c.media_ns>0&&c.guest_ns<INT64_MAX&&c.media_ns<INT64_MAX&&c.uncertainty_ns<=1000000;}
void tl_pt_monitor(bool value){
 atomic_store(&monitoring,false);
 if(value){pthread_mutex_lock(&history_mu);head=length=0;sequence=0;memset(history,0,sizeof(history));pthread_mutex_unlock(&history_mu);
  for(unsigned i=0;i<COUNTERS;i++){atomic_store(&counters[i],0);}
  atomic_store(&latest_offset,0);atomic_store(&latest_uncertainty,0);}
 atomic_store(&monitoring,value);
}
static void observe_clock(tl_pt_clock c){
 if(!atomic_load_explicit(&monitoring,memory_order_relaxed))return;
 atomic_store(&latest_uncertainty,c.uncertainty_ns);
 if(tl_pt_clock_valid(c))atomic_store(&latest_offset,(int64_t)c.guest_ns-(int64_t)c.media_ns);
}
/* Sizes of supported Vulkan-Headers v1.4.321 present-chain prefixes. Tail is
 * borrowed unchanged once the unique timing node is reached. Never guess. */
static unsigned node_size(uint32_t type){
 switch(type){
 case TIMES:case 1000084000u:case 1000294000u:case 1000479001u:case 1000275001u:case 1000275003u:return 32;
 case 1000060011u:return 40;
 case 1000003000u:return 56;
 default:return 0;
 }
}
bool tl_pt_prepare(const void *raw,tl_pt_copy *copy,tl_pt_clock c,const void **output){
 if(!raw||!copy||!output)return false;
 *output=raw;note(PRESENTS,1);
 const tl_pt_info *info=raw;const tl_pt_base *nodes[16],*at=info->next;unsigned count=0,timing=16;
 while(at){
  if(count==16){note(UNSUPPORTED,1);return false;}
  for(unsigned i=0;i<count;i++)if(nodes[i]==at){note(UNSUPPORTED,1);return false;}
  nodes[count]=at;
  if(at->type==TIMES){if(timing!=16){note(UNSUPPORTED,1);return false;}timing=count;}
  count++;at=at->next;
 }
 if(timing==16)return true;
 const tl_pt_times *source=(const tl_pt_times *)nodes[timing];
 if(source->count>8||source->count!=info->count||(source->count&&!source->times)){note(UNSUPPORTED,1);return false;}
 for(unsigned i=0;i<=timing;i++)if(!node_size(nodes[i]->type)){note(UNSUPPORTED,1);return false;}
 copy->info=*info;copy->info.next=&copy->nodes[0];
 for(unsigned i=0;i<=timing;i++){
  memcpy(copy->nodes[i].bytes,nodes[i],node_size(nodes[i]->type));
  const void *next=i<timing?(const void *)&copy->nodes[i+1]:nodes[i]->next;
  memcpy(copy->nodes[i].bytes+8,&next,sizeof(next));
 }
 tl_pt_times *times=(tl_pt_times *)copy->nodes[timing].bytes;times->times=copy->times;
 bool enabled=tl_pt_requested(),valid=tl_pt_clock_valid(c);if(enabled)observe_clock(c);
 for(unsigned i=0;i<source->count;i++){
  copy->times[i]=source->times[i];uint64_t want=copy->times[i].time;copy->times[i].time=0;
  if(!want)continue;
  note(REQUESTS,1);
  if(!enabled)continue; /* Existing immediate presentation, without guest writes. */
  if(!valid){note(CLOCK_BAD,1);continue;}
  if(want<=c.guest_ns){note(EXPIRED,1);continue;}
  uint64_t delay=want-c.guest_ns;
  if(delay>50000000ULL){note(FUTURE,1);continue;}
  if(c.media_ns>UINT64_MAX-delay){note(CLOCK_BAD,1);continue;}
  copy->times[i].time=c.media_ns+delay;note(MAPPED,1);
 }
 *output=&copy->info;return true;
}
static uint64_t to_guest(uint64_t value,tl_pt_clock c){
 if(!value)return 0;
 if(c.guest_ns>=c.media_ns){uint64_t d=c.guest_ns-c.media_ns;if(value>UINT64_MAX-d){note(CLOCK_BAD,1);return 0;}return value+d;}
 uint64_t d=c.media_ns-c.guest_ns;if(value<d){note(CLOCK_BAD,1);return 0;}return value-d;
}
void tl_pt_feedback(tl_pt_past *rows,uint32_t count,tl_pt_clock c){
 note(FEEDBACK_CALLS,1);observe_clock(c);
 bool valid=tl_pt_clock_valid(c),convert=tl_pt_feedback_requested();
 if(!valid){note(CLOCK_BAD,1);return;}
 if(!rows)return;
 for(unsigned i=0;i<count;i++){
  tl_pt_past original=rows[i],mapped=original;
  mapped.desired=to_guest(original.desired,c);mapped.actual=to_guest(original.actual,c);mapped.earliest=to_guest(original.earliest,c);
  if(convert)rows[i]=mapped; /* IDs and duration margin are unchanged. */
  note(FEEDBACK_ROWS,1);
  if(!atomic_load_explicit(&monitoring,memory_order_relaxed))continue;
  if(pthread_mutex_trylock(&history_mu)){note(CONTENTION,1);continue;}
  if(length==256){head=(head+1)%256;length--;note(OVERWRITES,1);}
  history[(head+length++)%256]=(tl_pt_record){++sequence,original.actual,mapped.actual,mapped.desired,mapped.earliest,mapped.margin,c.guest_ns,c.media_ns,c.uncertainty_ns,original.id};
  pthread_mutex_unlock(&history_mu);
 }
}
void tl_pt_snapshot(tl_pt_stats *out){
 if(!out)return;
 *out=(tl_pt_stats){.requested=tl_pt_requested(),.feedback_only=atomic_load(&feedback_only),.monitoring=atomic_load(&monitoring),
 .presents=atomic_load(&counters[PRESENTS]),.timing_requests=atomic_load(&counters[REQUESTS]),.mapped=atomic_load(&counters[MAPPED]),
 .expired=atomic_load(&counters[EXPIRED]),.far_future=atomic_load(&counters[FUTURE]),.invalid_clock=atomic_load(&counters[CLOCK_BAD]),
 .unsupported=atomic_load(&counters[UNSUPPORTED]),.feedback_calls=atomic_load(&counters[FEEDBACK_CALLS]),.feedback_records=atomic_load(&counters[FEEDBACK_ROWS]),
 .record_overwrites=atomic_load(&counters[OVERWRITES]),.record_contention=atomic_load(&counters[CONTENTION]),
 .latest_offset_ns=atomic_load(&latest_offset),.latest_uncertainty_ns=atomic_load(&latest_uncertainty)};
}
uint32_t tl_pt_records(tl_pt_record *out,uint32_t capacity){
 if(!out||!capacity)return 0;
 pthread_mutex_lock(&history_mu);uint32_t n=capacity<length?capacity:length;
 for(unsigned i=0;i<n;i++){out[i]=history[(head+i)%256];}
 pthread_mutex_unlock(&history_mu);return n;
}
