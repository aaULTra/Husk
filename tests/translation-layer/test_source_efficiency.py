#!/usr/bin/env python3
"""Compile real snapshot/wait routines; verify behaviour without a phone or APK."""
import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class SourceEfficiencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        loader = (ROOT / 'src/translation-layer/husk-tl-load.c').read_text()
        log_types = loader[loader.index('#define TL_LOG_CHUNK'):loader.index('/* The append funnel.')]
        log_append = loader[loader.index('void tl_log_line(const char *fmt, ...)\n{'):loader.index('/*\n * Finished frames,')]
        log_snapshot = loader[loader.index('static char *attempt_log_snapshot_locked'):loader.index('\nint husk_tl_attempt_frames')]
        pthreads = (ROOT / 'src/translation-layer-next/husk-tl-bionic-pthread.c').read_text()
        wait = pthreads[pthreads.index('static int b_sem_timedwait'):pthreads.index('static int b_sem_getvalue')]
        source = r'''
#define _POSIX_C_SOURCE 200809L
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <time.h>
#include <errno.h>
#include <unistd.h>
static void tl_thread_policy_checkpoint(void) {}
static bool allocation_fails;
static void *snapshot_malloc(size_t n) { return allocation_fails ? NULL : malloc(n); }
static char *snapshot_strdup(const char *s) { return allocation_fails ? NULL : strdup(s); }
#define malloc snapshot_malloc
#define strdup snapshot_strdup
'''
        source += log_types + '\nstatic struct { tl_logbuf log; } g_run;\nint tl_log_sink_fd = -1;\n'
        source += log_append + log_snapshot
        source += r'''
void append_line(const char *s) { tl_log_line("%s", s); }
void fail_allocations(int fail) { allocation_fails = fail; }
void reset_log(void) {
 pthread_mutex_lock(&g_log_mutex);
 free(g_run.log.buf); memset(&g_run.log, 0, sizeof(g_run.log)); ++g_log_revision;
 pthread_mutex_unlock(&g_log_mutex);
}
typedef struct { pthread_mutex_t m; pthread_cond_t c; int count; } host_sem;
static host_sem *hs(void *g) { return g; }
static int guest_errno;
static int tl_errno_to_guest(int e) { return e; }
static void tl_set_guest_errno(int e) { guest_errno = e; }
'''
        source += wait + r'''
static void *wake_thread(void *raw) {
 host_sem *s = raw;
 for (int i=0; i<25; ++i) {
  struct timespec delay = {0, 10000000}; nanosleep(&delay, NULL);
  pthread_mutex_lock(&s->m); pthread_cond_signal(&s->c); pthread_mutex_unlock(&s->m);
 }
 return NULL;
}
/* modes: spurious wakes, expired, invalid, token with expired, token with invalid */
double exercise_wait(int mode, int *result, int *error, int *remaining) {
 host_sem s = {PTHREAD_MUTEX_INITIALIZER, PTHREAD_COND_INITIALIZER, mode >= 3 ? 1 : 0};
 struct timespec deadline, start, end;
 clock_gettime(CLOCK_REALTIME, &deadline);
 if (mode == 0) { deadline.tv_nsec += 100000000; if (deadline.tv_nsec >= 1000000000) { ++deadline.tv_sec; deadline.tv_nsec -= 1000000000; } }
 else deadline.tv_sec -= 1;
 if (mode == 2 || mode == 4) deadline.tv_nsec = 1000000000;
 pthread_t worker;
 if (mode == 0) pthread_create(&worker, NULL, wake_thread, &s);
 clock_gettime(CLOCK_MONOTONIC, &start); guest_errno = 0;
 *result = b_sem_timedwait(&s, &deadline); *error = guest_errno;
 clock_gettime(CLOCK_MONOTONIC, &end); *remaining = s.count;
 if (mode == 0) pthread_join(worker, NULL);
 pthread_cond_destroy(&s.c); pthread_mutex_destroy(&s.m);
 return end.tv_sec - start.tv_sec + (end.tv_nsec - start.tv_nsec) / 1e9;
}
'''
        path = Path(cls.tmp.name) / 'source.c'
        library = path.with_suffix('.so')
        path.write_text(source)
        subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-shared', '-fPIC', '-pthread', str(path), '-o', str(library)], check=True)
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.husk_tl_attempt_log_if_changed.argtypes = [ctypes.POINTER(ctypes.c_uint64)]
        cls.lib.husk_tl_attempt_log_if_changed.restype = ctypes.c_void_p
        cls.lib.husk_tl_attempt_log.restype = ctypes.c_void_p
        cls.lib.append_line.argtypes = [ctypes.c_char_p]
        cls.lib.exercise_wait.argtypes = [ctypes.c_int] + [ctypes.POINTER(ctypes.c_int)] * 3
        cls.lib.exercise_wait.restype = ctypes.c_double
        cls.libc = ctypes.CDLL(None)
        cls.libc.free.argtypes = [ctypes.c_void_p]

    def setUp(self):
        self.lib.fail_allocations(0)
        self.lib.reset_log()

    def text(self, pointer):
        self.assertTrue(pointer)
        try:
            return ctypes.string_at(pointer)
        finally:
            self.libc.free(pointer)

    def test_unchanged_snapshot_skips_allocation_and_keeps_unconditional_export(self):
        revision = ctypes.c_uint64()
        self.assertEqual(self.text(self.lib.husk_tl_attempt_log_if_changed(ctypes.byref(revision))), b'')
        self.assertFalse(self.lib.husk_tl_attempt_log_if_changed(ctypes.byref(revision)))
        self.lib.append_line(b'game started')
        self.assertEqual(self.text(self.lib.husk_tl_attempt_log_if_changed(ctypes.byref(revision))), b'game started\n')
        self.assertFalse(self.lib.husk_tl_attempt_log_if_changed(ctypes.byref(revision)))
        self.assertEqual(self.text(self.lib.husk_tl_attempt_log()), b'game started\n')

    def test_allocation_failure_does_not_consume_update(self):
        self.lib.append_line(b'keep this')
        revision = ctypes.c_uint64()
        self.lib.fail_allocations(1)
        self.assertFalse(self.lib.husk_tl_attempt_log_if_changed(ctypes.byref(revision)))
        self.assertEqual(revision.value, 0)
        self.lib.fail_allocations(0)
        self.assertEqual(self.text(self.lib.husk_tl_attempt_log_if_changed(ctypes.byref(revision))), b'keep this\n')

    def test_independent_readers_receive_their_own_updates(self):
        a, b = ctypes.c_uint64(), ctypes.c_uint64()
        self.lib.append_line(b'one')
        self.assertEqual(self.text(self.lib.husk_tl_attempt_log_if_changed(ctypes.byref(a))), b'one\n')
        self.lib.append_line(b'two')
        self.assertEqual(self.text(self.lib.husk_tl_attempt_log_if_changed(ctypes.byref(b))), b'one\ntwo\n')
        self.assertEqual(self.text(self.lib.husk_tl_attempt_log_if_changed(ctypes.byref(a))), b'one\ntwo\n')

    def exercise(self, mode):
        result, error, remaining = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        elapsed = self.lib.exercise_wait(mode, ctypes.byref(result), ctypes.byref(error), ctypes.byref(remaining))
        return elapsed, result.value, error.value, remaining.value

    def test_spurious_wakes_do_not_extend_absolute_deadline(self):
        elapsed, result, error, remaining = self.exercise(0)
        import errno
        self.assertEqual((result, error, remaining), (-1, errno.ETIMEDOUT, 0))
        self.assertGreater(elapsed, 0.06)
        self.assertLess(elapsed, 0.22)

    def test_expired_and_invalid_deadlines_preserve_semaphore(self):
        import errno
        self.assertEqual(self.exercise(1)[1:], (-1, errno.ETIMEDOUT, 0))
        self.assertEqual(self.exercise(2)[1:], (-1, errno.EINVAL, 0))

    def test_available_token_succeeds_even_with_expired_or_invalid_deadline(self):
        self.assertEqual(self.exercise(3)[1:], (0, 0, 0))
        self.assertEqual(self.exercise(4)[1:], (0, 0, 0))

if __name__ == '__main__':
    unittest.main()
