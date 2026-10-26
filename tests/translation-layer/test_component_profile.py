#!/usr/bin/env python3
"""Actual sampled CPU/wall scopes: disabled paths, boundaries, nesting and contention."""
import ctypes,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];TL=ROOT/'src/translation-layer-next'
class ComponentTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);p=Path(cls.tmp.name)
  (p/'check.c').write_text(r'''
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include "husk-tl-component-profile.c"
#include "husk-tl-component-scope.h"
static tl_cp_ticket next(uint32_t k){tl_cp_ticket t;for(unsigned i=0;i<64;i++){t=tl_cp_begin(k);if(t.active)return t;}assert(0);return(tl_cp_ticket){0};}
static int work(unsigned kind,int early){TL_CP_SCOPE(kind);struct timespec wait={0,1000000};nanosleep(&wait,NULL);if(early)return 17;return 23;}
int disabled(void){tl_cp_start(false);tl_cp_exclude(false);for(unsigned i=0;i<130;i++)assert(work(TL_CP_JNI,1)==17);tl_cp_row row[TL_CP_COUNT];tl_cp_stats s;return tl_cp_snapshot(row,TL_CP_COUNT,&s)==0&&!s.requested&&!s.clock_errors;}
int sampled(void){tl_cp_start(true);tl_cp_exclude(false);for(unsigned i=0;i<130;i++)assert(work(TL_CP_SUBMIT,i&1)==(i&1?17:23));tl_cp_row row[TL_CP_COUNT];tl_cp_stats s;unsigned n=tl_cp_snapshot(row,TL_CP_COUNT,&s);return n==1&&row[0].kind==TL_CP_SUBMIT&&row[0].samples>=2&&row[0].samples<=3&&row[0].wall_ns>500000&&row[0].cpu_ns<=row[0].wall_ns+1000000&&s.sample_every==64;}
int crossing(int restart){tl_cp_start(true);tl_cp_exclude(false);tl_cp_ticket t=next(TL_CP_GRAPHICS);if(restart){tl_cp_stop();tl_cp_start(true);tl_cp_exclude(false);}else{tl_cp_exclude(true);tl_cp_exclude(false);}tl_cp_end(t);tl_cp_stats s;tl_cp_row r[TL_CP_COUNT];return tl_cp_snapshot(r,TL_CP_COUNT,&s)==0&&s.boundary_dropped==1;}
int busy(void){tl_cp_start(true);tl_cp_exclude(false);tl_cp_ticket t=next(TL_CP_COMPUTE);pthread_mutex_lock(&mu);tl_cp_end(t);pthread_mutex_unlock(&mu);tl_cp_stats s;tl_cp_row r[TL_CP_COUNT];return tl_cp_snapshot(r,TL_CP_COUNT,&s)==0&&s.dropped==1;}
int exclusion(void){tl_cp_start(true);assert(!tl_cp_begin(TL_CP_PRESENT).active);tl_cp_exclude(false);tl_cp_ticket t=next(TL_CP_PRESENT);tl_cp_end(t);tl_cp_stop();assert(!tl_cp_begin(TL_CP_PRESENT).active);tl_cp_row row[TL_CP_COUNT];tl_cp_stats s;return tl_cp_snapshot(row,TL_CP_COUNT,&s)==1&&!s.running&&s.requested&&row[0].samples==1;}
int invalid(void){tl_cp_start(true);tl_cp_exclude(false);assert(!tl_cp_begin(UINT32_MAX).active);tl_cp_end((tl_cp_ticket){.active=true,.kind=UINT32_MAX});tl_cp_stats s;tl_cp_row r[TL_CP_COUNT];return tl_cp_snapshot(r,TL_CP_COUNT,&s)==0&&!s.clock_errors;}
int reset(void){tl_cp_start(true);tl_cp_exclude(false);tl_cp_ticket t=next(TL_CP_ACQUIRE);tl_cp_end(t);tl_cp_start(false);tl_cp_stats s;tl_cp_row r[TL_CP_COUNT];return tl_cp_snapshot(r,TL_CP_COUNT,&s)==0&&!s.requested;}
''')
  subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared','-I',str(TL),str(p/'check.c'),'-pthread','-o',str(p/'check.so')],check=True);cls.lib=ctypes.CDLL(str(p/'check.so'))
 def test_disabled_collects_nothing_and_preserves_early_returns(self):self.assertEqual(self.lib.disabled(),1)
 def test_real_clock_sampling_is_bounded_and_wait_is_not_cpu(self):self.assertEqual(self.lib.sampled(),1)
 def test_exclusion_and_restart_do_not_attribute_cross_boundary_work(self):
  for restart in [0,1]:self.assertEqual(self.lib.crossing(restart),1)
 def test_busy_recording_drops_instead_of_blocking(self):self.assertEqual(self.lib.busy(),1)
 def test_initial_exclusion_stop_and_completed_only_scope(self):self.assertEqual(self.lib.exclusion(),1)
 def test_invalid_component_is_not_a_memory_or_clock_access(self):self.assertEqual(self.lib.invalid(),1)
 def test_new_session_clears_metrics_without_old_credit(self):self.assertEqual(self.lib.reset(),1)
if __name__=='__main__':unittest.main()
