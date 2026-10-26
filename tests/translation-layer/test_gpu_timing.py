#!/usr/bin/env python3
"""Exercise sampled GPU collector with delayed/out-of-order/error completions."""
import ctypes, os, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class GPUTimingTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup)
  p=Path(cls.tmp.name)
  (p/'test.c').write_text(r'''
#include "husk-tl-gpu-timing.c"
int exercise(int mode){
 tl_gput_ticket a,b;tl_gput_record record;tl_gput_stats out;
 tl_gput_begin(mode!=0,100);tl_gput_exclude(false);
 if(mode==0)return tl_gput_capture(100.2,1,&a);
 if(!tl_gput_capture(100.2,1,&a))return 1;
 if(mode==1){
  if(tl_gput_capture(101,1,&b)||tl_gput_capture(109.9,1,&b))return 2;
  if(!tl_gput_capture(110.1,2,&b)||b.begin!=110||b.end!=111)return 3;
  tl_gput_complete(b,110.2,110.4,110.5,true);
  tl_gput_complete(a,100.1,100.8,111,true);
  if(!tl_gput_pop(&record)||record.queue!=2||record.gpu_end!=110.4)return 4;
  if(!tl_gput_pop(&record)||record.queue!=1||tl_gput_pop(&record))return 5;
  tl_gput_snapshot(&out);return out.completed==2&&out.pending==0?0:6;
 }
 if(mode==2){
  tl_gput_exclude(true);tl_gput_exclude(false);tl_gput_complete(a,100.1,100.2,100.3,true);
  tl_gput_snapshot(&out);return out.stale==1&&!out.completed?0:1;
 }
 if(mode==3){
  tl_gput_end();tl_gput_begin(true,200);tl_gput_exclude(false);tl_gput_complete(a,100.1,100.2,100.3,true);
  tl_gput_snapshot(&out);return out.pending||out.completed||out.stale||out.dropped;
 }
 if(mode==4){
  tl_gput_complete(a,0,0,100.3,true);tl_gput_capture(100.3,1,&a);tl_gput_complete(a,100.3,100.2,100.4,true);
  tl_gput_capture(100.4,1,&a);tl_gput_complete(a,100.1,100.2,100.3,false);
  tl_gput_capture(100.5,1,&a);tl_gput_complete(a,101.1,101.2,101.3,true);
  tl_gput_capture(100.5,1,&a);tl_gput_complete(a,100.1,101,100.2,true);
  tl_gput_snapshot(&out);return out.invalid==3&&out.errors==1&&out.outside==1&&!out.completed&&!out.pending?0:1;
 }
 if(mode==5){
  for(unsigned i=1;i<256;i++)if(!tl_gput_capture(100.3,1,&b))return 1;
  if(tl_gput_capture(100.4,1,&b))return 2;
  tl_gput_snapshot(&out);return out.attached==256&&out.dropped==1&&out.pending==256?0:3;
 }
 if(mode==6){
  pthread_mutex_lock(&mu);tl_gput_complete(a,100.1,100.2,100.3,true);pthread_mutex_unlock(&mu);
  tl_gput_snapshot(&out);return out.dropped==1&&out.pending==1?0:1;
 }
 if(mode==8){
  for(unsigned w=0;w<5;w++)for(unsigned i=0;i<256;i++){
   tl_gput_ticket t;if(!tl_gput_capture(100+w*10+0.1,1,&t))continue;
   tl_gput_complete(t,100+w*10+0.1,100+w*10+0.2,100+w*10+0.3,true);
  }
  tl_gput_snapshot(&out);return out.completed==1024&&out.dropped>0?0:1;
 }
 if(mode==7){
  tl_gput_end();tl_gput_complete(a,100.1,100.2,100.3,true);tl_gput_snapshot(&out);
  return out.stale==1&&!out.completed&&!tl_gput_capture(100.5,1,&b)?0:1;
 }
 return 999;
}
int exercise_kind(void){
 for(unsigned kind=0;kind<7;kind++){
  tl_gput_begin(true,100);tl_gput_exclude(false);tl_gput_ticket t;tl_gput_record r;
  if(!tl_gput_capture(100.1,1,&t))return 1;
  tl_gput_complete_kind(t,100.1,100.2,100.3,true,kind);
  if(!tl_gput_pop(&r)||r.kind!=(kind<=TL_GPUT_OTHER?kind:TL_GPUT_UNKNOWN))return 2;
 }return 0;
}
''')
  lib=p/'test.so';subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC','-pthread','-I',str(ROOT/'src/translation-layer-next'),str(p/'test.c'),'-lm','-o',str(lib)],check=True)
  cls.lib=ctypes.CDLL(str(lib))
 def test_disabled_does_no_collection(self):self.assertEqual(self.lib.exercise(0),0)
 def test_sample_windows_preserve_out_of_order_completion_and_queue_identity(self):self.assertEqual(self.lib.exercise(1),0)
 def test_exclusion_epoch_rejects_crossing_buffers(self):self.assertEqual(self.lib.exercise(2),0)
 def test_restart_discards_old_session_callbacks(self):self.assertEqual(self.lib.exercise(3),0)
 def test_invalid_error_and_outside_timestamps_are_separate(self):self.assertEqual(self.lib.exercise(4),0)
 def test_sampling_budget_bounds_handler_overhead_and_reports_loss(self):self.assertEqual(self.lib.exercise(5),0)
 def test_completion_never_waits_on_consumer_mutex(self):self.assertEqual(self.lib.exercise(6),0)
 def test_stop_rejects_new_and_late_completions(self):self.assertEqual(self.lib.exercise(7),0)
 def test_record_capacity_is_bounded_and_loss_disclosed(self):self.assertEqual(self.lib.exercise(8),0)
 def test_kind_is_bounded_and_retained_without_expanding_sampling(self):self.assertEqual(self.lib.exercise_kind(),0)
if __name__=='__main__':unittest.main()
