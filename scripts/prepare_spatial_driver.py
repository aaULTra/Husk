#!/usr/bin/env python3
"""Exact source-pinned transforms; refuse drift rather than guessing offsets."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,re
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
      "\tVkExtent2D _imageExtent = {0, 0};\n\ttl_spatial_config _huskSpatial = {};\n\tuint64_t _huskDisplayGeneration = huskDisplayNewGeneration();"
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
# This is a GPU compiler contract, not a diagnostic/package build identity.
# Bump when transforms change MSL/native descriptor compilation semantics.
NATIVE_COMPILER_CONTRACT="husk-native-default-mvk-compiler-contract-v1"
def archive_compatibility_id(src):
    revision=(src/"ExternalRevisions/SPIRV-Cross_repo_revision").read_text().strip()
    if not re.fullmatch(r"[0-9a-f]{40}",revision):raise ValueError("Invalid pinned SPIRV-Cross revision")
    inputs={"schema":2,"upstream_commit":PIN,"spirv_cross_revision":revision,
            "compiler_contract":NATIVE_COMPILER_CONTRACT,"archive_format_owner":"Metal binary archive"}
    payload=json.dumps(inputs,sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(payload).hexdigest(),inputs

def prepare(src):
    rev=subprocess.check_output(["git","-C",str(src),"rev-parse","HEAD"],text=True).strip()
    if rev!=PIN:raise SystemExit("Unexpected MoltenVK source pin")
    compatibility,compatibility_inputs=archive_compatibility_id(src)
    gpu=src/"MoltenVK/MoltenVK/GPUObjects"
    changed={}
    for name,edits in REPLACEMENTS.items():
        content=(gpu/name).read_text()
        for before,after in edits:
            if content.count(before)!=1:raise SystemExit("Pinned source/patch drift: "+name)
            content=content.replace(before,after)
        changed[gpu/name]=content
    image=changed[gpu/"MVKImage.mm"]
    anchor='\tif (actualPresentTime == 0) { actualPresentTime = mvkGetRuntimeNanoseconds(); }'
    if image.count(anchor)!=1:raise SystemExit("Pinned source/patch drift: presentation provenance")
    image=image.replace(anchor,'\tconst uint64_t huskRawDrawableTime = actualPresentTime;\n'+anchor)
    anchor='\t\tif (_swapchain) { _swapchain->endPresentation(presentInfo, _beginPresentTime, actualPresentTime); }'
    if image.count(anchor)!=1:raise SystemExit("Pinned source/patch drift: presentation callback")
    image=image.replace(anchor,'\t\tif (_swapchain) {\n'
       '\t\t\tif (huskDisplayMonitoring()) huskDisplayObserve(_swapchain->_huskDisplayGeneration, presentInfo.presentIDGoogle, presentInfo.desiredPresentTime, huskRawDrawableTime, actualPresentTime, _beginPresentTime, (uint64_t)(CACurrentMediaTime() * 1.0e9));\n'
       '\t\t\t_swapchain->endPresentation(presentInfo, _beginPresentTime, actualPresentTime);\n\t\t}')
    changed[gpu/"MVKImage.mm"]=image
    changed[gpu/"MVKSwapchain.mm"]+='\n#include "HuskDisplay.inc"\n'
    pipeline=gpu/"MVKPipeline.mm"
    content=pipeline.read_text()
    if content.count("using namespace std;")!=1:raise SystemExit("Pinned source/patch drift: pipeline include")
    content=content.replace("using namespace std;",'using namespace std;\n#include "HuskArchive.inc"')
    transforms=[
      (r'\[mtlDev newRenderPipelineStateWithDescriptor: mtlRPLDesc\s+completionHandler: (\^\(id<MTLRenderPipelineState> ps, NSError\* error\) \{.*?\})\];',r'huskArchiveNewRender(mtlDev, mtlRPLDesc, \1);'),
      (r'\[mtlDev newComputePipelineStateWithDescriptor: plDesc\s+options: MTLPipelineOptionNone\s+completionHandler: (\^\(id<MTLComputePipelineState> ps, MTLComputePipelineReflection\*, NSError\* error\) \{.*?\})\];',r'huskArchiveNewCompute(mtlDev, plDesc, MTLPipelineOptionNone, \1);')]
    for before,after in transforms:
        content,n=re.subn(before,after,content,flags=re.S)
        if n!=1:raise SystemExit("Pinned source/patch drift: native pipeline compiler")
    changed[pipeline]=content
    project=src/"MoltenVK/MoltenVK.xcodeproj/project.pbxproj"
    original=project.read_text()
    if '"-all_load",' not in original:raise SystemExit("Missing framework link anchor")
    changed[project]=original.replace('"-all_load",','"-all_load",\\n\\t\\t\\t\\t\\t"-weak_framework",\\n\\t\\t\\t\\t\\t"MetalFX",'.replace("\\n","\n").replace("\\t","\t"))
    # All anchors are checked before mutation.
    for path,content in changed.items():path.write_text(content)
    for name in ["HuskSpatial.inc","HuskSpatialDriver.h"]:shutil.copy2(ROOT/"patches/metalfx"/name,gpu/name)
    shutil.copy2(ROOT/"src/translation-layer-next/husk-tl-spatial.h",gpu/"HuskSpatialABI.h")
    shutil.copy2(ROOT/"patches/metalfx/HuskDisplay.inc",gpu/"HuskDisplay.inc")
    shutil.copy2(ROOT/"src/translation-layer-next/husk-tl-display.h",gpu/"HuskDisplayABI.h")
    inputs=[ROOT/"patches/metalfx/HuskDisplay.inc",ROOT/"src/translation-layer-next/husk-tl-display.h",Path(__file__),ROOT/"patches/metalfx/HuskSpatial.inc",ROOT/"patches/metalfx/HuskSpatialDriver.h",ROOT/"src/translation-layer-next/husk-tl-spatial.h",ROOT/"patches/metalfx/HuskArchive.inc",ROOT/"src/translation-layer-next/husk-tl-native-archive.h"]
    digest=hashlib.sha256()
    for path in inputs:digest.update(path.read_bytes())
    archive=(ROOT/"patches/metalfx/HuskArchive.inc").read_text()
    (gpu/"HuskArchive.inc").write_text('#define HUSK_ARCHIVE_PATCH_ID "'+digest.hexdigest()+'"\n#define HUSK_ARCHIVE_COMPAT_ID "'+compatibility+'"\n'+archive)
    shutil.copy2(ROOT/"src/translation-layer-next/husk-tl-native-archive.h",gpu/"HuskArchiveABI.h")
    manifest={"schema":1,"upstream_commit":PIN,"upstream_version":"1.4.2","husk_spatial_patch_sha256":digest.hexdigest(),"husk_native_pipeline_patch_sha256":digest.hexdigest(),"native_archive_abi":2,"native_archive_cache_schema":2,"native_archive_compatibility_id":compatibility,"native_archive_compatibility_inputs":compatibility_inputs,"feature":"M9-SPATIAL-v3+M5-NATIVE-ARCHIVE-v1+M4-DISPLAY-v1","default_enabled":False}
    (src/"HuskSpatialBuild.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest))
if __name__=="__main__":prepare(Path(sys.argv[1]).resolve())
