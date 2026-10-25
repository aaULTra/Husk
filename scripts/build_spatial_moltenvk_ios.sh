#!/bin/bash
# Build a separate experimental driver. Never replace the protected donor framework.
set -euo pipefail
HUSK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIN=db66022459ffb663aa2b50f6b018bc2e124f5edf
SRC="$HUSK_ROOT/third_party/build/MoltenVK-1.4.2-spatial"
OUT="$HUSK_ROOT/build/ios-arm64/lib/HuskMoltenVK.framework"
mkdir -p "$HUSK_ROOT/third_party/build"
if [ ! -d "$SRC/.git" ]; then
    git clone --depth 1 --branch v1.4.2 https://github.com/KhronosGroup/MoltenVK "$SRC"
fi
test "$(git -C "$SRC" rev-parse HEAD)" = "$PIN"
# Clean only this dedicated disposable build tree to make reruns deterministic.
git -C "$SRC" restore MoltenVK/MoltenVK/GPUObjects/MVKImage.h MoltenVK/MoltenVK/GPUObjects/MVKImage.mm MoltenVK/MoltenVK/GPUObjects/MVKSwapchain.h MoltenVK/MoltenVK/GPUObjects/MVKSwapchain.mm MoltenVK/MoltenVK.xcodeproj/project.pbxproj
python3 "$HUSK_ROOT/scripts/prepare_spatial_driver.py" "$SRC"
cd "$SRC"
SPVC_REV="$(cat ExternalRevisions/SPIRV-Cross_repo_revision)"
SPVC="$HUSK_ROOT/third_party/build/SPIRV-Cross-spatial-$SPVC_REV"
if [ ! -d "$SPVC/.git" ]; then
    git clone https://github.com/KhronosGroup/SPIRV-Cross "$SPVC"
    git -C "$SPVC" checkout -q "$SPVC_REV"
fi
test "$(git -C "$SPVC" rev-parse HEAD)" = "$SPVC_REV"
for patch in "$HUSK_ROOT"/patches/husk-spirv-cross-*.patch; do
    git -C "$SPVC" apply --reverse --check "$patch" 2>/dev/null || git -C "$SPVC" apply "$patch"
done
./fetchDependencies --ios --spirv-cross-root "$SPVC"
make ios
SOURCE="$SRC/Package/Release/MoltenVK/dynamic/MoltenVK.xcframework/ios-arm64/MoltenVK.framework"
test -s "$SOURCE/MoltenVK"
rm -rf "$OUT"
mkdir -p "$(dirname "$OUT")"
cp -R "$SOURCE" "$OUT"
mv "$OUT/MoltenVK" "$OUT/HuskMoltenVK"
/usr/libexec/PlistBuddy -c "Set :CFBundleExecutable HuskMoltenVK" "$OUT/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleName HuskMoltenVK" "$OUT/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier com.husk.experimental.MoltenVK" "$OUT/Info.plist"
install_name_tool -id @rpath/HuskMoltenVK.framework/HuskMoltenVK "$OUT/HuskMoltenVK"
codesign --remove-signature "$OUT/HuskMoltenVK" 2>/dev/null || true
cp "$SRC/HuskSpatialBuild.json" "$OUT/"
nm -gU "$OUT/HuskMoltenVK" | grep -E '_vkHuskSpatialConfigure$'
nm -gU "$OUT/HuskMoltenVK" | grep -E '_vkHuskSpatialSnapshot$'
test -s "$HUSK_ROOT/build/ios-arm64/lib/MoltenVK.framework/MoltenVK"
echo "M9-SPATIAL separate driver built; original donor framework preserved"

# Add this optional framework only in this build workspace; normal source builds
# keep their original dependencies and safely decline the unavailable option.
python3 - "$HUSK_ROOT/src/app/project.yml" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
dependency='''      - framework: ../../build/ios-arm64/lib/HuskMoltenVK.framework
        embed: true
        codeSign: true
        link: false
'''
anchor='      # The PS4 layer: Bachata-S4'
if 'framework: ../../build/ios-arm64/lib/HuskMoltenVK.framework' not in s:
    if s.count(anchor)!=1:raise SystemExit("Unexpected project embedding layout")
    p.write_text(s.replace(anchor,dependency+anchor))
PY
