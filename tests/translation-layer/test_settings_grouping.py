#!/usr/bin/env python3
"""Protect existing per-game controls while keeping optional diagnostics organised."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAME = (ROOT / "src/app/Husk/TLAppSettings.swift").read_text()
APP = (ROOT / "src/app/Husk/SettingsTab.swift").read_text()

class SettingsGroupingTests(unittest.TestCase):
    def test_every_existing_unreal_control_is_present(self):
        # Prefer identity of the setting binding over UI label text, so renaming
        # labels won't silently delete an experimental control.
        names = [
            "unrealGraphics", "efficientResolution",
            "efficientFrameRate", "workerScheduling", "vulkanSubmission",
            "execution.prefill", "execution.commandBufferLimit",
            "execution.swapchainImages", "execution.initializationParking",
            "spatialUpscaling", "spatialInputPercent", "engineOnlyLimiter",
            "nativePipelineArchiveMode", "nativeArchiveVerification",
            "feedbackClockCorrection", "clockPresentation",
            "pipelineIdentification", "pipelineFeedback", "renderTargetInventory",
            "driverPhaseProfiling",
        ]
        for name in names:
            with self.subTest(setting=name):
                self.assertIn(f"$settings.{name}", GAME)
        # The 1%-step slider deliberately uses a clamped custom Binding rather
        # than a direct $settings binding. Assert both read and write paths.
        self.assertIn("Double(settings.customResolutionPercent)", GAME)
        self.assertIn("settings.customResolutionPercent = Int($0.rounded())", GAME)

    def test_simple_page_and_advanced_page_are_separate(self):
        self.assertIn("TLGameAdvancedSettingsView(settings: $settings, appID: app.id)", GAME)
        simple, advanced = GAME.split("private struct TLGameAdvancedSettingsView: View", 1)
        self.assertIn('Text("Game Graphics")', simple)
        self.assertIn('Text("Upscaling & Rendering")', advanced)
        self.assertIn('Text("Frame Pacing & CPU")', advanced)
        self.assertIn('Text("Vulkan & GPU Queues")', advanced)
        self.assertIn('Text("Pipeline Cache & Diagnostics")', advanced)
        self.assertIn('Text("General Game Diagnostics")', advanced)
        self.assertIn('.onChange(of: settings) { $0.save(appID) }', advanced)
        self.assertIn("EfficiencyDiagnosticsView()", advanced)
        self.assertIn("EfficiencyMetricKitView()", advanced)
        self.assertIn("EfficiencyProfilesView(settings: $settings", simple)

    def test_general_diagnostics_grouped_outside_about(self):
        self.assertIn('row(HuskDiagnosticsSettings()', APP)
        general = APP.split("struct HuskDiagnosticsSettings: View", 1)[1].split("struct AboutSettings: View", 1)[0]
        for name in ("Open Console", "Developer Info", "Device Checks", "Mass Test",
                     "Delayed OS Reports (MetricKit)", "Crash Reports"):
            with self.subTest(tool=name):
                self.assertIn(name, general)
        about = APP.split("struct AboutSettings: View", 1)[1]
        self.assertNotIn("Button { showLogs", about)
        self.assertNotIn("Toggle(isOn: $devInfo)", about)

if __name__ == "__main__":
    unittest.main()
