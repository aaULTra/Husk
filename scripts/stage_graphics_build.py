#!/usr/bin/env python3
"""Stage official Husk 3.1 resources with the protected QEMU library for a source rebuild on macOS.

The app executable and all translation-layer code are rebuilt from this checkout.
The QEMU/ANGLE/MoltenVK/PS4 libraries are reused without modification. This avoids
requiring the upstream developer's unpublished PS4 build trees. Does not fetch
anything; the caller supplies the checksum-pinned official release IPA.
"""
import hashlib
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SHA256 = "650c062c774ee87debee2c96bb9c921125ff642a814a85a6718dc5e7db2e45cc"
QEMU_BASE_SHA256 = "112a1ddbb3143ae25e80c18c5b195b6dfa5067d66cbf99d2188fc03f4ab0f61d"


def stage(ipa, qemu_base):
    if hashlib.sha256(ipa.read_bytes()).hexdigest() != SHA256:
        raise SystemExit("Official Husk 3.1 IPA checksum mismatch; refusing to stage")
    if hashlib.sha256(qemu_base.read_bytes()).hexdigest() != QEMU_BASE_SHA256:
        raise SystemExit("Protected Husk 3.0 QEMU donor checksum mismatch; refusing to stage")
    destination = ROOT / "build/graphics-base"
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ipa) as archive:
        for entry in archive.infolist():
            if not (destination / entry.filename).resolve().is_relative_to(destination.resolve()):
                raise SystemExit("Unsafe archive path")
        archive.extractall(destination)
    apps = list((destination / "Payload").glob("*.app"))
    if len(apps) != 1:
        raise SystemExit("Expected exactly one app in the official IPA")
    app = apps[0]
    frameworks = app / "Frameworks"
    copies = {
        "libANGLE-shared.dylib": "build/ios-arm64/sysroot/lib/libANGLE-shared.dylib",
        "libhuskps4.dylib": "build/ios-arm64/lib/libhuskps4.dylib",
        "MoltenVK.framework": "build/ios-arm64/lib/MoltenVK.framework",
    }
    for name, target in copies.items():
        source = frameworks / name
        target = ROOT / target
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            shutil.copy2(source, target)
    # QEMU changed in3.1; retain the currently tested JIT/guest baseline while
    # using3.1's matching Java resources. ANGLE/MoltenVK/PS4 file-backed
    # sections were independently verified identical to the protected donor.
    target = ROOT / "build/ios-arm64/lib/libqemu-aarch64-softmmu.dylib"
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(qemu_base) as baseline:
        target.write_bytes(baseline.read("Payload/Husk.app/Frameworks/libqemu-aarch64-softmmu.dylib"))
    # Regenerated only in the build workspace. Existing StikJIT headers/modules
    # remain in the repo; the original release's unrelated app binary is unused.
    project = ROOT / "src/app/project.yml"
    text = project.read_text()
    old = "../../build/ios-arm64/lib/MoltenVK.xcframework"
    if text.count(old) != 1:
        raise SystemExit("Unexpected MoltenVK dependency; inspect project.yml")
    text = text.replace(old, "../../build/ios-arm64/lib/MoltenVK.framework")
    start = text.index("    preBuildScripts:\n")
    stop = text.index("    postBuildScripts:\n", start)
    # Stage data/firmware from the exact donor release instead of bootstrapping a
    # whole Android image. Never copy the donor's executable, plist, or plugins.
    script = '''    preBuildScripts:
      - name: Stage official release resources
        script: |
          set -eu
          SRC="$SRCROOT/../../build/graphics-base/Payload/Husk.app"
          DST="$BUILT_PRODUCTS_DIR/$UNLOCALIZED_RESOURCES_FOLDER_PATH"
          test -d "$SRC"
          mkdir -p "$DST"
          rsync -a --exclude=Frameworks --exclude=PlugIns --exclude=Info.plist --exclude=Husk --exclude=Assets.car --exclude=_CodeSignature --exclude=embedded.mobileprovision "$SRC/" "$DST/"
        basedOnDependencyAnalysis: false

'''
    if app.name != "Husk.app":
        raise SystemExit("Unexpected official app name")
    project.write_text(text[:start] + script + text[stop:])
    print("Staged checksum-verified Husk 3.1 resources/protected QEMU; the app will be rebuilt from source")


if __name__ == "__main__":
    stage(Path(sys.argv[1]), Path(sys.argv[2]))
