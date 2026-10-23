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
        start = source.index("bool tl_ld_replace_function(")
        routine = source[start:source.index("\n}\n", start) + 3]
        harness = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
typedef struct { uint8_t st_info; uint64_t st_size, st_value; } elf_sym;
typedef struct { int ncode; struct { uint64_t start, end; } code[1]; } tl_lib;
static unsigned char rx[64], rw[64];
static elf_sym symbol;
static bool found, executable;
static size_t flushed;
static const elf_sym *lib_find(tl_lib *l, const char *n) { (void)l; (void)n; return found ? &symbol : NULL; }
static void *sym_value(tl_lib *l, const elf_sym *s) { (void)l; (void)s; return rx; }
static bool tl_xmem_is_rx(const void *p) { return executable && p == rx; }
static ptrdiff_t tl_xmem_delta(void) { return (intptr_t)rw - (intptr_t)rx; }
static void tl_xmem_flush(void *p, size_t n) { if (p == rx) flushed = n; }
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


if __name__ == "__main__":
    unittest.main()
