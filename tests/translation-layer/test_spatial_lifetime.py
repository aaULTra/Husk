#!/usr/bin/env python3
"""Actual scaler component with deterministic Metal protocol doubles on Apple."""
import subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
@unittest.skipUnless(sys.platform=='darwin','Apple Objective-C/MetalFX SDK required; IPA CI runs this check')
class SpatialLifetimeTests(unittest.TestCase):
 def test_ownership_preparation_reuse_failure_serialization_and_reconfiguration(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);tl=ROOT/'src/translation-layer-next';inc=ROOT/'patches/metalfx'
   (p/'HuskSpatialABI.h').write_text((tl/'husk-tl-spatial.h').read_text())
   (p/'main.mm').write_text(r'''
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <atomic>
#include <thread>
#include <cassert>
enum{VK_COLOR_SPACE_SRGB_NONLINEAR_KHR=0,VK_FORMAT_B8G8R8A8_UNORM=44,VK_FORMAT_B8G8R8A8_SRGB=50,VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR=1,VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR=1};
struct VkSwapchainCreateInfoKHR{struct{unsigned width,height;}imageExtent;unsigned imageArrayLayers,imageColorSpace,imageFormat,preTransform,compositeAlpha,flags;void*pNext;};
#include "HuskSpatial.inc"
static std::atomic<unsigned> texturesFreed{0},scalersFreed{0},overlaps{0};
@interface TestTexture:NSObject
@property(nonatomic) NSUInteger width,height;
@property(nonatomic) MTLPixelFormat pixelFormat;
@property(nonatomic) MTLTextureUsage usage;
@end
@implementation TestTexture
-(void)dealloc{++texturesFreed;[super dealloc];}
@end
@interface TestScaler:NSObject{std::atomic<unsigned> _active;}
@property(nonatomic) NSUInteger inputWidth,inputHeight,outputWidth,outputHeight;
@property(nonatomic) MTLPixelFormat colorTextureFormat,outputTextureFormat;
@property(nonatomic) MTLTextureUsage colorTextureUsage,outputTextureUsage;
@property(nonatomic) MTLFXSpatialScalerColorProcessingMode colorProcessingMode;
@property(nonatomic,retain) id colorTexture,outputTexture;
@property(nonatomic) NSUInteger inputContentWidth,inputContentHeight;
@property(nonatomic) unsigned inputBindings,contentWrites,outputBindings,encodes;
@end
@implementation TestScaler
@synthesize colorTexture=_colorTexture,outputTexture=_outputTexture,inputContentWidth=_inputContentWidth,inputContentHeight=_inputContentHeight;
-(id)init{self=[super init];if(self)_active.store(0);return self;}
-(void)setColorTexture:(id)value{self.inputBindings++;[value retain];[_colorTexture release];_colorTexture=value;}
-(void)setOutputTexture:(id)value{self.outputBindings++;[value retain];[_outputTexture release];_outputTexture=value;}
-(void)setInputContentWidth:(NSUInteger)value{self.contentWrites++;_inputContentWidth=value;}
-(void)setInputContentHeight:(NSUInteger)value{self.contentWrites++;_inputContentHeight=value;}
-(void)encodeToCommandBuffer:(id)command{
 assert(command&&self.colorTexture&&self.outputTexture&&self.inputContentWidth==1696&&self.inputContentHeight==1280);
 if(_active.fetch_add(1))++overlaps;
 self.encodes++;std::this_thread::yield();_active.fetch_sub(1);
}
-(void)dealloc{[_colorTexture release];[_outputTexture release];++scalersFreed;[super dealloc];}
@end
static TestTexture *texture(unsigned w,unsigned h,MTLTextureUsage usage){auto*t=[TestTexture new];t.width=w;t.height=h;t.pixelFormat=MTLPixelFormatBGRA8Unorm;t.usage=usage;return t;}
static HuskSpatialImage *image(const tl_spatial_config&c){
 auto*state=new HuskSpatialImage();++huskSpatialLive;
 state->input=(id<MTLTexture>)texture(c.input_width,c.input_height,MTLTextureUsageShaderRead|MTLTextureUsageRenderTarget);
 auto*s=[TestScaler new];s.inputWidth=c.input_width;s.inputHeight=c.input_height;s.outputWidth=c.output_width;s.outputHeight=c.output_height;
 s.colorTextureFormat=s.outputTextureFormat=MTLPixelFormatBGRA8Unorm;s.colorTextureUsage=MTLTextureUsageShaderRead;s.outputTextureUsage=MTLTextureUsageShaderWrite;
 state->scaler=(id<MTLFXSpatialScaler>)s;return state;
}
int main(){@autoreleasepool{
 tl_spatial_config c={1,sizeof(c),1696,1280,2128,1600,1,0};huskSpatialConfig=c;
 auto*a=image(c),*b=image(c);assert(huskSpatialLive.load()==2);
 assert(huskSpatialPrepareImage(a,c,MTLPixelFormatBGRA8Unorm));assert(huskSpatialPrepareImage(b,c,MTLPixelFormatBGRA8Unorm));
 auto*scaler=(TestScaler*)a->scaler;assert(scaler.inputBindings==1&&scaler.contentWrites==2);
 auto*out=texture(2128,1600,MTLTextureUsageShaderWrite);id command=[NSObject new];
 unsigned invalid=huskSpatialEncodeFailures.load();
 out.width=2120;assert(!huskSpatialEncode(a,(id<MTLTexture>)out,(id<MTLCommandBuffer>)command));out.width=2128;
 out.pixelFormat=MTLPixelFormatRGBA8Unorm;assert(!huskSpatialEncode(a,(id<MTLTexture>)out,(id<MTLCommandBuffer>)command));out.pixelFormat=MTLPixelFormatBGRA8Unorm;
 out.usage=MTLTextureUsageShaderRead;assert(!huskSpatialEncode(a,(id<MTLTexture>)out,(id<MTLCommandBuffer>)command));out.usage=MTLTextureUsageShaderWrite;
 assert(huskSpatialEncodeFailures.load()==invalid+3&&scaler.encodes==0);
 auto encode=[&]{@autoreleasepool{for(unsigned i=0;i<500;i++)assert(huskSpatialEncode(a,(id<MTLTexture>)out,(id<MTLCommandBuffer>)command));}};
 std::thread first(encode),second(encode);first.join();second.join();
 assert(scaler.encodes==1000&&scaler.inputBindings==1&&scaler.contentWrites==2&&scaler.outputBindings==1000&&!overlaps.load());
 tl_spatial_observations observations={};observations.version=1;observations.size=sizeof(observations);
 assert(vkHuskSpatialObservations(&observations)&&observations.observed_images==1&&observations.input_width==1696&&observations.output_width==2128);
 tl_spatial_config off={1,sizeof(off),0,0,0,0,0,0};assert(!vkHuskSpatialConfigure(&off));
 huskSpatialDeleteImage(a);assert(huskSpatialLive.load()==1&&texturesFreed.load()==1&&scalersFreed.load()==1);assert(!vkHuskSpatialConfigure(&off));
 auto*input=(TestTexture*)b->input;input.usage=MTLTextureUsageRenderTarget;
 assert(!huskSpatialPrepareImage(b,c,MTLPixelFormatBGRA8Unorm)&&!b->prepared);
 assert(!huskSpatialEncode(b,(id<MTLTexture>)out,(id<MTLCommandBuffer>)command));
 huskSpatialDeleteImage(b);assert(huskSpatialLive.load()==0&&texturesFreed.load()==2&&scalersFreed.load()==2);
 assert(vkHuskSpatialConfigure(&off));assert(vkHuskSpatialObservations(&observations)&&observations.observed_images==0);
 unsigned resources=huskSpatialResources.load();assert(!huskSpatialNewImage(nil,MTLPixelFormatBGRA8Unorm,MTLTextureUsageRenderTarget,c));
 assert(huskSpatialResources.load()==resources+1&&!huskSpatialLive.load());
 [out release];[command release];assert(texturesFreed.load()==3);return 0;
}}
''')
   binary=p/'check';subprocess.run(['clang++','-std=c++17','-fno-objc-arc','-fblocks','-I',str(p),'-I',str(inc),str(p/'main.mm'),'-framework','Foundation','-framework','Metal','-framework','MetalFX','-o',str(binary)],check=True);subprocess.run([str(binary)],check=True)
if __name__=='__main__':unittest.main()
