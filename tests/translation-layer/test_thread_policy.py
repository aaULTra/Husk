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
static int test_pcores;
int husk_test_performance_cores(void) { return test_pcores; }
static _Thread_local unsigned fake_qos;
static _Thread_local int fake_relative, next_failure, query_failure_at, queries;
static atomic_int writes, lines;
int pthread_get_qos_class_np(pthread_t t, qos_class_t *qos, int *relative) {
 (void)t;
 if (++queries == query_failure_at) return 22;
 *qos = fake_qos; *relative = fake_relative; return 0;
}
int pthread_set_qos_class_self_np(qos_class_t qos, int relative) {
 atomic_fetch_add(&writes, 1);
 if (next_failure) { int r = next_failure; next_failure = 0; return r; }
 fake_qos = qos; fake_relative = relative; return 0;
}
void tl_log_line(const char *fmt, ...) { (void)fmt; atomic_fetch_add(&lines, 1); }
void reset_fake(unsigned qos, int relative, int mode, const char *project, int pcores) {
 memset(&state, 0, sizeof(state)); test_pcores = pcores; fake_qos = qos; fake_relative = relative; next_failure = 0; query_failure_at = 0; queries = 0;
 atomic_store(&writes, 0); atomic_store(&lines, 0);
 husk_ue4_set_thread_policy(mode); tl_thread_policy_activate(project);
}
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
        cls.lib.reset_fake.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        cls.lib.tl_thread_policy_named.argtypes = [ctypes.c_char_p]
        cls.lib.tl_thread_policy_role.argtypes = [ctypes.c_char_p]
        cls.lib.current_qos.restype = ctypes.c_uint
        cls.lib.external_qos.argtypes = [ctypes.c_uint, ctypes.c_int]
        cls.lib.exercise_naming.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]

    def reset(self, qos=HIGH, relative=-2, mode=2, project=b'Dungeons', pcores=0):
        self.lib.reset_fake(qos, relative, mode, project, pcores)
    def name(self, value): self.lib.tl_thread_policy_named(value)

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
        for mode in (0, 1, -1, 3):
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

    def test_device_aware_iphone_duo_a20_pro_two_performance_cores(self):
        self.reset(mode=3, pcores=2)
        self.name(b'TaskGraphNP 0')
        self.assertEqual((self.lib.current_qos(), self.lib.write_count()), (HIGH, 0))
        self.name(b'TaskGraphNP 1')
        self.assertEqual(self.lib.current_qos(), NORMAL)
        self.name(b'TaskGraphBP 0')
        self.assertEqual(self.lib.current_qos(), UTILITY)
        self.name(b'RenderThread')
        self.assertEqual((self.lib.current_qos(), self.lib.current_relative()), (HIGH, -2))

    def test_device_aware_ipad_m4_one_tb_four_performance_cores(self):
        self.reset(mode=3, pcores=4)
        for index in (0, 1):
            self.name(f'TaskGraphNP {index}'.encode())
            self.assertEqual(self.lib.current_qos(), HIGH)
        self.name(b'TaskGraphNP 2')
        self.assertEqual(self.lib.current_qos(), NORMAL)
        self.name(b'TaskGraphThreadBP 2')
        self.assertEqual(self.lib.current_qos(), UTILITY)
        self.name(b'GameThread')
        self.assertEqual((self.lib.current_qos(), self.lib.current_relative()), (HIGH, -2))

    def test_device_aware_unknown_topology_falls_back_to_one_reserved_worker(self):
        self.reset(mode=3, pcores=0)
        self.name(b'TaskGraphNP 0')
        self.assertEqual(self.lib.current_qos(), HIGH)
        self.name(b'TaskGraphNP 1')
        self.assertEqual(self.lib.current_qos(), NORMAL)

    def test_device_aware_does_not_touch_other_unreal_projects(self):
        self.reset(mode=3, pcores=4, project=b'OtherGame')
        self.name(b'TaskGraphNP 3')
        self.assertEqual((self.lib.current_qos(), self.lib.write_count()), (HIGH, 0))

    def test_device_aware_does_not_reserve_ambiguous_worker_names(self):
        self.reset(mode=3, pcores=4)
        for name in (b'TaskGraphNP', b'TaskGraphNP 22', b'TaskGraphNP 1x'):
            self.name(name)
            self.assertEqual(self.lib.current_qos(), NORMAL if name != b'TaskGraphNP 1x' else HIGH)
        self.name(b'AudioThread')
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
