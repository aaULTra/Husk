#!/usr/bin/env python3
"""Actual parked once/object publication: collisions, races, cancellation and CPU bench."""
import json,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];TL=ROOT/'src/translation-layer-next'
def build_harness(directory):
 p=Path(directory);source=(TL/'husk-tl-bionic-pthread.c').read_text()
 objects=source[source.index('#define MAGIC_READY'):source.index('static int rc(')]
 once=source[source.index('static bool once_initializing('):source.index("/* bionic's pthread_key_t")]
 (p/'main.c').write_text(r'''
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sched.h>
#include <string.h>
#include <time.h>
#include "husk-tl-component-scope.h"
#include "husk-tl-efficiency.h"
#include "husk-tl-publication-wait.c"
void tl_em_sync_event(unsigned kind){(void)kind;}
static void pause_ns(long ns){struct timespec t={ns/1000000000L,ns%1000000000L};nanosleep(&t,NULL);}
'''+objects+once+r'''
static _Atomic int once_word,init_count,done;static int result;
static void initializer(void){atomic_fetch_add(&init_count,1);pause_ns(100000000L);result=12345;}
static void *once_worker(void*unused){(void)unused;b_once(&once_word,initializer);assert(result==12345);return NULL;}
static guest_obj object;static int made;
static void *make(uint32_t v){assert(v==123);atomic_fetch_add(&init_count,1);pause_ns(10000000);made=345;return &made;}
static void *object_worker(void*unused){(void)unused;assert(obj_host(&object,make)==&made&&made==345);return NULL;}
static bool pending(const void*word){return atomic_load_explicit((const _Atomic int*)word,memory_order_acquire)==0;}
static void *wait_worker(void*word){tl_publication_wait(word,pending);atomic_fetch_add(&done,1);return NULL;}
static double stamp(clockid_t clock){struct timespec t;clock_gettime(clock,&t);return t.tv_sec+t.tv_nsec/1e9;}
int main(int argc,char**argv){assert(argc==2);husk_ue4_set_initialization_parking(true);pthread_t threads[12];
 if(!strcmp(argv[1],"once")||!strcmp(argv[1],"bench-on")||!strcmp(argv[1],"bench-off")){
  bool bench=strncmp(argv[1],"bench-",6)==0;husk_ue4_set_initialization_parking(strcmp(argv[1],"bench-off")!=0);
  double cpu=stamp(CLOCK_PROCESS_CPUTIME_ID),wall=stamp(CLOCK_MONOTONIC);
  for(unsigned i=0;i<12;i++)assert(!pthread_create(&threads[i],NULL,once_worker,NULL));
  for(unsigned i=0;i<12;i++)pthread_join(threads[i],NULL);
  assert(atomic_load(&init_count)==1&&atomic_load(&once_word)==1);
  tl_publication_stats before,after;tl_publication_snapshot(&before);for(unsigned i=0;i<100000;i++)b_once(&once_word,initializer);tl_publication_snapshot(&after);assert(before.waits==after.waits);
  if(bench)printf("{\"cpu_seconds\":%.9f,\"wall_seconds\":%.9f,\"parked_waits\":%llu}\n",stamp(CLOCK_PROCESS_CPUTIME_ID)-cpu,stamp(CLOCK_MONOTONIC)-wall,(unsigned long long)after.waits);
 }else if(!strcmp(argv[1],"object")){
  object.value=123;for(unsigned i=0;i<12;i++)assert(!pthread_create(&threads[i],NULL,object_worker,NULL));for(unsigned i=0;i<12;i++)pthread_join(threads[i],NULL);
  assert(atomic_load(&init_count)==1&&atomic_load(&object.magic)==MAGIC_READY);
 }else if(!strcmp(argv[1],"races")){
  for(unsigned i=0;i<1000;i++){_Atomic int word=0;assert(!pthread_create(&threads[0],NULL,wait_worker,&word));atomic_store_explicit(&word,1,memory_order_release);tl_publication_notify(&word);pthread_join(threads[0],NULL);}assert(atomic_load(&done)==1000);
 }else if(!strcmp(argv[1],"collisions")){
  _Atomic int words[4096]={0};unsigned b=1;while(b<4096&&index_for(words)!=index_for(words+b))b++;assert(b<4096);
  assert(!pthread_create(&threads[0],NULL,wait_worker,words));assert(!pthread_create(&threads[1],NULL,wait_worker,words+b));
  pause_ns(10000000);tl_publication_notify(words);pause_ns(10000000);assert(!atomic_load(&done));
  atomic_store(words,1);tl_publication_notify(words);pthread_join(threads[0],NULL);assert(atomic_load(&done)==1);
  atomic_store(words+b,1);tl_publication_notify(words+b);pthread_join(threads[1],NULL);assert(atomic_load(&done)==2);
 }else if(!strcmp(argv[1],"cancel")){
  _Atomic int word=0;assert(!pthread_create(&threads[0],NULL,wait_worker,&word));pause_ns(10000000);pthread_cancel(threads[0]);void *cancelled;pthread_join(threads[0],&cancelled);assert(cancelled==PTHREAD_CANCELED);
  atomic_store(&word,1);tl_publication_notify(&word);tl_publication_wait(&word,pending);
 }else if(!strcmp(argv[1],"fallback")){
  pthread_once(&initialized,initialize);available=false;_Atomic int word=0;assert(!pthread_create(&threads[0],NULL,wait_worker,&word));pause_ns(10000000);atomic_store(&word,1);pthread_join(threads[0],NULL);assert(atomic_load(&fallbacks)==1);
 }else if(!strcmp(argv[1],"disable")){
  _Atomic int word=0;assert(!pthread_create(&threads[0],NULL,wait_worker,&word));pause_ns(10000000);husk_ue4_set_initialization_parking(false);atomic_store(&word,1);tl_publication_notify(&word);pthread_join(threads[0],NULL);assert(atomic_load(&done)==1);
 }else assert(0);
 return 0;
}
''')
 binary=p/'check';subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-pthread','-I',str(TL),str(p/'main.c'),str(TL/'husk-tl-component-profile.c'),'-o',str(binary)],check=True);return binary
class PublicationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);cls.exe=build_harness(cls.tmp.name)
 def run_case(self,name):subprocess.run([str(self.exe),name],check=True,timeout=15)
 def test_once_publication_and_completed_fast_path(self):self.run_case('once')
 def test_guest_object_creation_and_memory_publication(self):self.run_case('object')
 def test_publication_before_or_during_wait_has_no_lost_wake(self):self.run_case('races')
 def test_spurious_wake_and_hash_collision_preserve_predicate(self):self.run_case('collisions')
 def test_native_cancelled_waiter_releases_bucket_mutex(self):self.run_case('cancel')
 def test_unavailable_native_wait_uses_sleeping_fallback(self):self.run_case('fallback')
 def test_disable_during_existing_wait_cannot_strand_waiter(self):self.run_case('disable')
if __name__=='__main__':unittest.main()
