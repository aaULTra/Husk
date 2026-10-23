#!/usr/bin/env python3
"""Exercise the real loader replacement routine with bounded fake ELF metadata."""
import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ResolutionHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        source = (ROOT / "src/translation-layer-next/husk-tl-ld.c").read_text()
        start = source.index("static uint8_t *function_patch_site(")
        stop = source.index("/* dlsym(handle)", start)
        routine = source[start:stop]
        harness = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
typedef struct { uint8_t st_info; uint64_t st_size, st_value; } elf_sym;
typedef struct { int ncode; struct { uint64_t start, end; } code[1]; } tl_lib;
static unsigned char rx[64], rw[64];
static unsigned char trampoline_rx[64], trampoline_rw[64];
static elf_sym symbol;
static bool found, executable, allocation_allowed;
static size_t flushed, trampoline_flushed;
static const elf_sym *lib_find(tl_lib *l, const char *n) { (void)l; (void)n; return found ? &symbol : NULL; }
static void *sym_value(tl_lib *l, const elf_sym *s) { (void)l; (void)s; return rx; }
static bool tl_xmem_is_rx(const void *p) { return executable && p == rx; }
static ptrdiff_t tl_xmem_delta(void) { return (intptr_t)rw - (intptr_t)rx; }
static void tl_xmem_flush(void *p, size_t n) { if (p == rx) flushed = n; if (p == trampoline_rx) trampoline_flushed = n; }
static bool tl_xmem_alloc(size_t n, uint8_t **x, uint8_t **w) {
    if (!allocation_allowed || n != 32) return false;
    *x = trampoline_rx; *w = trampoline_rw; return true;
}
'''
        harness += routine + r'''
int exercise(unsigned type, uint64_t size, uint64_t value, uint64_t code_end, int present, int exec)
{
    memset(rx, 0xaa, sizeof(rx)); memset(rw, 0xaa, sizeof(rw)); flushed = 0;
    symbol = (elf_sym){type, size, value}; found = present; executable = exec;
    tl_lib lib = {.ncode=1, .code={{0x1000, code_end}}};
    return tl_ld_replace_function(&lib, "function", (void *)(uintptr_t)0x123456789abcdef0ULL);
}
const void *written(void) { return rw; }
size_t flush_size(void) { return flushed; }
int exercise_hook(int mismatch, int allocate)
{
    uint32_t expected[] = {0xD10183FFu,0xA90357F6u,0xA9044FF4u,0xA9057BFDu};
    memcpy(rx, expected, 16); memset(rw, 0xaa, sizeof(rw));
    memset(trampoline_rw, 0xaa, sizeof(trampoline_rw));
    if (mismatch) rx[0] ^= 1;
    symbol = (elf_sym){2, 424, 0x1000}; found = executable = true;
    allocation_allowed = allocate; flushed = trampoline_flushed = 0;
    tl_lib lib = {.ncode=1, .code={{0x1000,0x1200}}};
    return tl_ld_hook_prologue(&lib, "function", (void *)(uintptr_t)0x123456789abcdef0ULL, expected) == trampoline_rx;
}
const void *trampoline_written(void) { return trampoline_rw; }
uintptr_t continuation(void) { return (uintptr_t)(rx + 16); }
size_t trampoline_flush_size(void) { return trampoline_flushed; }
'''
        native = (ROOT / "src/translation-layer-next/husk-tl-nativeactivity.c").read_text()
        start = native.index("static void sharp_request_resolution(")
        wrapper = native[start:native.index("\n}\n", start) + 3]
        harness += r'''
#include <stdarg.h>
typedef struct { int left, top, right, bottom; } Rect;
static Rect sharp_screen_rect = {0,0,2424,1816};
static int passed[3];
static void record_request(int w, int h, int mode) { passed[0]=w; passed[1]=h; passed[2]=mode; }
static void (*original_resolution_request)(int,int,int) = record_request;
static void tl_log_line(const char *format, ...) { (void)format; }
'''
        harness += wrapper + r'''
