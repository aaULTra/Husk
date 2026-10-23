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
generated INI handling. The v2 device log showed native 2752x2064 at startup,
then a later 816x720 swapchain while the host stayed 2752x2064. Startup worked,
but gameplay did not remain at native resolution.

V3 additionally replaces the exported `FAndroidWindow::GetScreenRect` function
for project `Dungeons` with Sharp enabled. Both known UE4 signatures are looked
up by name. Every query returns the launch surface rounded down to multiples of
eight, as UE4 Android normally requires. The change affects the engine window
query upstream of rendering-target creation; it does not enlarge Vulkan's
swapchain behind the engine's back. Installation runs before engine threads
start and requires an exported function with at least 16 bytes in an executable
section. The code cache is flushed. An unavailable export leaves the startup
path active and produces a diagnostic. Game Default and other projects skip it.

The v3 log confirmed installation and calls returning 2424x1816, followed by
another 816x720 swapchain. The later resize therefore is not constrained by the
Android window query.

V4 additionally hooks `FSystemResolution::RequestResolutionChange(int,int,
EWindowMode::Type)`. The supplied Dungeons `libUE4.so`, ELF build ID
`2b5d2a005213e32589cdd34f53882fe49e02cd4f`, contains this function at virtual
address `0xb203870`, size 424. Disassembly confirms direct calls from
`UGameUserSettings::ApplyResolutionSettings` at `0xac14c38` and
`UGameViewportClient::HandleSetResCommand` at `0xac240b8`.
`UGameUserSettings::ApplySettings` calls `ApplyResolutionSettings` directly at
`0xac14d84`; the game's user-settings initializer calls the settings object's
virtual apply method independently of Android's window query.

The hook logs positive incoming resolution requests, replaces differing sizes
with the native launch size, and calls the original function. Window mode,
original CVar priority and resize/delegate logic are preserved. Nonpositive
requests pass through unchanged. No APK or game-save bytes are changed. Exact
symbol lookup and the existing executable-section guards are followed by a
16-byte prologue comparison. The reviewed instructions only adjust the stack
and store callee-saved registers; none is PC relative or uses x16. A trampoline
executes them once and jumps back to the original function after those bytes.
Unexpected code or allocation failure leaves the function unmodified and logs
that the v4 override is unavailable. Installation happens before engine startup.

Further disassembly confirms that the game's `ExecuteResolutionCommand` builds
the literal `r.SetRes ` (string at `0x595eb35`) and invokes a controller method.
That direct CVar path can bypass `RequestResolutionChange`.
`SystemResolutionSinkCallback` calls `ParseResolution` at `0xb1e7fb0`, targeting
`0xb1e612c`, size 1480. V4 hooks this parser too, using its independently verified
stack-store prologue. It calls the original parser first, preserves validity
and parsed window mode, and changes only valid positive dimensions. Failed or
zero-size parses retain their outputs. This covers both engine requests and
the direct CVar path actually present in the game library. It logs
`parsed resolution v4 ... -> ...` when a parsed size changes.

The provided log alone does not establish that a particular caller caused the
816x720 switch. Device validation must show the v4 request/parser logs and native
presentation after gameplay loads and resume. A direct viewport resize could
still bypass these paths. The PR remains a draft pending this check.

Source references: Epic's UE4.26 Android window implementation at
https://github.com/CFHH/UnrealEngine-4.26/blob/main/Engine/Source/Runtime/ApplicationCore/Private/Android/AndroidWindow.cpp
and the older no-argument signature at
https://github.com/folgerwang/UnrealEngine/blob/release/Engine/Source/Runtime/ApplicationCore/Private/Android/AndroidWindow.cpp.

The log records the **requested** preset and surface dimensions, and explicitly
logs when the startup asset/external file is served with `-mcsf=0`. Vulkan's
existing swapchain log records the actual presentation dimensions, which do not
alone prove the internal 3D scene resolution. None of these messages claims that
all CVars took effect. Some packaged games ignore generated INIs or command-line
overrides, or contain fewer texture/shader variants than the PC build. There is
no guarantee of PC-equivalent graphics or unchanged frame rate without testing
the actual APK on the device.

## Validation and build

Run `python3 tests/translation-layer/test_ue4_graphics.py -v` and
`python3 tests/translation-layer/test_ue4_resolution_hook.py -v`. The latter
checks the actual loader patch routines' bounds, function-type and executable
memory guards, writable-alias writes, prologue mismatch and allocation failures,
trampoline continuation, cache flush sizes and native request forwarding with
mode preservation, and parser validity/zero-size handling. There are 16 portable
tests total. Local ARM64 emulation
also verified the supplied game's displaced prologue and stack/register state
when executing the trampoline back into the original function.
The former compiles the real
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
