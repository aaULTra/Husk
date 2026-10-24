#!/usr/bin/env python3
"""Exercise the real portable preset code against temporary game directories."""
import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class GraphicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        library = Path(cls.build.name) / "graphics.so"
        subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra", "-Werror",
                        "-shared", "-fPIC", str(ROOT / "src/translation-layer-next/husk-tl-ue4-graphics.c"),
                        "-o", str(library)], check=True)
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.tl_ue4_resolution_fraction.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_int]
        cls.lib.tl_ue4_resolution_fraction.restype = ctypes.c_double
        cls.lib.husk_ue4_set_sharp_graphics.argtypes = [ctypes.c_bool]
        cls.lib.husk_ue4_set_efficiency.argtypes = [ctypes.c_bool, ctypes.c_int]
        cls.lib.tl_ue4_effective_frame_limit.argtypes = [ctypes.c_int]
        cls.lib.tl_ue4_frame_delay_ns.argtypes = [ctypes.c_int64, ctypes.c_int, ctypes.POINTER(ctypes.c_int64)]
        cls.lib.tl_ue4_frame_delay_ns.restype = ctypes.c_int64
        cls.lib.tl_ue4_graphics_prepare.argtypes = [ctypes.c_char_p] * 3
        cls.lib.tl_ue4_graphics_prepare.restype = ctypes.c_bool
        cls.lib.tl_ue4_graphics_command_line.argtypes = [ctypes.c_char_p]
        cls.lib.tl_ue4_graphics_command_line.restype = ctypes.c_void_p
        cls.lib.tl_ue4_graphics_command_asset.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t]
        cls.lib.tl_ue4_graphics_command_asset.restype = ctypes.c_void_p
        cls.lib.tl_ue4_graphics_command_file.argtypes = [ctypes.c_char_p]
        cls.lib.tl_ue4_graphics_command_file.restype = ctypes.c_void_p
        cls.libc = ctypes.CDLL(None)
        cls.libc.free.argtypes = [ctypes.c_void_p]

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.roots = [Path(self.tmp.name) / name for name in ("files", "external")]
        self.paths = [root / "UE4Game/Dungeons/Dungeons/Saved/Config" / platform / "Engine.ini"
                      for root in self.roots for platform in ("Android", "Android_Vulkan")]
        self.lib.husk_ue4_set_sharp_graphics(False)
        self.lib.husk_ue4_set_efficiency(False, 60)

    def prepare(self, project=b"Dungeons"):
        return self.lib.tl_ue4_graphics_prepare(*(os.fsencode(p) for p in self.roots), project)

    def test_resolution_budget_preserves_aspect_and_is_orientation_independent(self):
        f = self.lib.tl_ue4_resolution_fraction
        for tablet in (False, True):
            for w, h in ((2752, 2064), (2400, 1800), (2400, 1080), (1280, 720)):
                scale = f(w, h, tablet, 0)
                self.assertGreater(scale, 0)
                self.assertLessEqual(scale, 1)
                self.assertEqual(scale, f(h, w, tablet, 0))
                self.assertLessEqual(max(w, h) * scale, 2304 if tablet else 2048)
                self.assertLessEqual(min(w, h) * scale, 1600 if tablet else 1280)

    def test_resolution_budget_retains_more_detail_on_tablet_and_never_upscales(self):
        f = self.lib.tl_ue4_resolution_fraction
        self.assertGreater(f(2752, 2064, True, 0), f(2752, 2064, False, 0))
        self.assertEqual(f(1280, 720, False, 0), 1)
        self.assertEqual(f(0, 720, True, 0), 1)
        self.assertEqual(f(-1, 720, False, 0), 1)
        self.assertEqual(f(2400, 1800, False, -1), f(2400, 1800, False, 0))

    def test_manual_resolution_allows_repeatable_native_comparisons(self):
        f = self.lib.tl_ue4_resolution_fraction
        for percent in range(65, 101):
            self.assertEqual(f(2752, 2064, True, percent), percent / 100)
            self.assertEqual(f(2400, 1800, False, percent), percent / 100)

    def command(self, base):
        p = self.lib.tl_ue4_graphics_command_line(base)
        self.assertTrue(p)
        try:
            return ctypes.string_at(p).decode()
        finally:
            self.libc.free(p)

    def test_default_does_not_create_configs_and_preserves_arguments(self):
        self.assertTrue(self.prepare())
        self.assertFalse(any(p.exists() for p in self.paths))
        self.assertEqual(self.command(b"-vulkan -custom=1"), "-vulkan -custom=1")
        self.assertEqual(self.command(None), "")

    def test_enable_repeat_disable_preserves_original_bytes(self):
        for original in (b"", b"[Custom]\nValue=7", b"[Custom]\r\nValue=7\r\n", b"\n\n"):
            with self.subTest(original=original):
                for p in self.paths:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(original)
                self.lib.husk_ue4_set_sharp_graphics(True)
                self.assertTrue(self.prepare())
                first = [p.read_bytes() for p in self.paths]
                self.assertIn(b"r.MobileContentScaleFactor=0", first[0])
                self.assertIn(b"r.MaxAnisotropy=16", first[0])
                self.assertNotIn(b"r.TextureStreaming=0", first[0])
                self.assertTrue(self.prepare())
                self.assertEqual(first, [p.read_bytes() for p in self.paths])
                self.lib.husk_ue4_set_sharp_graphics(False)
                self.assertTrue(self.prepare())
                for p in self.paths:
                    self.assertEqual(p.read_bytes() if p.exists() else b"", original)

    def test_disable_preserves_later_unrelated_game_settings_and_saves(self):
        save = self.roots[0] / "character.sav"
        save.parent.mkdir(parents=True)
        save.write_bytes(b"GVAS-character")
        self.lib.husk_ue4_set_sharp_graphics(True)
        self.assertTrue(self.prepare())
        p = self.paths[0]
        with p.open("ab") as f:
            f.write(b"[AddedByGame]\nVolume=5\n")
        self.lib.husk_ue4_set_sharp_graphics(False)
        self.assertTrue(self.prepare())
        self.assertEqual(p.read_bytes(), b"[AddedByGame]\nVolume=5\n")
        self.assertEqual(save.read_bytes(), b"GVAS-character")

    def test_malformed_marker_and_io_error_report_failure_without_truncation(self):
        p = self.paths[0]
        p.parent.mkdir(parents=True)
        original = b"[Custom]\n; BEGIN HUSK SHARP GRAPHICS v1\nDoNotLose=1"
        p.write_bytes(original)
        self.lib.husk_ue4_set_sharp_graphics(True)
        self.assertFalse(self.prepare())
        self.assertEqual(p.read_bytes(), original)
        p.unlink()
        p.mkdir()
        self.assertFalse(self.prepare())

    def test_rejects_project_path_traversal(self):
        self.lib.husk_ue4_set_sharp_graphics(True)
        for name in (b"../Other", b"..", b".", b"", b"Bad/Name", b"Bad\\Name"):
            self.assertFalse(self.prepare(name))
        self.assertFalse(any(p.exists() for p in self.paths))

    def test_arguments_keep_existing_flags_and_use_config_not_console_execution(self):
        self.lib.husk_ue4_set_sharp_graphics(True)
        args = self.command(b"-vulkan -custom=1")
        self.assertTrue(args.startswith("-vulkan -custom=1 -mcsf=0 -ini:Engine:"))
        self.assertIn("[SystemSettings]:r.ScreenPercentage=100", args)
        self.assertIn("[SystemSettings]:r.DepthOfFieldQuality=0", args)
        self.assertNotIn("ExecCmds", args)

    def test_efficient_switch_keeps_native_detail_and_restores_original_config(self):
        original = b"[User]\r\nSound=7\r\n"
        for p in self.paths:
            p.parent.mkdir(parents=True)
            p.write_bytes(original)
        self.lib.husk_ue4_set_sharp_graphics(True)
        self.assertTrue(self.prepare())
        self.lib.husk_ue4_set_efficiency(True, 60)
        self.assertTrue(self.prepare())
        args = self.command(b"-vulkan")
        for item in ("r.ScreenPercentage=100", "r.MobileContentScaleFactor=0", "sg.TextureQuality=3",
                     "r.Streaming.MipBias=0", "r.PostProcessAAQuality=4", "r.MaxAnisotropy=8",
                     "r.Shadow.MaxResolution=1024", "r.Shadow.CSM.MaxCascades=2", "t.MaxFPS=60"):
            self.assertIn(item, args)
            for p in self.paths:
                self.assertIn(item.encode(), p.read_bytes())
        self.assertNotIn("r.Shadow.MaxResolution=2048", args)
        first = [p.read_bytes() for p in self.paths]
        self.assertTrue(self.prepare())
        self.assertEqual(first, [p.read_bytes() for p in self.paths])
        self.lib.husk_ue4_set_sharp_graphics(False)
        self.assertTrue(self.prepare())
        self.assertEqual([p.read_bytes() for p in self.paths], [original] * 4)
        self.assertEqual(self.command(b"-custom"), "-custom")

    def test_frame_limit_is_scoped_and_responds_to_heat(self):
        self.lib.husk_ue4_set_efficiency(True, 60)
        self.assertEqual(self.lib.tl_ue4_effective_frame_limit(0), 0)
        self.lib.husk_ue4_set_sharp_graphics(True)
        self.assertEqual([self.lib.tl_ue4_effective_frame_limit(i) for i in range(4)], [60, 60, 30, 20])
        self.lib.husk_ue4_set_efficiency(True, 30)
        self.assertEqual([self.lib.tl_ue4_effective_frame_limit(i) for i in range(4)], [30, 30, 30, 20])
        self.lib.husk_ue4_set_efficiency(False, 60)
        self.assertEqual(self.lib.tl_ue4_effective_frame_limit(3), 0)

    def test_frame_pacer_sleeps_only_remaining_budget_and_does_not_catch_up(self):
        deadline = ctypes.c_int64()
        delay = lambda now, fps=60: self.lib.tl_ue4_frame_delay_ns(now, fps, ctypes.byref(deadline))
        start = 1000000000
        self.assertEqual(delay(start), 0)
        self.assertEqual(delay(start + 5000000), 11666666)
        self.assertEqual(delay(start + 21000000), 12333332)
        # Long GPU frame and background/resume never cause a catch-up burst.
        self.assertEqual(delay(start + 100000000), 0)
        self.assertEqual(delay(start + 10000000000), 0)
        self.assertEqual(delay(start + 10005000000), 11666666)
        self.assertEqual(delay(start + 10005000000, 0), 0)
        self.assertEqual(deadline.value, 0)

    def test_frame_pacer_targets_sixty_with_varying_work_below_budget(self):
        deadline = ctypes.c_int64()
        now = 1000000000
        timestamps = []
        for i in range(601):
            now += (4 + i % 9) * 1000000  # 4–12 ms of simulated game work
            now += self.lib.tl_ue4_frame_delay_ns(now, 60, ctypes.byref(deadline))
            timestamps.append(now)
        self.assertAlmostEqual(600 * 1e9 / (timestamps[-1] - timestamps[0]), 60, places=4)

    def owned(self, p):
        self.assertTrue(p)
        try:
            return ctypes.string_at(p).decode()
        finally:
            self.libc.free(p)

    def test_startup_asset_keeps_project_and_replaces_old_scale_flag(self):
        self.lib.husk_ue4_set_sharp_graphics(True)
        base = b'"../../../Dungeons/My Project.uproject" -vulkan -mcsf=1 -custom=7\r\n'
        args = self.owned(self.lib.tl_ue4_graphics_command_asset(b"UE4CommandLine.txt", base, len(base)))
        self.assertIn('"../../../Dungeons/My Project.uproject"', args)
        self.assertIn("-vulkan", args)
        self.assertIn("-custom=7", args)
        self.assertNotIn("-mcsf=1", args)
        self.assertEqual(args.lower().count("mcsf="), 1)
        self.assertIn("-mcsf=0", args)
        self.assertNotIn("\n", args)

    def test_startup_overlay_is_scoped_and_handles_absent_asset(self):
        self.assertFalse(self.lib.tl_ue4_graphics_command_asset(b"UE4CommandLine.txt", None, 0))
        self.lib.husk_ue4_set_sharp_graphics(True)
        self.assertFalse(self.lib.tl_ue4_graphics_command_asset(b"OtherAsset.txt", b"x", 1))
        self.assertFalse(self.lib.tl_ue4_graphics_command_asset(b"UE4CommandLine.txt", b"a\0b", 3))
        self.assertFalse(self.lib.tl_ue4_graphics_command_asset(b"UE4CommandLine.txt", b"x" * 16000, 16000))
        self.assertIn("-mcsf=0", self.owned(self.lib.tl_ue4_graphics_command_asset(b"UE4CommandLine.txt", None, 0)))

    def test_external_startup_overlay_preserves_file_and_first_line_semantics(self):
        p = Path(self.tmp.name) / "ue4commandline.txt"
        original = b'../../../Dungeons/Dungeons.uproject -mcsf=2 -custom=9\nignored-second-line\n'
        p.write_bytes(original)
        self.assertFalse(self.lib.tl_ue4_graphics_command_file(os.fsencode(p)))
        self.lib.husk_ue4_set_sharp_graphics(True)
        args = self.owned(self.lib.tl_ue4_graphics_command_file(os.fsencode(p)))
        self.assertIn("Dungeons.uproject", args)
        self.assertIn("-custom=9", args)
        self.assertNotIn("mcsf=2", args)
        self.assertNotIn("ignored-second-line", args)
        self.assertNotIn("\n", args)
        self.assertEqual(p.read_bytes(), original)
        p.unlink()
        self.assertFalse(self.lib.tl_ue4_graphics_command_file(os.fsencode(p)))

    def test_scale_flag_removal_respects_quotes_and_case(self):
        self.lib.husk_ue4_set_sharp_graphics(True)
        args = self.command(b'"a path/mcsf=1.uproject" "-MCSF=2" mcsf=1 -keep="two words"')
        self.assertIn('"a path/mcsf=1.uproject"', args)
        self.assertIn('-keep="two words"', args)
        self.assertNotIn('"-MCSF=2"', args)
        self.assertNotIn(" mcsf=1 ", args)


if __name__ == "__main__":
    unittest.main()
