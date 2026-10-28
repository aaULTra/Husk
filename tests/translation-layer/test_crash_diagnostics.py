#!/usr/bin/env python3
"""Regression test: fatal crash record survives a terminated process on the macOS CI host."""
import os
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/translation-layer-next/husk-tl-crash-signal.c"
HEADER_DIR = ROOT / "src/translation-layer-next"
TEST_PROGRAM = r"""
#include "husk-tl-crash-signal.h"
#include <fcntl.h>
#include <signal.h>
#include <unistd.h>
#include <string.h>
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    int fd = open(argv[1], O_CREAT | O_TRUNC | O_WRONLY, 0600);
    if (fd < 0) return 3;
    husk_crash_report_sink(fd);
    if (husk_crash_install(-1, -1) != 5) return 4;
    /* A JIT-owned signal must not be intercepted by the generic handler. */
    struct sigaction action = {0};
    if (sigaction(SIGTRAP, NULL, &action) != 0 || action.sa_handler != SIG_DFL) return 5;
    raise(SIGABRT);
    return 6;
}
"""

class CrashDiagnosticsTest(unittest.TestCase):
    def test_fatal_signal_writes_independent_durable_record(self):
        with tempfile.TemporaryDirectory() as directory:
            test_c = Path(directory) / "test.c"
            executable = Path(directory) / "test-crash-handler"
            evidence = Path(directory) / "fatal-signal.txt"
            test_c.write_text(TEST_PROGRAM, encoding="utf-8")
            subprocess.run(
                ["clang", "-std=c11", "-Wall", "-Wextra", "-pthread",
                 "-I", str(HEADER_DIR), str(SOURCE), str(test_c), "-o", str(executable)],
                check=True, capture_output=True, text=True,
            )
            result = subprocess.run([str(executable), str(evidence)], capture_output=True, text=True)
            self.assertEqual(result.returncode, -signal.SIGABRT,
                             f"signal handler must re-raise SIGABRT, got {result.returncode}: {result.stderr}")
            record = evidence.read_text(encoding="utf-8")
            self.assertIn("*** FATAL SIGNAL 6", record)
            self.assertIn("process terminating", record)

if __name__ == "__main__":
    unittest.main()
