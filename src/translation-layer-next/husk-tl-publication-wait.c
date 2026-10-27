/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#include "husk-tl-publication-wait.h"
#include <pthread.h>
#include <stdatomic.h>
#include <time.h>
#define BUCKETS 64
static struct {pthread_mutex_t mutex;pthread_cond_t condition;} buckets[BUCKETS];
static pthread_once_t initialized=PTHREAD_ONCE_INIT;
static bool available;
static atomic_bool requested,ever_enabled;
static atomic_uint_fast64_t waits,wakeups,fallbacks;
static void initialize(void){
 unsigned n=0;
 for(;n<BUCKETS;n++){
  if(pthread_mutex_init(&buckets[n].mutex,NULL))break;
  if(pthread_cond_init(&buckets[n].condition,NULL)){pthread_mutex_destroy(&buckets[n].mutex);break;}
 }
 available=n==BUCKETS;
 if(!available)while(n){--n;pthread_cond_destroy(&buckets[n].condition);pthread_mutex_destroy(&buckets[n].mutex);}
}
static unsigned index_for(const void *address){uintptr_t n=(uintptr_t)address>>2;return (unsigned)(n^(n>>11))&(BUCKETS-1);}
void husk_ue4_set_initialization_parking(bool value){if(value)atomic_store(&ever_enabled,true);atomic_store(&requested,value);}
bool tl_publication_parking(void){return atomic_load_explicit(&requested,memory_order_relaxed);}
static void unlock(void *mutex){pthread_mutex_unlock(mutex);}
static void sleep_until_ready(const void *address,bool (*pending)(const void *),bool counted){
 bool fallback_counted=false;
 while(pending(address)){
  if(!counted){atomic_fetch_add_explicit(&waits,1,memory_order_relaxed);counted=true;}
  if(!fallback_counted){atomic_fetch_add_explicit(&fallbacks,1,memory_order_relaxed);fallback_counted=true;}
  struct timespec delay={0,100000};nanosleep(&delay,NULL);
 }
}
void tl_publication_wait(const void *address,bool (*pending)(const void *)){
 if(!address||!pending||!pending(address))return;
 pthread_once(&initialized,initialize);
 if(!available){sleep_until_ready(address,pending,false);return;}
 unsigned i=index_for(address);pthread_mutex_lock(&buckets[i].mutex);
 /* Recheck under the same mutex used by notification: no lost publication.
  * Hash collisions only cause harmless predicate rechecks. No callback holds
  * this mutex while running an initializer, allowing nested initialization. */
 bool failed=false,counted=false;
 pthread_cleanup_push(unlock,&buckets[i].mutex);
 while(pending(address)){
  if(!counted){atomic_fetch_add_explicit(&waits,1,memory_order_relaxed);counted=true;}
  if(pthread_cond_wait(&buckets[i].condition,&buckets[i].mutex)){failed=true;break;}
 }
 pthread_cleanup_pop(1);
 if(failed)sleep_until_ready(address,pending,counted);
}
void tl_publication_notify(const void *address){
 if(!address||!atomic_load_explicit(&ever_enabled,memory_order_relaxed))return;
 pthread_once(&initialized,initialize);if(!available)return;
 unsigned i=index_for(address);pthread_mutex_lock(&buckets[i].mutex);
 pthread_cond_broadcast(&buckets[i].condition);
 atomic_fetch_add_explicit(&wakeups,1,memory_order_relaxed);pthread_mutex_unlock(&buckets[i].mutex);
}
void tl_publication_snapshot(tl_publication_stats *out){if(out)*out=(tl_publication_stats){atomic_load(&requested),atomic_load(&waits),atomic_load(&wakeups),atomic_load(&fallbacks)};}
