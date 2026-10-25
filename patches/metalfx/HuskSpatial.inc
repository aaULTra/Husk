/* SPDX-License-Identifier: Apache-2.0
 * Husk experimental integration for pinned MoltenVK v1.4.2. */
#import <MetalFX/MetalFX.h>
#include "HuskSpatialABI.h"
#include <atomic>
#include <mutex>
#include <new>
static std::mutex huskSpatialConfigLock;
static tl_spatial_config huskSpatialConfig={};
static std::atomic<uint64_t> huskSpatialCreated{0},huskSpatialEncoded{0},huskSpatialFailures{0};
static std::atomic<uint32_t> huskSpatialLive{0};
struct HuskSpatialImage {
    id<MTLTexture> input=nil;
    id<MTLFXSpatialScaler> scaler=nil;
    std::mutex lock;
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
    if(!request->enabled){huskSpatialConfig={};return 1;}
    if(request->input_width<64||request->input_height<64||request->output_width>8192||request->output_height>8192||
       request->output_width<=request->input_width||request->output_height<=request->input_height||
       request->output_width>request->input_width*2||request->output_height>request->input_height*2)return 0;
    @autoreleasepool{
        id<MTLDevice> device=MTLCreateSystemDefaultDevice();
        id<MTLFXSpatialScaler> probe=huskNewScaler(device,MTLPixelFormatBGRA8Unorm,*request);
        bool supported=probe!=nil;[probe release];[device release];
        if(!supported){++huskSpatialFailures;return 0;}
    }
    huskSpatialConfig=*request;return 1;
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
static int huskSpatialPlan(const VkSwapchainCreateInfoKHR* ci,tl_spatial_config* out){
    std::lock_guard<std::mutex> guard(huskSpatialConfigLock);
    if(!huskSpatialConfig.enabled)return 0;
    const auto& c=huskSpatialConfig;
    if(ci->imageExtent.width!=c.input_width||ci->imageExtent.height!=c.input_height||
       ci->imageArrayLayers!=1||ci->imageColorSpace!=VK_COLOR_SPACE_SRGB_NONLINEAR_KHR||
       (ci->imageFormat!=VK_FORMAT_B8G8R8A8_UNORM&&ci->imageFormat!=VK_FORMAT_B8G8R8A8_SRGB)||
       ci->preTransform!=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR||
       ci->compositeAlpha!=VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR||ci->flags||ci->pNext){
        ++huskSpatialFailures;return -1;
    }
    *out=c;return 1;
}
void* huskSpatialNewImage(id<MTLDevice> device,MTLPixelFormat format,MTLTextureUsage guestUsage,const tl_spatial_config& c){
    if(!c.enabled)return nullptr;
    auto* state=new(std::nothrow) HuskSpatialImage();
    if(!state){++huskSpatialFailures;return nullptr;}
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
    if(!state->scaler||!state->input){++huskSpatialFailures;delete state;return nullptr;}
    ++huskSpatialCreated;return state;
}
id<MTLTexture> huskSpatialInput(void* raw){return raw?((HuskSpatialImage*)raw)->input:nil;}
bool huskSpatialEncode(void* raw,id<MTLTexture> output,id<MTLCommandBuffer> command){
    auto* state=(HuskSpatialImage*)raw;
    if(!state||!command||!output){++huskSpatialFailures;return false;}
    std::lock_guard<std::mutex> guard(state->lock);
    id<MTLFXSpatialScaler> scaler=state->scaler;
    if(output.width!=scaler.outputWidth||output.height!=scaler.outputHeight||
       output.pixelFormat!=scaler.outputTextureFormat||
       (output.usage&scaler.outputTextureUsage)!=scaler.outputTextureUsage){++huskSpatialFailures;return false;}
    scaler.colorTexture=state->input;scaler.outputTexture=output;
    scaler.inputContentWidth=state->input.width;scaler.inputContentHeight=state->input.height;
    [scaler encodeToCommandBuffer:command];++huskSpatialEncoded;return true;
}
void huskSpatialDeleteImage(void* raw){delete (HuskSpatialImage*)raw;}
