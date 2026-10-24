#!/usr/bin/env python3
"""Compile the actual policy with deterministic public-QoS API substitutes."""
import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]
NORMAL, UTILITY, HIGH, UNSPECIFIED = 0x15, 0x11, 0x19, 0

class ThreadPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        root = Path(cls.tmp.name)
        (root / 'husk-thread-policy-test-api.h').write_text('''typedef unsigned husk_test_qos_class_t;
#define qos_class_t husk_test_qos_class_t
#define pthread_get_qos_class_np husk_fake_get_qos
#define pthread_set_qos_class_self_np husk_fake_set_qos
#undef QOS_CLASS_UNSPECIFIED
#undef QOS_CLASS_BACKGROUND
#undef QOS_CLASS_UTILITY
#undef QOS_CLASS_DEFAULT
#undef QOS_CLASS_USER_INITIATED
#undef QOS_CLASS_USER_INTERACTIVE
#define QOS_CLASS_UNSPECIFIED 0
#define QOS_CLASS_BACKGROUND 0x09
#define QOS_CLASS_UTILITY 0x11
#define QOS_CLASS_DEFAULT 0x15
#define QOS_CLASS_USER_INITIATED 0x19
#define QOS_CLASS_USER_INTERACTIVE 0x21
int pthread_get_qos_class_np(pthread_t, qos_class_t *, int *);
int pthread_set_qos_class_self_np(qos_class_t, int);
''')
        source = r'''
#define HUSK_THREAD_POLICY_TEST 1
#include <stdarg.h>
#include <string.h>
#include "husk-tl-thread-policy.c"
static _Thread_local unsigned fake_qos;
static _Thread_local int fake_relative, next_failure, query_failure_at, queries;
static atomic_int writes, lines;
static _Thread_local int flip_generation;
int pthread_get_qos_class_np(pthread_t t, qos_class_t *qos, int *relative) {
 (void)t;
 if (++queries == query_failure_at) return 22;
 *qos = fake_qos; *relative = fake_relative; return 0;
}
int pthread_set_qos_class_self_np(qos_class_t qos, int relative) {
 errno = 5;
 atomic_fetch_add(&writes, 1);
 if (next_failure) { int r = next_failure; next_failure = 0; return r; }
 fake_qos = qos; fake_relative = relative;
 if (flip_generation && qos == QOS_CLASS_UTILITY) { flip_generation=0; tl_thread_policy_suspend(); }
 return 0;
}
void tl_log_line(const char *fmt, ...) { (void)fmt; atomic_fetch_add(&lines, 1); }
void reset_fake(unsigned qos, int relative, int mode, const char *project) {
 memset(&state, 0, sizeof(state)); flip_generation=0; fake_qos = qos; fake_relative = relative; next_failure = 0; query_failure_at = 0; queries = 0;
 atomic_store(&writes, 0); atomic_store(&lines, 0);
 husk_ue4_set_worker_capacity(6); husk_ue4_set_thread_policy(mode); tl_thread_policy_activate(project);
}
int checkpoint_errno(void) { errno=11; tl_thread_policy_checkpoint(); return errno; }
void flip_during_cap(void) { flip_generation=1; }
unsigned current_qos(void) { return fake_qos; }
int current_relative(void) { return fake_relative; }
int write_count(void) { return atomic_load(&writes); }
int log_count(void) { return atomic_load(&lines); }
void fail_query_after(int calls) { query_failure_at = queries + calls; }
void fail_next(int rc) { next_failure = rc; }
void external_qos(unsigned qos, int relative) { fake_qos = qos; fake_relative = relative; }
static void *other_thread(void *p) {
 (void)p; fake_qos = QOS_CLASS_USER_INTERACTIVE; fake_relative = -4;
 tl_thread_policy_named("TaskGraphBP 1");
 if (fake_qos != QOS_CLASS_UTILITY) return (void *)1;
 tl_thread_policy_named("RenderThread");
 return (void *)(uintptr_t)(fake_qos != QOS_CLASS_USER_INTERACTIVE || fake_relative != -4);
}
int exercise_other_thread(void) {
 pthread_t t; void *result;
 if (pthread_create(&t, NULL, other_thread, NULL)) return 2;
 pthread_join(t, &result); return (int)(uintptr_t)result;
}
'''.replace('#include <stdarg.h>', '#include <stdarg.h>\n#include <stdint.h>')
        pthreads = (ROOT / 'src/translation-layer-next/husk-tl-bionic-pthread.c').read_text()
        shim = (ROOT / 'src/translation-layer-next/husk-tl-bionic.c').read_text()
        io = (ROOT / 'src/translation-layer-next/husk-tl-bionic-io.c').read_text()
        rename = pthreads[pthreads.index('static int b_setname_np('):pthreads.index('static int b_join(')]
        prctl = shim[shim.index('static int bionic_prctl('):shim.index('\n}', shim.index('static int bionic_prctl(')) + 2]
        raw = io[io.index('    case 167:'):io.index('    case 160:')].split('\n', 1)[1]
        source += r'''
static int name_error;
static int mock_name(const char *name) { (void)name; return name_error; }
static int mock_getname(pthread_t thread, char *name, size_t n) { (void)thread; if (n) name[0]=0; return 0; }
static void tl_set_guest_errno(int e) { (void)e; }
#define pthread_setname_np mock_name
#define pthread_getname_np mock_getname
''' + rename + prctl
        source += 'static long raw_prctl(long a0, long a1) {\n' + raw + '}\n'
        source += r'''
void exercise_naming(int path, const char *name, int failure) {
 name_error = failure;
 if (path == 0) b_setname_np(pthread_self(), name);
 else if (path == 1) bionic_prctl(15, (unsigned long)name, 0, 0, 0);
 else raw_prctl(15, (long)name);
}
'''
        path = root / 'test.c'; path.write_text(source)
        library = root / 'policy.so'
        subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-shared', '-fPIC', '-pthread', '-I'+str(root),
                        '-I'+str(ROOT/'src/translation-layer-next'), str(path), '-o', str(library)], check=True)
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.reset_fake.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_char_p]
        cls.lib.tl_thread_policy_named.argtypes = [ctypes.c_char_p]
        cls.lib.tl_thread_policy_role.argtypes = [ctypes.c_char_p]
        cls.lib.current_qos.restype = ctypes.c_uint
        cls.lib.tl_thread_policy_sample.argtypes = [ctypes.c_int64, ctypes.c_int64, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_int, ctypes.c_bool, ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint]
        cls.lib.tl_thread_policy_pipeline_completed.argtypes = [ctypes.c_int64, ctypes.c_int64]
        cls.lib.tl_thread_policy_frame.argtypes = [ctypes.c_int64, ctypes.c_int64]
        cls.lib.external_qos.argtypes = [ctypes.c_uint, ctypes.c_int]
        cls.lib.exercise_naming.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]

    def reset(self, qos=HIGH, relative=-2, mode=2, project=b'Dungeons'):
        self.lib.reset_fake(qos, relative, mode, project)
    def name(self, value): self.lib.tl_thread_policy_named(value)

    def sample(self, seconds, fps=60, p95=18, maximum=20, thermal=0, low=False,
               pipeline_ms=0, pipeline_max_ms=0, inflight=0, span=10):
        self.lib.tl_thread_policy_sample(int(seconds*1e9), int(span*1e9), fps, p95, maximum,
                                       thermal, low, int(pipeline_ms*1e6), int(pipeline_max_ms*1e6), inflight)

    def admit(self):
        self.sample(10); self.sample(20)
        self.assertTrue(self.lib.tl_thread_policy_trial_active())

    def test_adaptive_capacity_hint_and_guarded_admission(self):
        for cpu_count, name, expected in ((10,b'TaskGraphNP 1',NORMAL),(6,b'TaskGraphNP 1',UTILITY),(10,b'TaskGraphNP 2',UTILITY)):
            self.reset(mode=3); self.lib.husk_ue4_set_worker_capacity(cpu_count)
            self.name(name); self.assertEqual(self.lib.current_qos(),NORMAL)
            self.sample(10); self.assertFalse(self.lib.tl_thread_policy_trial_active())
            self.sample(20); self.lib.tl_thread_policy_checkpoint()
            self.assertEqual(self.lib.current_qos(),expected)

    def test_adaptive_rollback_restores_baseline_at_self_checkpoint(self):
        self.reset(mode=3); self.name(b'TaskGraphNP 2'); self.admit()
        self.lib.tl_thread_policy_checkpoint(); self.assertEqual(self.lib.current_qos(),UTILITY)
        self.sample(30,fps=50,p95=24)
        self.assertFalse(self.lib.tl_thread_policy_trial_active())
        self.lib.tl_thread_policy_checkpoint(); self.assertEqual(self.lib.current_qos(),NORMAL)
        for t in range(40,90,10): self.sample(t)
        self.assertFalse(self.lib.tl_thread_policy_trial_active())
        self.sample(90); self.sample(100)
        self.assertTrue(self.lib.tl_thread_policy_trial_active())

    def test_expensive_pipeline_work_heat_power_transition_and_loading_do_not_admit_trial(self):
        for kwargs in ({'pipeline_max_ms':2.01},{'pipeline_ms':50.01},{'inflight':1},
                       {'maximum':50.01},{'thermal':1},{'span':1},{'fps':58},{'p95':21}):
            self.reset(mode=3); self.sample(10,**kwargs); self.sample(20,**kwargs)
            self.assertFalse(self.lib.tl_thread_policy_trial_active())
        self.reset(mode=3); self.admit(); self.sample(30,low=True)
        self.assertFalse(self.lib.tl_thread_policy_trial_active())

    def test_small_pipeline_activity_no_longer_permanently_blocks_healthy_trial(self):
        self.reset(mode=3)
        for t in (10,20): self.sample(t,pipeline_ms=32.4,pipeline_max_ms=1.2)
        self.assertTrue(self.lib.tl_thread_policy_trial_active())

    def test_pipeline_budget_scales_with_valid_window_duration(self):
        for span, total, expected in ((8,40,True),(8,40.01,False),(15,75,True),(15,75.01,False)):
            self.reset(mode=3)
            for t in (span,span*2,span*3): self.sample(t,span=span,pipeline_ms=total,pipeline_max_ms=2)
            self.assertEqual(bool(self.lib.tl_thread_policy_trial_active()),expected)

    def test_expensive_pipeline_completion_releases_trial_before_next_sample(self):
        self.reset(mode=3); self.name(b'TaskGraphNP 2'); self.admit()
        self.lib.tl_thread_policy_checkpoint(); self.assertEqual(self.lib.current_qos(),UTILITY)
        self.lib.tl_thread_policy_pipeline_completed(21000000000,2000001)
        self.assertFalse(self.lib.tl_thread_policy_trial_active())
        self.lib.tl_thread_policy_checkpoint(); self.assertEqual(self.lib.current_qos(),NORMAL)
        self.sample(30); self.sample(40)
        self.assertFalse(self.lib.tl_thread_policy_trial_active())

    def test_cheap_pipeline_completion_preserves_trial(self):
        self.reset(mode=3); self.admit()
        self.lib.tl_thread_policy_pipeline_completed(21000000000,2000000)
        self.assertTrue(self.lib.tl_thread_policy_trial_active())

    def test_waiting_diagnostics_are_rate_limited_for_same_reason(self):
        self.reset(mode=3)
        for t in (10,20,30): self.sample(t,pipeline_ms=100,pipeline_max_ms=10)
        self.assertEqual(self.lib.log_count(),3) # two activation lines, one reason
        self.sample(40,pipeline_ms=100,pipeline_max_ms=10)
        self.assertEqual(self.lib.log_count(),4)

    def test_critical_and_ambiguous_roles_preserved_and_pause_releases_trial(self):
        for name in (b'TaskGraphHP 4',b'RenderThread',b'AudioThread',b'TaskGraphNP'):
            self.reset(mode=3); self.name(name); self.admit(); self.lib.tl_thread_policy_checkpoint()
            self.assertEqual(self.lib.current_qos(), NORMAL if name==b'TaskGraphNP' else HIGH)
        self.reset(mode=3); self.name(b'TaskGraphNP 2'); self.admit(); self.lib.tl_thread_policy_checkpoint()
        self.lib.tl_thread_policy_suspend(); self.lib.tl_thread_policy_checkpoint()
        self.assertEqual(self.lib.current_qos(),NORMAL)

    def test_fast_guard_releases_after_six_misses_or_one_large_stall(self):
        for interval, count in ((23000000,6),(60000000,1)):
            self.reset(mode=3); self.admit()
            for i in range(count): self.lib.tl_thread_policy_frame(21000000000+i*interval,interval)
            self.assertFalse(self.lib.tl_thread_policy_trial_active())

    def test_adaptive_failure_retries_are_rate_limited(self):
        self.reset(mode=3); self.name(b'TaskGraphNP 2'); self.admit()
        self.lib.fail_next(22); self.lib.tl_thread_policy_checkpoint()
        writes=self.lib.write_count()
        for _ in range(100): self.lib.tl_thread_policy_checkpoint()
        self.assertEqual(self.lib.write_count(),writes)

    def test_self_checkpoint_preserves_wait_errno(self):
        self.reset(mode=3); self.name(b'TaskGraphNP 2'); self.admit()
        self.assertEqual(self.lib.checkpoint_errno(),11)

    def test_generation_change_during_setter_is_not_mistaken_for_applied_revision(self):
        self.reset(mode=3); self.name(b'TaskGraphNP 2'); self.admit()
        self.lib.flip_during_cap(); self.lib.tl_thread_policy_checkpoint()
        self.assertFalse(self.lib.tl_thread_policy_trial_active())
        self.lib.tl_thread_policy_checkpoint()
        self.assertEqual(self.lib.current_qos(),NORMAL)

    def test_exact_worker_names_and_android_shortened_forms(self):
        for name in (b'TaskGraphThreadNP', b'TaskGraphThreadNP 0', b'TaskGraphNP 12'):
            self.assertEqual(self.lib.tl_thread_policy_role(name), 1)
        for name in (b'TaskGraphThreadBP 0', b'TaskGraphBP 3'):
            self.assertEqual(self.lib.tl_thread_policy_role(name), 2)
        for name in (None, b'', b'TaskGraphThreadHP 0', b'TaskGraphHP 1', b'TaskGraphThreadNPx',
                     b'TaskGraphNP -1', b'TaskGraphNP 2 extra', b'TaskGraphNP ', b'AudioThread', b'RenderThread', b'GameThread'):
            self.assertEqual(self.lib.tl_thread_policy_role(name), 0)

    def test_normal_and_background_caps(self):
        self.reset(); self.name(b'TaskGraphNP 0')
        self.assertEqual((self.lib.current_qos(), self.lib.current_relative()), (NORMAL, -2))
        self.reset(); self.name(b'TaskGraphBP 0')
        self.assertEqual(self.lib.current_qos(), UTILITY)

    def test_critical_and_unknown_threads_are_preserved(self):
        for name in (b'GameThread', b'RenderThread', b'RHIThread', b'AudioThread', b'TaskGraphHP 0', b'unknown'):
            self.reset(); self.name(name)
            self.assertEqual((self.lib.current_qos(), self.lib.current_relative(), self.lib.write_count()), (HIGH, -2, 0))

    def test_lower_and_unspecified_qos_are_never_raised(self):
        for qos in (UNSPECIFIED, 0x09, UTILITY):
            self.reset(qos=qos); self.name(b'TaskGraphNP 0')
            self.assertEqual((self.lib.current_qos(), self.lib.write_count()), (qos, 0))

    def test_default_and_observe_modes_do_not_change_qos(self):
        for mode in (0, 1, -1, 4):
            self.reset(mode=mode); self.name(b'TaskGraphBP 0')
            self.assertEqual((self.lib.current_qos(), self.lib.write_count()), (HIGH, 0))
        self.reset(mode=1); self.name(b'TaskGraphNP 0')
        self.assertGreater(self.lib.log_count(), 0)

    def test_other_projects_and_missing_metadata_are_untouched(self):
        for project in (None, b'', b'dungeons', b'Other', b'DungeonsOther'):
            self.reset(project=project); self.name(b'TaskGraphNP 0')
            self.assertEqual((self.lib.current_qos(), self.lib.write_count()), (HIGH, 0))

    def test_renaming_restores_original_relative_priority(self):
        self.reset(); self.name(b'TaskGraphBP 0'); self.name(b'RenderThread')
        self.assertEqual((self.lib.current_qos(), self.lib.current_relative()), (HIGH, -2))
        self.name(b'TaskGraphNP 0')
        self.assertEqual(self.lib.current_qos(), NORMAL)

    def test_setter_failure_does_not_claim_or_keep_a_cap(self):
        self.reset(); self.lib.fail_next(1); self.name(b'TaskGraphBP 0')
        self.assertEqual(self.lib.current_qos(), HIGH)
        self.name(b'RenderThread')
        self.assertEqual(self.lib.write_count(), 1)

    def test_restore_failure_retries_without_applying_another_cap(self):
        self.reset(); self.name(b'TaskGraphBP 0')
        self.lib.fail_next(1); self.name(b'RenderThread')
        self.assertEqual(self.lib.current_qos(), UTILITY)
        self.name(b'RenderThread')
        self.assertEqual((self.lib.current_qos(), self.lib.current_relative()), (HIGH, -2))

    def test_initial_query_failure_preserves_qos_and_saved_restore_state(self):
        self.reset(); self.lib.fail_query_after(1); self.name(b'TaskGraphBP 0')
        self.assertEqual((self.lib.current_qos(), self.lib.write_count()), (HIGH, 0))
        self.name(b'TaskGraphBP 0')
        self.lib.fail_query_after(1); self.name(b'RenderThread')
        self.assertEqual((self.lib.current_qos(), self.lib.write_count()), (UTILITY, 1))
        self.name(b'RenderThread')
        self.assertEqual((self.lib.current_qos(), self.lib.current_relative()), (HIGH, -2))

    def test_after_query_failure_does_not_forget_successful_cap(self):
        self.reset(); self.lib.fail_query_after(2); self.name(b'TaskGraphNP 0')
        self.assertEqual((self.lib.current_qos(), self.lib.write_count()), (NORMAL, 1))
        self.name(b'GameThread')
        self.assertEqual((self.lib.current_qos(), self.lib.current_relative()), (HIGH, -2))

    def test_uncapped_external_qos_change_is_not_overridden(self):
        self.reset(); self.name(b'unknown')
        self.lib.external_qos(UTILITY, -1); self.name(b'TaskGraphNP 0')
        self.assertEqual((self.lib.current_qos(), self.lib.current_relative(), self.lib.write_count()), (UTILITY, -1, 0))

    def test_policy_state_is_per_thread(self):
        self.reset(); self.name(b'TaskGraphNP 0')
        self.assertEqual(self.lib.exercise_other_thread(), 0)
        self.assertEqual(self.lib.current_qos(), NORMAL)
        self.name(b'GameThread')
        self.assertEqual((self.lib.current_qos(), self.lib.current_relative()), (HIGH, -2))

    def test_diagnostics_are_bounded(self):
        self.reset(mode=1)
        for _ in range(200): self.name(b'unknown')
        self.assertEqual(self.lib.log_count(), 129) # activation plus 128 named events

    def test_all_three_naming_routes_apply_the_policy(self):
        for path in range(3):
            self.reset()
            self.lib.exercise_naming(path, b'TaskGraphNP 0', 0)
            self.assertEqual(self.lib.current_qos(), NORMAL)

    def test_unsuccessful_host_naming_does_not_apply_policy(self):
        for path in range(3):
            self.reset()
            self.lib.exercise_naming(path, b'TaskGraphNP 0', 34)
            self.assertEqual((self.lib.current_qos(), self.lib.write_count()), (HIGH, 0))

if __name__ == '__main__': unittest.main()
