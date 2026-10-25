#!/usr/bin/env python3
"""Exercise real observer aggregation/exclusions/retention, independent of iOS."""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TL = ROOT / 'src/translation-layer-next'

class Stats(C.Structure):
    _fields_ = [(x, C.c_uint64) for x in ['intervals','above20','above33','above50','discontinuities']] + [
        (x,C.c_double) for x in ['interval_seconds','p50_ms','p95_ms','p99_ms','worst_ms']] + [
        ('host_calls',C.c_uint64*6),('host_ns',C.c_uint64*6),('slow_pipeline_calls',C.c_uint64),
        ('worst_pipeline_ns',C.c_uint64),('dropped',C.c_uint64), *[(x,C.c_uint64) for x in ['dropped_frames','dropped_host','dropped_events','lost_frame_ns','lost_frame_max_ns']],('width',C.c_uint32),('height',C.c_uint32)]
class Event(C.Structure):
    _fields_ = [('monotonic_seconds',C.c_double),('text',C.c_char*512)]

class EfficiencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.temp.cleanup)
        path=Path(cls.temp.name)/'observer.c'
        path.write_text('#include "husk-tl-efficiency.c"\nvoid hold(int v) { if(v) pthread_mutex_lock(&mu); else pthread_mutex_unlock(&mu); }\nvoid hold_writer(int v) { if(v) atomic_flag_test_and_set(&frame_writer); else atomic_flag_clear(&frame_writer); }\n')
        lib=path.with_suffix('.so')
        subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC','-pthread','-I',str(TL),str(path),'-o',str(lib)],check=True)
        cls.lib=C.CDLL(str(lib))
        cls.lib.tl_em_frame.argtypes=[C.c_int64]
        cls.lib.tl_em_host.argtypes=[C.c_uint,C.c_uint64]
        cls.lib.tl_em_snapshot.argtypes=[C.c_bool,C.POINTER(Stats)]
        cls.lib.tl_em_pop.argtypes=[C.POINTER(Event)]; cls.lib.tl_em_pop.restype=C.c_bool
        cls.lib.tl_em_log.argtypes=[C.c_char_p]
    def setUp(self):
        self.lib.tl_em_start(); self.lib.tl_em_exclude(False)
    def tearDown(self): self.lib.tl_em_stop()
    def snapshot(self,total=True):
        s=Stats();self.lib.tl_em_snapshot(total,C.byref(s));return s
    def test_thresholds_percentiles_and_long_hitch_retained(self):
        t=1;self.lib.tl_em_frame(t)
        for n in [16666667,20000000,20000001,33333333,33333334,50000000,50000001,1500000000]:
            t+=n;self.lib.tl_em_frame(t)
        s=self.snapshot()
        self.assertEqual((s.intervals,s.above20,s.above33,s.above50),(8,6,4,2))
        self.assertEqual(s.p50_ms,33.4);self.assertEqual(s.p95_ms,1500)
        self.assertEqual(s.worst_ms,1500)
    def test_exclusion_resets_anchor_but_keeps_surrounding_data(self):
        self.lib.tl_em_frame(1);self.lib.tl_em_frame(20000001)
        self.lib.tl_em_exclude(True);self.lib.tl_em_frame(5000000000)
        self.lib.tl_em_host(0,777)
        self.lib.tl_em_exclude(False);self.lib.tl_em_frame(8000000000);self.lib.tl_em_frame(8020000000)
        s=self.snapshot();self.assertEqual(s.intervals,2);self.assertAlmostEqual(s.interval_seconds,.04)
        self.assertEqual(s.host_calls[0],0)
    def test_window_drain_preserves_total(self):
        self.lib.tl_em_frame(1);self.lib.tl_em_frame(16666668)
        self.assertEqual(self.snapshot(False).intervals,1)
        self.assertEqual(self.snapshot(False).intervals,0)
        self.assertEqual(self.snapshot().intervals,1)
    def test_disabled_does_not_change_statistics(self):
        self.lib.tl_em_stop();self.lib.tl_em_frame(1);self.lib.tl_em_host(4,500000000)
        self.lib.tl_em_log(b'ue4 cache: ignored');self.assertEqual(self.snapshot().host_calls[4],0)
        e=Event();self.assertFalse(self.lib.tl_em_pop(C.byref(e)))
    def test_bounded_events_and_relevant_filter(self):
        self.lib.tl_em_log(b'unrelated repetitive frame log')
        for _ in range(300):self.lib.tl_em_log(b'ue4 cache: accepted seed is not a hit')
        e=Event();count=0
        while self.lib.tl_em_pop(C.byref(e)):count+=1
        self.assertEqual(count,256);self.assertEqual(self.snapshot().dropped,44)
    def test_busy_diagnostics_never_wait_and_disclose_gap(self):
        self.lib.tl_em_frame(1);self.lib.hold(1)
        self.lib.tl_em_frame(20000001);self.lib.tl_em_host(2,7000);self.lib.hold(0)
        self.lib.tl_em_frame(40000001);self.lib.tl_em_frame(60000001)
        s=self.snapshot();self.assertEqual(s.dropped,1);self.assertEqual(s.dropped_host,1);self.assertEqual(s.intervals,3)
    def test_host_and_event_contention_cannot_hide_a_long_frame(self):
        self.lib.tl_em_frame(1);self.lib.hold(1)
        self.lib.tl_em_host(1,1000);self.lib.tl_em_log(b'ue4 cache: observed')
        self.lib.tl_em_frame(600000001);self.lib.hold(0)
        s=self.snapshot();self.assertEqual(s.worst_ms,600);self.assertEqual(s.intervals,1)
        self.assertEqual((s.dropped_host,s.dropped_events,s.dropped_frames),(1,1,0))
    def test_frame_writer_loss_is_categorised_without_resetting_next_anchor(self):
        self.lib.tl_em_frame(1);self.lib.hold_writer(1)
        self.lib.tl_em_frame(600000001);self.lib.hold_writer(0)
        self.lib.tl_em_frame(620000001)
        s=self.snapshot();self.assertEqual(s.intervals,1);self.assertEqual(s.dropped_frames,1)
        self.assertEqual(s.lost_frame_max_ns,600000000);self.assertEqual(s.lost_frame_ns,600000000)
        self.assertEqual(s.worst_ms,20)
    def test_ring_overflow_is_bounded_and_old_session_records_are_rejected(self):
        for t in range(8200):self.lib.tl_em_frame(t*20000000+1)
        s=self.snapshot();self.assertEqual(s.intervals,8192);self.assertEqual(s.dropped_frames,7)
        self.lib.tl_em_frame(200000000000);self.lib.tl_em_start();self.lib.tl_em_exclude(False)
        self.lib.tl_em_frame(300000000000);self.lib.tl_em_frame(300020000000)
        s=self.snapshot();self.assertEqual(s.intervals,1);self.assertEqual(s.worst_ms,20)
    def test_backward_clock_and_pipeline_batch_call_attribution(self):
        self.lib.tl_em_frame(100);self.lib.tl_em_frame(50)
        self.lib.tl_em_host(4,17000000);self.lib.tl_em_host(5,90000000)
        self.lib.tl_em_host(123,999)
        s=self.snapshot();self.assertEqual(s.discontinuities,1)
        self.assertEqual(s.slow_pipeline_calls,2);self.assertEqual(s.worst_pipeline_ns,90000000)
        self.assertEqual(s.host_calls[4],1)
    def test_dimensions_survive_start_and_missing_data_has_no_samples(self):
        self.lib.tl_em_size(2128,1600);self.lib.tl_em_start()
        s=self.snapshot();self.assertEqual((s.width,s.height),(2128,1600));self.assertEqual(s.intervals,0)

if __name__=='__main__':unittest.main()
