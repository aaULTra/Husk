#!/usr/bin/env python3
"""Benchmark actual old/new once bodies; synthetic CPU work, not game/device energy."""
import argparse,hashlib,json,statistics,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PATH='src/translation-layer-next/husk-tl-bionic-pthread.c'
BASE='cb3a380070b5156aa8dd15108fee858963a5c9d1'
def body(source):return source[source.index('static int b_once('):source.index("/* bionic's pthread_key_t")].replace('static int b_once(', 'static __attribute__((noinline)) int b_once(')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate-ref');p.add_argument('--output',type=Path);a=p.parse_args()
 old=subprocess.check_output(['git','show',BASE+':'+PATH],cwd=ROOT,text=True)
 new=subprocess.check_output(['git','show',a.candidate_ref+':'+PATH],cwd=ROOT,text=True)if a.candidate_ref else(ROOT/PATH).read_text()
 prefix='''#define _POSIX_C_SOURCE 200809L
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <sched.h>
#include <time.h>
#include <stdlib.h>
#include <stdio.h>
#include "husk-tl-efficiency.h"
void tl_em_sync_event(unsigned kind){(void)kind;}
'''
 suffix='''
static _Atomic int once=1;static void init(void){}
static void*run(void*p){(void)p;for(unsigned i=0;i<2000000;i++)b_once(&once,init);return NULL;}
static double stamp(clockid_t c){struct timespec t;clock_gettime(c,&t);return t.tv_sec+t.tv_nsec/1e9;}
int main(int argc,char**argv){unsigned n=argc>1?(unsigned)atoi(argv[1]):1;pthread_t threads[4];double cpu=stamp(CLOCK_PROCESS_CPUTIME_ID),wall=stamp(CLOCK_MONOTONIC);
if(n==1)run(NULL);else {for(unsigned i=0;i<n;i++)pthread_create(&threads[i],NULL,run,NULL);for(unsigned i=0;i<n;i++)pthread_join(threads[i],NULL);}
printf("%.9f %.9f\\n",stamp(CLOCK_PROCESS_CPUTIME_ID)-cpu,stamp(CLOCK_MONOTONIC)-wall);return 0;}
'''
 result={'baseline_commit':BASE,'candidate_ref':a.candidate_ref or 'working tree','candidate_file_sha256':hashlib.sha256(new.encode()).hexdigest(),'scope':'Synthetic completed-once calls:2million/thread,1 or4threads,5 repeats,-O2. CPU/wall seconds only; not M4/Dungeons/energy/temperature evidence.','runs':{}}
 with tempfile.TemporaryDirectory()as d:
  for name,source in [('old',old),('new',new)]:
   path=Path(d)/(name+'.c');path.write_text(prefix+body(source)+suffix);binary=Path(d)/name
   subprocess.run(['cc','-std=c11','-O2','-pthread','-I',str(ROOT/'src/translation-layer-next'),str(path),'-o',str(binary)],check=True)
   result['runs'][name]={}
   for threads in [1,4]:
    values=[list(map(float,subprocess.check_output([str(binary),str(threads)],text=True).split()))for _ in range(5)]
    result['runs'][name][str(threads)]={'cpu_wall_seconds':values,'median_cpu_seconds':statistics.median(v[0]for v in values),'median_wall_seconds':statistics.median(v[1]for v in values)}
 text=json.dumps(result,indent=2)+'\n'
 if a.output:a.output.write_text(text)
 else:print(text,end='')
if __name__=='__main__':main()
