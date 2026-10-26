/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "husk-tl-native-archive.h"
#include <pthread.h>
#include <stdatomic.h>
#include <string.h>
static atomic_int requested_mode;
static atomic_bool verify_requested;
static atomic_int preparation_phase; /*0 idle,1 reserved on UI thread,2 executing*/
static bool configured;
static tl_npa_api api;
static void *first_device;
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
void tl_log_line(const char *format,...);
void husk_ue4_set_native_archive(int mode){atomic_store(&requested_mode,mode==2?2:mode==1?1:0);}
void husk_ue4_set_native_archive_verification(bool enabled){atomic_store(&verify_requested,enabled);}
bool tl_npa_requested(void){return atomic_load(&requested_mode)==2;}
void tl_npa_set_api(tl_npa_api value){pthread_mutex_lock(&lock);api=value;pthread_mutex_unlock(&lock);}
void tl_npa_configure(const char *project,const char *directory,bool sharp){
 if(!tl_npa_requested()||!sharp||!project||strcmp(project,"Dungeons"))return;
 pthread_mutex_lock(&lock);
 tl_na_config c={TL_NATIVE_ARCHIVE_ABI,sizeof(c),1,atomic_load(&verify_requested)?TL_NA_VERIFY_REQUIREMENT:0,directory};
 configured=api.configure&&api.snapshot&&api.prepare&&api.forget&&api.configure(&c);
 pthread_mutex_unlock(&lock);
 tl_log_line("[M2/M5 native-archive] requested; driver ABI %s; native support checked on first pipeline; no guaranteed cache hits/first-use elimination or energy benefit",configured?"accepted":"unavailable");
}
void tl_npa_device(void *device){if(!device)return;pthread_mutex_lock(&lock);if(configured&&!first_device)first_device=device;pthread_mutex_unlock(&lock);}
void tl_npa_forget(void *device){
 pthread_mutex_lock(&lock);
 if(device&&device==first_device){configured=false;first_device=NULL;if(api.forget)api.forget();int reserved=1;atomic_compare_exchange_strong(&preparation_phase,&reserved,0);}
 pthread_mutex_unlock(&lock);
}
void tl_vk_archive_snapshot(tl_na_stats *out){
 if(!out)return;
 *out=(tl_na_stats){.version=TL_NATIVE_ARCHIVE_ABI,.size=sizeof(*out),.requested=tl_npa_requested()};
 pthread_mutex_lock(&lock);
 if(configured&&api.snapshot&&!api.snapshot(out))*out=(tl_na_stats){.version=TL_NATIVE_ARCHIVE_ABI,.size=sizeof(*out),.requested=1};
 pthread_mutex_unlock(&lock);
 out->preparing|=(atomic_load(&preparation_phase)!=0);
}
bool tl_vk_archive_begin_prepare(void){
 pthread_mutex_lock(&lock);tl_na_stats s={.version=TL_NATIVE_ARCHIVE_ABI,.size=sizeof(s)};
 bool valid=configured&&api.snapshot&&api.snapshot(&s)&&s.supported&&s.pending;
 int expected=0;
 valid=valid&&atomic_compare_exchange_strong(&preparation_phase,&expected,1);
 pthread_mutex_unlock(&lock);return valid;
}
bool tl_vk_archive_preparing(void){return (atomic_load(&preparation_phase)!=0);}
int tl_vk_archive_prepare(void){
 int expected=1;if(!atomic_compare_exchange_strong(&preparation_phase,&expected,2))return 0;
 pthread_mutex_lock(&lock);int(*prepare)(void)=configured?api.prepare:NULL;pthread_mutex_unlock(&lock);
 int result=prepare?prepare():-1;
 atomic_store(&preparation_phase,0);
 tl_log_line("[M2/M5 native-archive] explicit paused preparation finished result %d; include its CPU/time/energy in comparisons",result);
 return result;
}
