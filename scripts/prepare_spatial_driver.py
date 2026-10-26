#!/usr/bin/env python3
"""Exact source-pinned transforms; refuse drift rather than guessing offsets."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
PIN="db66022459ffb663aa2b50f6b018bc2e124f5edf"
ROOT=Path(__file__).resolve().parents[1]
REPLACEMENTS={
  "MVKSwapchain.h": [
    [
      "#import <Metal/Metal.h>",
      "#import <Metal/Metal.h>\n#include \"HuskSpatialDriver.h\""
    ],
    [
      "\tVkExtent2D _imageExtent = {0, 0};",
      "\tVkExtent2D _imageExtent = {0, 0};\n\ttl_spatial_config _huskSpatial = {};"
    ]
  ],
  "MVKImage.h": [
    [
      "#import <IOSurface/IOSurfaceRef.h>",
      "#import <IOSurface/IOSurfaceRef.h>\n#include \"HuskSpatialDriver.h\""
    ],
    [
      "\tid<MTLTexture> _mtlTextureHeadless = nil;",
      "\tid<MTLTexture> _mtlTextureHeadless = nil;\n\tvoid* _huskSpatialImage = nullptr;"
    ]
  ],
  "MVKSwapchain.mm": [
    [
      "using namespace std;",
      "using namespace std;\n#include \"HuskSpatial.inc\""
    ],
    [
      "\tinitCAMetalLayer(pCreateInfo, pScalingInfo, imgCnt);",
      "    int spatial=huskSpatialPlan(pCreateInfo,&_huskSpatial);\n    if(spatial<0||(spatial&&isHeadless())){\n        setConfigurationResult(reportError(VK_ERROR_FORMAT_NOT_SUPPORTED,\"Husk M9: unsupported spatial swapchain; disable experiment and restart\"));\n        return;\n    }\n    if(spatial){_isDeliberatelyScaled=true;}\n\tinitCAMetalLayer(pCreateInfo, pScalingInfo, imgCnt);"
    ],
    [
      "oldSwapchain && mvkVkExtent2DsAreEqual(pCreateInfo->imageExtent, prevSurfaceExtent)",
      "oldSwapchain && (mvkVkExtent2DsAreEqual(pCreateInfo->imageExtent, prevSurfaceExtent) || _huskSpatial.enabled || oldSwapchain->_huskSpatial.enabled)"
    ],
    [
      "mtlLayer.drawableSize = mvkCGSizeFromVkExtent2D(_imageExtent);",
      "mtlLayer.drawableSize = _huskSpatial.enabled ? CGSizeMake(_huskSpatial.output_width,_huskSpatial.output_height) : mvkCGSizeFromVkExtent2D(_imageExtent);"
    ],
    [
      "\n\tif (pCreateInfo->compositeAlpha != VK_COMPOSITE_ALPHA_INHERIT_BIT_KHR)",
      "\n\tif (_huskSpatial.enabled) { mtlLayer.framebufferOnly = NO; }\n\n\tif (pCreateInfo->compositeAlpha != VK_COMPOSITE_ALPHA_INHERIT_BIT_KHR)"
    ],
    [
      "\t\t_presentableImages.push_back(_device->createPresentableSwapchainImage(&imgInfo, this, imgIdx, nullptr));",
      "\t\t_presentableImages.push_back(_device->createPresentableSwapchainImage(&imgInfo, this, imgIdx, nullptr));\n\t\tif (_huskSpatial.enabled) { setConfigurationResult(_presentableImages.back()->getConfigurationResult()); }"
    ]
  ],
  "MVKImage.mm": [
    [
      "\treturn _mtlTextureHeadless ? _mtlTextureHeadless : getCAMetalDrawable().texture;",
      "    if(_huskSpatialImage){\n        // Preserve original drawable acquisition/back-pressure.\n        return getCAMetalDrawable()?huskSpatialInput(_huskSpatialImage):nil;\n    }\n\treturn _mtlTextureHeadless ? _mtlTextureHeadless : getCAMetalDrawable().texture;"
    ],
    [
      "\tMVKSwapchainSignaler signaler = getPresentationSignaler();",
      "    // Caller already encoded render-completion waits on this retained buffer.\n    if(_huskSpatialImage&&!huskSpatialEncode(_huskSpatialImage,mtlDrwbl.texture,mtlCmdBuff)){\n        setConfigurationResult(reportError(VK_ERROR_INITIALIZATION_FAILED,\"Husk M9: scaler encode failed; disable experiment and restart\"));\n    }\n    // Retain original presentation/signal/completion cleanup on every path.\n\tMVKSwapchainSignaler signaler = getPresentationSignaler();"
    ],
    [
      "\t_availability.acquisitionID = _swapchain->getNextAcquisitionID();\n\t_availability.isAvailable = true;",
      "\t_availability.acquisitionID = _swapchain->getNextAcquisitionID();\n\t_availability.isAvailable = true;\n    if(swapchain->_huskSpatial.enabled){\n        _huskSpatialImage=huskSpatialNewImage(getMTLDevice(),getMTLPixelFormat(),\n            getMTLTextureUsage(getMTLPixelFormat()),swapchain->_huskSpatial);\n        if(!_huskSpatialImage){setConfigurationResult(reportError(VK_ERROR_OUT_OF_DEVICE_MEMORY,\"Husk M9: input/scaler allocation failed\"));}\n    }"
    ],
    [
      "\t_mtlTextureHeadless = nil;\n\tMVKSwapchainImage::destroy();",
      "\t_mtlTextureHeadless = nil;\n\thuskSpatialDeleteImage(_huskSpatialImage);\n\t_huskSpatialImage = nullptr;\n\tMVKSwapchainImage::destroy();"
    ]
  ]
}
def prepare(src):
    rev=subprocess.check_output(["git","-C",str(src),"rev-parse","HEAD"],text=True).strip()
    if rev!=PIN:raise SystemExit("Unexpected MoltenVK source pin")
    gpu=src/"MoltenVK/MoltenVK/GPUObjects"
    changed={}
    for name,edits in REPLACEMENTS.items():
        content=(gpu/name).read_text()
        for before,after in edits:
            if content.count(before)!=1:raise SystemExit("Pinned source/patch drift: "+name)
            content=content.replace(before,after)
        changed[gpu/name]=content
    project=src/"MoltenVK/MoltenVK.xcodeproj/project.pbxproj"
    original=project.read_text()
    if '"-all_load",' not in original:raise SystemExit("Missing framework link anchor")
    changed[project]=original.replace('"-all_load",','"-all_load",\\n\\t\\t\\t\\t\\t"-weak_framework",\\n\\t\\t\\t\\t\\t"MetalFX",'.replace("\\n","\n").replace("\\t","\t"))
    # All anchors are checked before mutation.
    for path,content in changed.items():path.write_text(content)
    for name in ["HuskSpatial.inc","HuskSpatialDriver.h"]:shutil.copy2(ROOT/"patches/metalfx"/name,gpu/name)
    shutil.copy2(ROOT/"src/translation-layer-next/husk-tl-spatial.h",gpu/"HuskSpatialABI.h")
    inputs=[Path(__file__),ROOT/"patches/metalfx/HuskSpatial.inc",ROOT/"patches/metalfx/HuskSpatialDriver.h",ROOT/"src/translation-layer-next/husk-tl-spatial.h"]
    digest=hashlib.sha256()
    for path in inputs:digest.update(path.read_bytes())
    manifest={"schema":1,"upstream_commit":PIN,"upstream_version":"1.4.2","husk_spatial_patch_sha256":digest.hexdigest(),"feature":"M9-SPATIAL-v2","default_enabled":False}
    (src/"HuskSpatialBuild.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest))
if __name__=="__main__":prepare(Path(sys.argv[1]).resolve())
