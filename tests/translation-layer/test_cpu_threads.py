#!/usr/bin/env python3
"""Actual supported Mach thread snapshots on Apple; no suspended threads or affinity."""
from pathlib import Path
import subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
@unittest.skipUnless(sys.platform=='darwin','Apple Mach APIs required; IPA CI runs this check')
class CPUThreadTests(unittest.TestCase):
 def test_actual_live_thread_identity_cpu_and_bounded_snapshot(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'main.c').write_text(r'''
#include "husk-tl-efficiency.h"
#include <pthread.h>
#include <stdatomic.h>
#include <assert.h>
#include <string.h>
#include <sched.h>
static atomic_bool ready,stop;
static void *worker(void *p){(void)p;pthread_setname_np("HuskCPUCheck");atomic_store(&ready,true);while(!atomic_load(&stop)){}return NULL;}
int main(void){pthread_t thread;assert(!pthread_create(&thread,NULL,worker,NULL));while(!atomic_load(&ready))sched_yield();
 tl_em_process process;tl_em_process_sample(true,&process);assert(process.cpu_seconds>=0&&process.footprint_bytes>=0);if(process.peak_bytes>=0)assert(process.peak_bytes>=process.footprint_bytes);
 tl_em_thread rows[128];tl_em_thread_stats s;unsigned count=tl_em_thread_sample(rows,128,&s);assert(s.result==0&&count>0&&count<=128&&s.enumerated>=count);
 uint64_t identity=0;double before=0;for(unsigned i=0;i<count;i++)if(!strcmp(rows[i].name,"HuskCPUCheck")){identity=rows[i].identity;before=rows[i].user_seconds+rows[i].system_seconds;}
 assert(identity);for(volatile unsigned i=0;i<20000000;i++){}count=tl_em_thread_sample(rows,128,&s);bool found=false;
 for(unsigned i=0;i<count;i++)if(rows[i].identity==identity){assert(rows[i].user_seconds+rows[i].system_seconds>=before);found=true;}assert(found);
 assert(tl_em_thread_sample(rows,1,&s)==1&&s.truncated);assert(tl_em_thread_sample(NULL,0,&s)==0);
 atomic_store(&stop,true);pthread_join(thread,NULL);return 0;}
''')
   tl=ROOT/'src/translation-layer-next';binary=p/'check'
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-pthread','-I',str(tl),str(p/'main.c'),str(tl/'husk-tl-efficiency.c'),'-o',str(binary)],check=True)
   subprocess.run([str(binary)],check=True)
if __name__=='__main__':unittest.main()
