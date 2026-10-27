/* SPDX-License-Identifier: Apache-2.0
 * Husk experimental integration for pinned MoltenVK v1.4.2. */
#import <MetalFX/MetalFX.h>
#include "HuskSpatialABI.h"
#include <atomic>
#include <mutex>
#include <new>
static std::mutex huskSpatialConfigLock;
static tl_spatial_config huskSpatialConfig={};
static std::atomic<uint64_t> huskSpatialChecks{0},huskSpatialRebinds{0};
static std::atomic<uint64_t> huskSpatialCreated{0},huskSpatialEncoded{0},huskSpatialFailures{0};
static std::atomic<uint32_t> huskSpatialLive{0};
static std::atomic<uint64_t> huskSpatialUnsupported{0},huskSpatialResources{0},huskSpatialEncodeFailures{0};
static std::mutex huskSpatialObservationLock;
static tl_spatial_observations huskSpatialObserved={};
struct HuskSpatialImage {
    id<MTLTexture> input=nil;
    id<MTLFXSpatialScaler> scaler=nil;
    std::mutex lock;
    bool observed=false,prepared=false;
    uint32_t outputWidth=0,outputHeight=0;
    MTLPixelFormat format=MTLPixelFormatInvalid;
    MTLTextureUsage outputUsage=MTLTextureUsageUnknown;
    id<MTLTexture> boundOutput=nil; // nonowning tag; scaler retains this binding
    ~HuskSpatialImage(){[input release];[scaler release];--huskSpatialLive;}
};
static id<MTLFXSpatialScaler> huskNewScaler(id<MTLDevice> device,MTLPixelFormat format,const tl_spatial_config& c){
    if(@available(iOS 16.0,macOS 13.0,tvOS 16.0,*)){
        if(!device||![MTLFXSpatialScalerDescriptor supportsDevice:device])return nil;
        auto* d=[MTLFXSpatialScalerDescriptor new];
        d.inputWidth=c.input_width;d.inputHeight=c.input_height;
        d.outputWidth=c.output_width;d.outputHeight=c.output_height;
        d.colorTextureFormat=format;d.outputTextureFormat=format;
        d.colorProcessingMode=format==MTLPixelFormatBGRA8Unorm_sRGB
            ?MTLFXSpatialScalerColorProcessingModeLinear:MTLFXSpatialScalerColorProcessingModePerceptual;
        id<MTLFXSpatialScaler> scaler=[d newSpatialScalerWithDevice:device];
        [d release];return scaler;
    }
    return nil;
}
extern "C" __attribute__((visibility("default")))
int vkHuskSpatialConfigure(const tl_spatial_config* request){
    if(!request||request->version!=1||request->size!=sizeof(*request)||request->reserved||request->enabled>1)return 0;
    std::lock_guard<std::mutex> guard(huskSpatialConfigLock);
    if(huskSpatialLive.load())return 0;
    if(!request->enabled){huskSpatialConfig={};
        std::lock_guard<std::mutex> observe(huskSpatialObservationLock);huskSpatialObserved={};return 1;}
    if(request->input_width<64||request->input_height<64||request->output_width>8192||request->output_height>8192||
       request->output_width<=request->input_width||request->output_height<=request->input_height||
       request->output_width>request->input_width*2||request->output_height>request->input_height*2)return 0;
    @autoreleasepool{
        id<MTLDevice> device=MTLCreateSystemDefaultDevice();
        id<MTLFXSpatialScaler> probe=huskNewScaler(device,MTLPixelFormatBGRA8Unorm,*request);
        bool supported=probe!=nil;[probe release];[device release];
        if(!supported){++huskSpatialFailures;return 0;}
    }
    huskSpatialConfig=*request;
    std::lock_guard<std::mutex> observe(huskSpatialObservationLock);huskSpatialObserved={};return 1;
}
extern "C" __attribute__((visibility("default")))
int vkHuskSpatialSnapshot(tl_spatial_stats* out){
    if(!out||out->version!=1||out->size!=sizeof(*out))return 0;
    std::lock_guard<std::mutex> guard(huskSpatialConfigLock);
    *out={1,sizeof(*out),huskSpatialConfig.enabled,huskSpatialLive.load(),
        huskSpatialConfig.input_width,huskSpatialConfig.input_height,
        huskSpatialConfig.output_width,huskSpatialConfig.output_height,
        huskSpatialCreated.load(),huskSpatialEncoded.load(),huskSpatialFailures.load()};
    return 1;
}
extern "C" __attribute__((visibility("default")))
int vkHuskSpatialObservations(tl_spatial_observations* out){
    if(!out||out->version!=1||out->size!=sizeof(*out))return 0;
    std::lock_guard<std::mutex> guard(huskSpatialObservationLock);
    *out=huskSpatialObserved;out->version=1;out->size=sizeof(*out);
    out->unsupported_swapchains=huskSpatialUnsupported.load();
    out->allocation_failures=huskSpatialResources.load();
    out->encode_validation_failures=huskSpatialEncodeFailures.load();
    return 1;
}
extern "C" __attribute__((visibility("default")))
int vkHuskSpatialBindings(tl_spatial_bindings* out){
    if(!out||out->version!=1||out->size!=sizeof(*out))return 0;
    *out={1,sizeof(*out),huskSpatialChecks.load(std::memory_order_relaxed),huskSpatialRebinds.load(std::memory_order_relaxed)};return 1;
}
static int huskSpatialPlan(const VkSwapchainCreateInfoKHR* ci,tl_spatial_config* out){
    std::lock_guard<std::mutex> guard(huskSpatialConfigLock);
    if(!huskSpatialConfig.enabled)return 0;
    const auto& c=huskSpatialConfig;
    if(ci->imageExtent.width!=c.input_width||ci->imageExtent.height!=c.input_height||
       ci->imageArrayLayers!=1||ci->imageColorSpace!=VK_COLOR_SPACE_SRGB_NONLINEAR_KHR||
       (ci->imageFormat!=VK_FORMAT_B8G8R8A8_UNORM&&ci->imageFormat!=VK_FORMAT_B8G8R8A8_SRGB)||
       ci->preTransform!=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR||
       ci->compositeAlpha!=VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR||ci->flags||ci->pNext){
        ++huskSpatialFailures;++huskSpatialUnsupported;return -1;
    }
    *out=c;return 1;
}
/* Texture/scaler dimensions and formats are immutable after creation. Prepare
 * the fixed input once, cache its validated contract, and keep only drawable
 * validation/rebinding in the per-frame path. */
