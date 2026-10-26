#!/usr/bin/env python3
"""Actual bounded presentation adapter: immutable chains, clock directions and history."""
from pathlib import Path
import ctypes,os,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class PresentClockTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup);p=Path(cls.temp.name)
  source=r'''
#define _GNU_SOURCE
#define _DARWIN_C_SOURCE
#include "husk-tl-present-clock.c"
#include <sys/mman.h>
#include <unistd.h>
static tl_pt_clock clock_pair={5000000000000ULL,1000000000000ULL,100};
int immutable_case(int mode){
 long bytes=sysconf(_SC_PAGESIZE);void*memory=mmap(NULL,(size_t)bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(memory==MAP_FAILED)return 1;
 struct frame{tl_pt_info info;tl_pt_times prefix,time;tl_pt_base tail;tl_pt_time value;}*f=memory;
 memset(f,0,sizeof(*f));int output=0;uint64_t swaps=77,wait=88;uint32_t index=2;
 f->value=(tl_pt_time){123,clock_pair.guest_ns+16666667};f->tail=(tl_pt_base){999,NULL};
 f->time=(tl_pt_times){1000092000,&f->tail,1,&f->value};f->prefix=(tl_pt_times){1000084000,&f->time,1,(void*)17};
 f->info=(tl_pt_info){1000001001,&f->prefix,1,&wait,1,&swaps,&index,&output};struct frame original=*f;
 if(mprotect(memory,(size_t)bytes,PROT_READ))return 2;
 husk_ue4_set_clock_presentation(mode);tl_pt_copy copy;const void*forward;
 bool ok=tl_pt_prepare(&f->info,&copy,clock_pair,&forward);
 if(!ok||forward==&f->info)return 3;
 const tl_pt_info*info=forward;const tl_pt_times*prefix=info->next,*timing=prefix->next;
 if(prefix->times!=(void*)17||timing->next!=&f->tail||timing->times[0].id!=123||timing->times[0].time!=(mode?clock_pair.media_ns+16666667:0))return 4;
 if(info->swaps!=&swaps||info->indices!=&index||info->waits!=&wait||info->results!=&output)return 5;
 info->results[0]=456;if(output!=456||memcmp(f,&original,sizeof(*f)))return 6;
 munmap(memory,(size_t)bytes);return 0;
}
int boundary_case(int which){
 tl_pt_monitor(true);husk_ue4_set_clock_presentation(true);tl_pt_clock c=clock_pair;
 tl_pt_time value={7,c.guest_ns+50000000};tl_pt_times times={1000092000,NULL,1,&value};tl_pt_info info={.next=&times,.count=1};tl_pt_copy copy;const void*forward;
 if(which==1)value.time=c.guest_ns;
 if(which==2)value.time=c.guest_ns+50000001;
 if(which==3)c.uncertainty_ns=1000001;
 if(!tl_pt_prepare(&info,&copy,c,&forward))return 1;
 const tl_pt_times*out=((const tl_pt_info*)forward)->next;tl_pt_stats stats;tl_pt_snapshot(&stats);
 if(which==0)return out->times[0].time==c.media_ns+50000000&&stats.mapped==1?0:2;
 if(out->times[0].time)return 3;
 return which==1?stats.expired!=1:which==2?stats.far_future!=1:stats.invalid_clock!=1;
}
int unsupported_case(int which){
 husk_ue4_set_clock_presentation(true);tl_pt_time value={7,clock_pair.guest_ns+1};tl_pt_times times={1000092000,NULL,1,&value};tl_pt_base unknown={999,&times};tl_pt_info info={.next=&times,.count=1};
 if(which==0)info.next=&unknown;
 if(which==1)times.next=&times;
 if(which==2){times.count=9;info.count=9;}
 if(which==3)times.count=2;
 if(which==4)times.times=NULL;
 tl_pt_copy copy;const void*forward;return !tl_pt_prepare(&info,&copy,clock_pair,&forward)&&value.time==clock_pair.guest_ns+1?0:1;
}
int feedback_case(int mode){
 tl_pt_monitor(true);husk_ue4_set_clock_presentation(mode);tl_pt_past row={7,1000000000001,1000000000002,1000000000000,123};tl_pt_past original=row;
 tl_pt_feedback(&row,1,clock_pair);tl_pt_record record;tl_pt_stats s;tl_pt_snapshot(&s);
 if(tl_pt_records(&record,1)!=1||record.raw_actual!=original.actual||record.guest_actual!=5000000000002||record.observed_guest_ns!=clock_pair.guest_ns)return 1;
 if(row.margin!=123||row.id!=7||row.actual!=(mode?5000000000002:original.actual))return 2;
 return s.feedback_records==1?0:3;
}
int bounded_case(void){
 tl_pt_monitor(true);husk_ue4_set_clock_presentation(false);tl_pt_past row={7,0,clock_pair.media_ns,clock_pair.media_ns,0};
 for(unsigned i=0;i<300;i++)tl_pt_feedback(&row,1,clock_pair);
 tl_pt_record rows[256];tl_pt_stats s;tl_pt_snapshot(&s);
 if(tl_pt_records(rows,256)!=256||rows[0].sequence!=45||rows[255].sequence!=300||s.record_overwrites!=44)return 1;
 pthread_mutex_lock(&history_mu);tl_pt_feedback(&row,1,clock_pair);pthread_mutex_unlock(&history_mu);tl_pt_snapshot(&s);
 if(s.record_contention!=1)return 2;
 tl_pt_monitor(false);tl_pt_feedback(&row,1,clock_pair);tl_pt_snapshot(&s);
 return s.feedback_records==301?0:3;
}
int overflow_case(void){
 tl_pt_monitor(true);husk_ue4_set_clock_presentation(true);tl_pt_past row={7,0,UINT64_MAX,1,987};tl_pt_feedback(&row,1,clock_pair);
 if(row.actual||row.margin!=987||row.desired)return 1;
 tl_pt_clock reverse={100,1000,0};row=(tl_pt_past){7,0,1,0,12};tl_pt_feedback(&row,1,reverse);return row.actual||row.margin!=12;
}
'''
  (p/'test.c').write_text(source);subprocess.run([os.environ.get('CC','cc'),'-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC','-pthread','-I',str(ROOT/'src/translation-layer-next'),str(p/'test.c'),'-o',str(p/'test.so')],check=True);cls.lib=ctypes.CDLL(str(p/'test.so'))
 def test_default_keeps_immediate_behavior_without_guest_writes(self):self.assertEqual(self.lib.immutable_case(0),0)
 def test_mapped_mode_preserves_readonly_prefix_tail_ids_and_output_pointers(self):self.assertEqual(self.lib.immutable_case(1),0)
 def test_horizon_expired_and_clock_uncertainty(self):
  for i in range(4):self.assertEqual(self.lib.boundary_case(i),0)
 def test_unknown_prefix_cycles_counts_and_null_times_decline_without_mutation(self):
  for i in range(5):self.assertEqual(self.lib.unsupported_case(i),0)
 def test_feedback_converts_absolute_fields_keeps_durations_and_passively_observes_off(self):
  for mode in [0,1]:self.assertEqual(self.lib.feedback_case(mode),0)
 def test_feedback_history_is_bounded_nonblocking_and_stops_with_session(self):self.assertEqual(self.lib.bounded_case(),0)
 def test_feedback_overflow_and_missing_zero_are_explicit(self):self.assertEqual(self.lib.overflow_case(),0)
if __name__=='__main__':unittest.main()
