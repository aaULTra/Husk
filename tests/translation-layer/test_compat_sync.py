#!/usr/bin/env python3
"""Actual Bionic once/futex bodies: publication, real waiters, masks and deadlines."""
import ctypes,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class CompatSyncTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup);p=Path(cls.temp.name)
  io=(ROOT/'src/translation-layer-next/husk-tl-bionic-io.c').read_text();futex=io[io.index('#define FUT_BUCKETS'):io.index('static long linux_syscall_impl(',io.index('#define FUT_BUCKETS'))]
  thread=(ROOT/'src/translation-layer-next/husk-tl-bionic-pthread.c').read_text();once=thread[thread.index('static int b_once('):thread.index("/* bionic's pthread_key_t")]
  source=r'''
#define _GNU_SOURCE
#define _DARWIN_C_SOURCE
#include "husk-tl-component-scope.h"
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>
#include <errno.h>
#include <sched.h>
#include <time.h>
#include <unistd.h>
#include "husk-tl-efficiency.h"
static bool fake_time;static int waits;static int64_t fake_ns,remaining[8];
void tl_em_sync_event(unsigned kind){(void)kind;}
void tl_log_line(const char*format,...){(void)format;}
static int tl_errno_to_guest(int value){return value;}
static int clock_read(clockid_t clock,struct timespec*out){if(!fake_time)return clock_gettime(clock,out);out->tv_sec=fake_ns/1000000000;out->tv_nsec=fake_ns%1000000000;return 0;}
static int relative_wait(pthread_cond_t*cv,pthread_mutex_t*mu,const struct timespec*rel){
 if(fake_time){int64_t n=(int64_t)rel->tv_sec*1000000000+rel->tv_nsec;remaining[waits++]=n;fake_ns+=waits==1?10000000:n;return waits==1?0:ETIMEDOUT;}
 struct timespec abs;clock_gettime(CLOCK_REALTIME,&abs);abs.tv_sec+=rel->tv_sec;abs.tv_nsec+=rel->tv_nsec;if(abs.tv_nsec>=1000000000){abs.tv_sec++;abs.tv_nsec-=1000000000;}return pthread_cond_timedwait(cv,mu,&abs);
}
#define clock_gettime clock_read
#define pthread_cond_timedwait_relative_np relative_wait
'''+futex+once+r'''
int deadline_case(int absolute){
 fake_time=true;waits=0;fake_ns=10000000000LL;uint32_t word=7;
 struct timespec t={absolute?10:0,50000000};long r=futex_call(&word,absolute?9:0,7,&t,UINT32_MAX);fake_time=false;
 return r==-110&&waits==2&&remaining[0]==50000000&&remaining[1]==40000000?0:1;
}
int invalid_case(void){
 uint32_t word=7;struct timespec bad={0,1000000000},past={0,1};
 if(futex_call(NULL,0,7,NULL,0)!=-14||futex_call((void*)((char*)&word+1),0,7,NULL,0)!=-22)return 1;
 if(futex_call(&word,9,7,NULL,0)!=-22||futex_call(&word,10,1,NULL,0)!=-22)return 2;
 if(futex_call(&word,1,UINT32_MAX,NULL,0)!=-22||futex_call(&word,0,7,&bad,0)!=-22)return 3;
 if(futex_call(&word,0,8,&past,0)!=-11||futex_call(&word,9,7,&past,UINT32_MAX)!=-110)return 4;
 return 0;
}
typedef struct{uint32_t*word;uint32_t mask;long result;} request;
static void *waiter(void *raw){request*r=raw;struct timespec abs;clock_gettime(CLOCK_MONOTONIC,&abs);abs.tv_sec+=2;r->result=futex_call(r->word,9,7,&abs,r->mask);return NULL;}
int real_waiters(void){
 uint32_t words[257]={0};words[0]=words[256]=7;request requests[]={{words,1,-999},{words,2,-999},{words+256,1,-999}};pthread_t threads[3];
 for(unsigned i=0;i<3;i++)if(pthread_create(&threads[i],NULL,waiter,&requests[i]))return 1;
 size_t h=((uintptr_t)words>>2)%FUT_BUCKETS;bool queued=false;
 for(unsigned n=0;n<10000;n++){pthread_mutex_lock(&g_fut[h].m);unsigned length=0;for(fut_waiter*w=g_fut[h].head;w;w=w->next)length++;pthread_mutex_unlock(&g_fut[h].m);if(length==3){queued=true;break;}usleep(100);}
 long a=futex_call(words,10,1,NULL,1),b=futex_call(words,10,1,NULL,2),c=futex_call(words+256,1,1,NULL,0);
 for(unsigned i=0;i<3;i++)pthread_join(threads[i],NULL);
 return queued&&a==1&&b==1&&c==1&&!requests[0].result&&!requests[1].result&&!requests[2].result?0:2;
}
static _Atomic int once_word,init_count;static int initialized_value;
static void initializer(void){atomic_fetch_add(&init_count,1);usleep(10000);initialized_value=12345;}
static void *once_waiter(void*raw){(void)raw;b_once(&once_word,initializer);return(void*)(uintptr_t)(initialized_value!=12345);}
int once_case(void){
 atomic_store(&once_word,0);atomic_store(&init_count,0);initialized_value=0;pthread_t threads[12];
 for(unsigned i=0;i<12;i++)if(pthread_create(&threads[i],NULL,once_waiter,NULL))return 1;
 for(unsigned i=0;i<12;i++){void*result;pthread_join(threads[i],&result);if(result)return 2;}
 for(unsigned i=0;i<10000;i++)b_once(&once_word,initializer);
 return atomic_load(&init_count)==1&&atomic_load(&once_word)==1?0:3;
}
'''
  (p/'test.c').write_text(source);subprocess.run([os.environ.get('CC','cc'),'-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC','-pthread','-I',str(ROOT/'src/translation-layer-next'),str(p/'test.c'),str(ROOT/'src/translation-layer-next/husk-tl-component-profile.c'),'-o',str(p/'test.so')],check=True);cls.lib=ctypes.CDLL(str(p/'test.so'))
 def test_spurious_wake_preserves_relative_deadline(self):self.assertEqual(self.lib.deadline_case(0),0)
 def test_spurious_wake_preserves_absolute_monotonic_deadline(self):self.assertEqual(self.lib.deadline_case(1),0)
 def test_validation_and_value_mismatch_before_expired_deadline(self):self.assertEqual(self.lib.invalid_case(),0)
 def test_actual_waiters_filter_bits_and_colliding_addresses(self):self.assertEqual(self.lib.real_waiters(),0)
 def test_once_initializes_once_and_publishes_to_all_waiters(self):self.assertEqual(self.lib.once_case(),0)
if __name__=='__main__':unittest.main()