static bool huskSpatialPrepareImage(HuskSpatialImage* state,const tl_spatial_config& c,MTLPixelFormat format){
    if(!state)return false;
    state->prepared=false;
    if(!state->input||!state->scaler)return false;
    auto input=state->input;auto scaler=state->scaler;
    if(input.width!=c.input_width||input.height!=c.input_height||input.pixelFormat!=format||
       scaler.inputWidth!=c.input_width||scaler.inputHeight!=c.input_height||
       scaler.outputWidth!=c.output_width||scaler.outputHeight!=c.output_height||
       scaler.colorTextureFormat!=format||scaler.outputTextureFormat!=format||
       (input.usage&scaler.colorTextureUsage)!=scaler.colorTextureUsage)return false;
    state->outputWidth=c.output_width;state->outputHeight=c.output_height;
    state->format=format;state->outputUsage=scaler.outputTextureUsage;
    scaler.colorTexture=input;scaler.inputContentWidth=c.input_width;scaler.inputContentHeight=c.input_height;
    state->prepared=true;return true;
}
void* huskSpatialNewImage(id<MTLDevice> device,MTLPixelFormat format,MTLTextureUsage guestUsage,const tl_spatial_config& c){
    if(!c.enabled)return nullptr;
    auto* state=new(std::nothrow) HuskSpatialImage();
    if(!state){++huskSpatialFailures;++huskSpatialResources;return nullptr;}
    ++huskSpatialLive;
    state->scaler=huskNewScaler(device,format,c);
    if(state->scaler){
        auto* desc=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:format
            width:c.input_width height:c.input_height mipmapped:NO];
        desc.storageMode=MTLStorageModePrivate;
        desc.usage=guestUsage|state->scaler.colorTextureUsage|MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;
        desc.hazardTrackingMode=MTLHazardTrackingModeTracked;
        state->input=[device newTextureWithDescriptor:desc];
        state->input.label=@"Husk M9 lower-resolution input";
    }
    if(!huskSpatialPrepareImage(state,c,format)){++huskSpatialFailures;++huskSpatialResources;delete state;return nullptr;}
    ++huskSpatialCreated;return state;
}
id<MTLTexture> huskSpatialInput(void* raw){return raw?((HuskSpatialImage*)raw)->input:nil;}
bool huskSpatialEncode(void* raw,id<MTLTexture> output,id<MTLCommandBuffer> command){
    auto* state=(HuskSpatialImage*)raw;
    if(!state||!command||!output){++huskSpatialFailures;++huskSpatialEncodeFailures;return false;}
    std::lock_guard<std::mutex> guard(state->lock);
    id<MTLFXSpatialScaler> scaler=state->scaler;
    if(!state->prepared||!scaler||!state->input){++huskSpatialFailures;++huskSpatialEncodeFailures;return false;}
    // Metal texture dimensions/format/usage are immutable. The scaler retains
    // its output, so this equality tag cannot become a dangling/ABA pointer.
    // Preserve checks/rebinding for every different drawable texture.
    if(output!=state->boundOutput){
        huskSpatialChecks.fetch_add(1,std::memory_order_relaxed);
        if(output.width!=state->outputWidth||output.height!=state->outputHeight||
           output.pixelFormat!=state->format||(output.usage&state->outputUsage)!=state->outputUsage){
            ++huskSpatialFailures;++huskSpatialEncodeFailures;return false;
        }
        scaler.outputTexture=output;state->boundOutput=output;
        huskSpatialRebinds.fetch_add(1,std::memory_order_relaxed);
    }
    [scaler encodeToCommandBuffer:command];++huskSpatialEncoded;
    if(!state->observed){
        std::lock_guard<std::mutex> observe(huskSpatialObservationLock);
        huskSpatialObserved.input_width=(uint32_t)state->input.width;
        huskSpatialObserved.input_height=(uint32_t)state->input.height;
        huskSpatialObserved.output_width=(uint32_t)output.width;
        huskSpatialObserved.output_height=(uint32_t)output.height;
        huskSpatialObserved.input_format=(uint32_t)state->input.pixelFormat;
        huskSpatialObserved.output_format=(uint32_t)output.pixelFormat;
        huskSpatialObserved.color_processing=(uint32_t)scaler.colorProcessingMode;
        huskSpatialObserved.observed_images++;state->observed=true;
    }
    return true;
}
void huskSpatialDeleteImage(void* raw){delete (HuskSpatialImage*)raw;}
