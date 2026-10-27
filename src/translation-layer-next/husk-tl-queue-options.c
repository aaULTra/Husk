/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#include "husk-tl-queue-options.h"
#include <errno.h>
#include <pthread.h>
#include <stdlib.h>
#include <stdio.h>
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static tl_queue_options_stats state={.requested_prefill=-1,.query_result=-1};
void husk_ue4_set_queue_options(int prefill,int limit){
 pthread_mutex_lock(&lock);
 if(!state.applied){state.requested_prefill=prefill>=0&&prefill<=2?prefill:-1;
 state.requested_limit=(limit==8||limit==16||limit==32||limit==64)?(uint32_t)limit:0;}
 pthread_mutex_unlock(&lock);
}
void tl_queue_options_environment(void){
 pthread_mutex_lock(&lock);
 if(!state.applied){
  if(state.requested_prefill>=0){char value[12];snprintf(value,sizeof(value),"%d",state.requested_prefill);if(setenv("MVK_CONFIG_PREFILL_METAL_COMMAND_BUFFERS",value,1))state.environment_error=errno;}
  if(state.requested_limit){char value[12];snprintf(value,sizeof(value),"%u",state.requested_limit);if(setenv("MVK_CONFIG_MAX_ACTIVE_METAL_COMMAND_BUFFERS_PER_QUEUE",value,1))state.environment_error=errno;}
  state.applied=true;
 }
 pthread_mutex_unlock(&lock);
}
void tl_queue_options_observe(int result,const uint32_t *prefix,uint32_t bytes){
 pthread_mutex_lock(&lock);state.query_result=result;state.observed=false;
 if((result==0||result==5)&&prefix&&bytes>=20){state.actual_synchronous=prefix[2];state.actual_prefill=prefix[3];state.actual_limit=prefix[4];state.observed=true;}
 pthread_mutex_unlock(&lock);
}
void tl_queue_options_snapshot(tl_queue_options_stats *out){if(!out)return;pthread_mutex_lock(&lock);*out=state;pthread_mutex_unlock(&lock);}