const int *exercise_request(int w, int h, int mode) { sharp_request_resolution(w,h,mode); return passed; }
'''
        path = Path(cls.tmp.name)
        (path / "hook.c").write_text(harness)
        subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra", "-Werror",
                        "-shared", "-fPIC", str(path / "hook.c"), "-o", str(path / "hook.so")], check=True)
        cls.lib = ctypes.CDLL(str(path / "hook.so"))
        cls.lib.exercise.argtypes = [ctypes.c_uint, ctypes.c_uint64, ctypes.c_uint64,
                                    ctypes.c_uint64, ctypes.c_int, ctypes.c_int]
        cls.lib.written.restype = ctypes.c_void_p
        cls.lib.flush_size.restype = ctypes.c_size_t
        cls.lib.trampoline_written.restype = ctypes.c_void_p
        cls.lib.continuation.restype = ctypes.c_size_t
        cls.lib.trampoline_flush_size.restype = ctypes.c_size_t
        cls.lib.exercise_request.restype = ctypes.POINTER(ctypes.c_int)

    def test_writes_absolute_tail_branch_to_writable_alias_only(self):
        self.assertTrue(self.lib.exercise(2, 16, 0x1000, 0x1100, 1, 1))
        written = ctypes.string_at(self.lib.written(), 64)
        self.assertEqual(written[:8], bytes.fromhex("5000005800021fd6"))
        self.assertEqual(written[8:16], bytes.fromhex("f0debc9a78563412"))
        self.assertEqual(written[16:], b"\xaa" * 48)
        self.assertEqual(self.lib.flush_size(), 16)

    def test_rejects_unsafe_or_missing_symbols_without_writing(self):
        for args in [(1, 64, 0x1000, 0x1100, 1, 1), (2, 8, 0x1000, 0x1100, 1, 1),
                     (2, 64, 0x1002, 0x1100, 1, 1), (2, 64, 0x1000, 0x1008, 1, 1),
                     (2, 64, 0x0ffc, 0x1100, 1, 1), (2, 64, 0x1100, 0x1100, 1, 1),
                     (2, 64, 0x1000, 0x1100, 0, 1), (2, 64, 0x1000, 0x1100, 1, 0)]:
            with self.subTest(args=args):
                self.assertFalse(self.lib.exercise(*args))
                self.assertEqual(ctypes.string_at(self.lib.written(), 64), b"\xaa" * 64)
                self.assertEqual(self.lib.flush_size(), 0)

    def test_original_prologue_and_continuation_are_retained(self):
        self.assertTrue(self.lib.exercise_hook(0, 1))
        code = ctypes.string_at(self.lib.trampoline_written(), 64)
        self.assertEqual(code[:16], bytes.fromhex("ff8301d1f65703a9f44f04a9fd7b05a9"))
        self.assertEqual(code[16:24], bytes.fromhex("5000005800021fd6"))
        self.assertEqual(int.from_bytes(code[24:32], "little"), self.lib.continuation())
        self.assertEqual(code[32:], b"\xaa" * 32)
        self.assertEqual(self.lib.trampoline_flush_size(), 32)
        self.assertEqual(self.lib.flush_size(), 16)

    def test_prologue_mismatch_and_allocation_failure_do_not_patch(self):
        for mismatch, allocate in ((1,1),(0,0)):
            self.assertFalse(self.lib.exercise_hook(mismatch, allocate))
            self.assertEqual(ctypes.string_at(self.lib.written(), 64), b"\xaa" * 64)
            self.assertEqual(self.lib.flush_size(), 0)
            self.assertEqual(self.lib.trampoline_flush_size(), 0)

    def test_resolution_request_forwards_native_size_and_original_mode(self):
        for mode in (0,1,2):
            result = self.lib.exercise_request(816,720,mode)
            self.assertEqual(list(result[:3]), [2424,1816,mode])
        self.assertEqual(list(self.lib.exercise_request(2424,1816,2)[:3]), [2424,1816,2])
        self.assertEqual(list(self.lib.exercise_request(0,0,1)[:3]), [0,0,1])
        self.assertEqual(list(self.lib.exercise_request(-1,720,0)[:3]), [-1,720,0])


if __name__ == "__main__":
    unittest.main()
