# Minecraft Dungeons graphics preset

In Dungeons' settings, **Game Graphics > Graphics** offers **Automatic**,
**Game Default**, and **Sharp / High Quality**. Automatic selects Sharp / High
Quality only for a UE4 game identified by its Minecraft Dungeons label or a
package name containing `dungeons`. Other games retain their defaults. The
explicit preset also works if a particular APK has an unrecognised name.

Close Husk completely and reopen after changing the preset. The preset uses the
screen's native scale in both full-screen and windowed launch paths. On a 2x
iPad, High and Native have the same surface size; the Unreal settings below are
the additional change. Enlarging a window after launch still scales its original
surface, as before; use full screen at launch for the sharpest full-screen result.

The preset requests 100% rendering, native Android content scale, no dynamic
resolution, quality level 3 for the standard UE4 scalability groups, 16x
anisotropic filtering, zero streaming mip bias, high-quality anti-aliasing and
shadows up to 2048, with motion blur, depth of field and chromatic aberration off.
It preserves texture streaming and does not set an unlimited texture pool. It
does not force a new feature level, renderer, HDR mode or material permutation.

Overrides are appended to the game's generated Engine.ini in marked blocks in
the internal/external UE4Game project roots, for Android and Android_Vulkan.
Unreal launch arguments also carry `-ini:Engine:` overrides, preserving existing
`TL_UE4_CMDLINE` flags. The v2 startup path overlays the actual NDK
`UE4CommandLine.txt` asset read, or an existing external command-line file when
opened read-only, to add `-mcsf=0`. It preserves project arguments, replaces old
`mcsf` flags and leaves the APK/external command file unchanged. The asset's
descriptor path is disabled for this synthetic text so it cannot return the
original unmodified bytes instead. This does not rely on ExecCmds.
Selecting Game Default removes only these blocks on the next launch, preserving
unrelated configuration and character saves. A malformed block is left intact
and a preparation failure is logged instead of truncating the file.

The v1 build only supplied launch arguments through a Java callback that stock
UE4 Android startup does not use. A device log showed a 1566x1300 host surface
but an 864x720 Vulkan swapchain. The v2 change supplies text through the
startup route implemented in Epic's Android `InitCommandLine`, and uses the
direct `mcsf` option read by `FAndroidWindow::GetScreenRect`, independently of
generated INI handling. The actual APK still needs a new on-device log to
establish the result.

The log records the **requested** preset and surface dimensions, and explicitly
logs when the startup asset/external file is served with `-mcsf=0`. Vulkan's
existing swapchain log records the actual presentation dimensions, which do not
alone prove the internal 3D scene resolution. None of these messages claims that
all CVars took effect. Some packaged games ignore generated INIs or command-line
overrides, or contain fewer texture/shader variants than the PC build. There is
no guarantee of PC-equivalent graphics or unchanged frame rate without testing
the actual APK on the device.

## Validation and build

Run `python3 tests/translation-layer/test_ue4_graphics.py -v`. It compiles the real
portable C module with warnings as errors, then checks argument preservation,
repeat application, byte-for-byte config restoration, preservation of unrelated
later game changes and character data, and invalid inputs / I/O failures.

**Build Dungeons Graphics IPA** in Actions rebuilds Husk's app and translation
layer from this branch using Xcode. To avoid upstream's unpublished PS4 build
trees, it stages the unchanged QEMU/ANGLE/MoltenVK/PS4 libraries and resources
from official Husk 3.0, verified against SHA-256
`112a1ddbb3143ae25e80c18c5b195b6dfa5067d66cbf99d2188fc03f4ab0f61d`.
On-device pairing is rebuilt from the existing locked Rust crate. The resulting
artifact is **Husk-Dungeons-Sharp**; it contains an IPA to sign with the usual
sideloading method. Its bundle identifiers remain those already used by Husk.

Device validation: use the same scene and camera position, compare Game Default
and Sharp after a complete restart, inspect texture detail and motion, and check
performance after the device has warmed up. The host tests verify configuration
handling; only this device comparison verifies the visual improvement.
