#!/usr/bin/env python3
"""Exercise actual bounded driver presentation provenance, aggregate and epochs."""
import subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class NativeDisplayTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);p=Path(cls.tmp.name)
  (p/'HuskDisplayABI.h').write_bytes((ROOT/'src/translation-layer-next/husk-tl-display.h').read_bytes())
  (p/'main.cpp').write_text(r'''
#include <cassert>
#include <cstring>
#include <thread>
#include <vector>
#include "HuskDisplay.inc"
static void start(uint64_t after=1){tl_display_config c={1,sizeof(c),1,0,after};assert(vkHuskDisplayConfigure(&c));}
static void emit(uint64_t time,uint64_t gen=1){huskDisplayObserve(gen,0,0,time,time,1,time+100);}
static tl_display_stats stats(){tl_display_stats s={1,sizeof(s)};assert(vkHuskDisplaySnapshot(&s,nullptr,0)==0);return s;}
int main(int argc,char**argv){assert(argc==2);start();
 if(!strcmp(argv[1],"direct")){emit(1000000000);emit(1016666667);emit(1050000001);auto s=stats();assert(s.direct_events==3&&s.intervals==2&&s.interval_ns==50000001&&s.above20==1&&s.above33==1&&s.histogram[167]==1);}
 else if(!strcmp(argv[1],"estimate")){emit(1000000000);huskDisplayObserve(1,3,0,0,1010000000,1,1010000100);emit(1020000000);auto s=stats();assert(s.direct_events==2&&s.estimated_events==1&&!s.intervals);}
 else if(!strcmp(argv[1],"generation")){emit(1000000000);emit(1010000000,2);emit(1020000000,2);assert(stats().intervals==1);assert(huskDisplayNewGeneration()!=huskDisplayNewGeneration());}
 else if(!strcmp(argv[1],"tail")){for(unsigned i=0;i<1000;i++)emit(1000000000ULL+i*16666667ULL);auto s=stats();assert(s.intervals==999&&s.retained==256&&s.overwrites==744);tl_display_record rows[256];s.version=1;s.size=sizeof(s);assert(vkHuskDisplaySnapshot(&s,rows,256)==256&&rows[0].sequence==745&&rows[255].sequence==1000);}
 else if(!strcmp(argv[1],"excluded")){emit(1000000000);tl_display_config c={1,sizeof(c),1,1,1010000000};assert(vkHuskDisplayConfigure(&c));emit(1020000000);c.excluded=0;c.include_after_media_ns=1030000000;assert(vkHuskDisplayConfigure(&c));emit(1025000000);emit(1040000000);emit(1050000000);auto s=stats();assert(s.intervals==1&&s.direct_events==3&&s.boundary_events==1);}
 else if(!strcmp(argv[1],"drop")){emit(1000000000);{std::lock_guard<std::mutex> lock(huskDisplayLock);emit(1010000000);}emit(1020000000);emit(1030000000);auto s=stats();assert(s.contention_drops==1&&s.intervals==1);}
 else if(!strcmp(argv[1],"invalid")){emit(1000000000);emit(999000000);emit(1010000000);emit(1020000000);auto s=stats();assert(s.invalid_events==1&&s.intervals==1);huskDisplayObserve(1,1,0,2000000000,2000000000,1,1000000000);assert(stats().boundary_events==1);}
 else if(!strcmp(argv[1],"stop")){emit(1000000000);tl_display_config c={1,sizeof(c),0,0,1};assert(vkHuskDisplayConfigure(&c));emit(1010000000);assert(stats().direct_events==1);start();assert(stats().direct_events==0&&stats().attempts==0);}
 else if(!strcmp(argv[1],"abi")){tl_display_config c={2,sizeof(c),1,0,1};assert(!vkHuskDisplayConfigure(&c));c.version=1;c.enabled=2;assert(!vkHuskDisplayConfigure(&c));tl_display_stats s={1,sizeof(s)};assert(vkHuskDisplaySnapshot(&s,nullptr,1)==-1);s.version=2;assert(vkHuskDisplaySnapshot(&s,nullptr,0)==-1);}
 else if(!strcmp(argv[1],"overflow")){emit(1000000000);emit(1600000000);auto s=stats();assert(s.histogram[511]==1&&s.worst_interval_ns==600000000&&s.above50==1);}
 else if(!strcmp(argv[1],"concurrency")){std::vector<std::thread> threads;for(unsigned i=0;i<8;i++)threads.emplace_back([]{for(unsigned j=0;j<500;j++)emit(1000000000ULL+j*1000000ULL);});for(auto &t:threads)t.join();auto s=stats();uint64_t n=0;for(auto b:s.histogram)n+=b;assert(s.attempts==4000&&s.direct_events+s.contention_drops==4000&&s.intervals==n&&s.retained<=256);}
 else assert(false);
}
''')
  cls.exe=p/'check';subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-Wno-missing-field-initializers','-pthread','-I',str(p),'-I',str(ROOT/'patches/metalfx'),str(p/'main.cpp'),'-o',str(cls.exe)],check=True)
 def case(self,name):subprocess.run([str(self.exe),name],check=True,timeout=10)
 def test_only_direct_times_enter_consecutive_interval_histogram(self):self.case('direct')
 def test_estimate_is_separate_and_breaks_interval_continuity(self):self.case('estimate')
 def test_swapchain_generation_breaks_continuity_and_never_reuses_identity(self):self.case('generation')
 def test_full_aggregate_survives_bounded_raw_tail_overwrite(self):self.case('tail')
 def test_exclusion_and_late_preinclusion_callback_are_not_gameplay(self):self.case('excluded')
 def test_nonblocking_lock_loss_breaks_continuity(self):self.case('drop')
 def test_out_of_order_and_future_times_cannot_fabricate_intervals(self):self.case('invalid')
 def test_disabled_capture_does_no_work_and_new_session_resets(self):self.case('stop')
 def test_abi_and_null_capacity_are_checked(self):self.case('abi')
 def test_long_hitch_has_truthful_overflow_bucket_and_exact_maximum(self):self.case('overflow')
 def test_concurrent_callbacks_keep_bounded_consistent_counters(self):self.case('concurrency')
 def test_actual_host_adapter_late_driver_availability_and_exclusion_forwarding(self):
  source=(ROOT/'src/translation-layer-next/husk-tl-display.m').read_text().replace('#import <QuartzCore/QuartzCore.h>','')
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory);(p/'main.c').write_text(r'''
#include "husk-tl-display.h"
#include <dlfcn.h>
#include <assert.h>
#include <string.h>
static tl_display_config last;static unsigned calls;static int bad;
static double CACurrentMediaTime(void){return 12.5;}
static int configure(const tl_display_config *c){last=*c;calls++;return 1;}
static int snapshot(tl_display_stats*s,tl_display_record*r,uint32_t cap){(void)r;if(cap)return bad?99:0;s->enabled=last.enabled;return 0;}
static void *fake_dlsym(void *library,const char*name){assert(library==(void*)1);return !strcmp(name,"vkHuskDisplayConfigure")?(void*)configure:!strcmp(name,"vkHuskDisplaySnapshot")?(void*)snapshot:0;}
#define dlsym fake_dlsym
'''+source+r'''
int main(void){tl_display_stats s;uint32_t copied=77;tl_display_record rows[1];
 tl_vk_display_monitor(true);assert(!tl_vk_display_snapshot(&s,NULL,0,&copied)&&copied==0&&!calls);
 tl_vk_display_driver((void*)1);assert(last.enabled&&last.excluded&&last.include_after_media_ns==12500000000ULL);
 tl_vk_display_exclude(false);assert(!last.excluded);unsigned previous=calls;tl_vk_display_exclude(false);assert(calls==previous);
 assert(tl_vk_display_snapshot(&s,NULL,0,&copied)&&!copied&&s.enabled);bad=1;assert(!tl_vk_display_snapshot(&s,rows,1,&copied)&&!copied);
 tl_vk_display_monitor(false);assert(!last.enabled);tl_vk_display_driver(NULL);assert(!tl_vk_display_snapshot(&s,NULL,0,&copied));return 0;
}
''')
   exe=p/'check';subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-pthread','-I',str(ROOT/'src/translation-layer-next'),str(p/'main.c'),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
