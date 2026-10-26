#!/usr/bin/env python3
"""Executable M9 input/rollback/touch/driver guards; full pinned driver built in IPA CI."""
from pathlib import Path
import subprocess,tempfile,sys,unittest
ROOT=Path(__file__).resolve().parents[2]
TL=ROOT/"src/translation-layer-next"
class SpatialTests(unittest.TestCase):
    def compile_run(self,source,cpp=False,extra=()):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);file=p/("main.cpp" if cpp else "main.c");file.write_text(source)
            exe=p/"check"
            subprocess.run(["c++" if cpp else "cc","-std=c++17" if cpp else "-std=c11","-Wall","-Wextra","-Werror","-I",str(TL),str(file),*map(str,extra),"-o",str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
    def test_dimensions_preserve_output_and_align_input(self):
        self.compile_run(r'''
#include "husk-tl-spatial.h"
#include <assert.h>
int main(void){tl_spatial_config c={0};assert(sizeof(c)==32&&sizeof(tl_spatial_stats)==56&&sizeof(tl_spatial_observations)==64);
 assert(tl_spatial_dimensions(2128,1600,80,&c));assert(c.input_width==1696&&c.input_height==1280);
 assert(c.output_width==2128&&c.output_height==1600&&c.version==1&&c.enabled==1);
 assert(c.input_width%8==0&&c.input_height%8==0);
 int percents[]={85,90,95},widths[]={1808,1912,2016},heights[]={1360,1440,1520};
 for(int i=0;i<3;i++){assert(tl_spatial_dimensions(2128,1600,percents[i],&c));assert(c.input_width==(unsigned)widths[i]&&c.input_height==(unsigned)heights[i]);assert(c.output_width==2128&&c.output_height==1600);}
 return 0;}
''',extra=[TL/"husk-tl-spatial.c"])
    def test_invalid_dimensions_leave_original_request_untouched(self):
        self.compile_run(r'''
#include "husk-tl-spatial.h"
#include <assert.h>
#include <string.h>
int main(void){tl_spatial_config c={.version=77},before=c;
 assert(!tl_spatial_dimensions(2128,1600,100,&c));assert(!tl_spatial_dimensions(10,10,80,&c));
 assert(!tl_spatial_dimensions(9000,1600,80,&c));assert(!tl_spatial_dimensions(2128,1600,49,&c));
 assert(!tl_spatial_dimensions(2128,1600,80,0));assert(!memcmp(&c,&before,sizeof(c)));return 0;}
''',extra=[TL/"husk-tl-spatial.c"])
    def test_real_host_preflight_forwarding_and_touch_mapping(self):
        v=(TL/"husk-tl-vulkan.m").read_text()
        body=v[v.index("static bool spatial_requested;"):v.index("static int submission_mode;")]
        body+=v[v.index("void tl_vk_spatial_snapshot("):v.index("/* MoltenVK's own list")]
        self.compile_run(r'''
#include "husk-tl-spatial.h"
#include <stdatomic.h>
#include <assert.h>
#include <string.h>
#include <stddef.h>
static struct{void* lib;}V={(void*)1};
static int driver_present=1,driver_accepts=1,ready=1,sharp=1,calls;
static bool vk_ready(void){return ready!=0;}
static bool tl_ue4_sharp_graphics_enabled(void){return sharp!=0;}
static void tl_log_line(const char *format,...){(void)format;}
static int configure(const tl_spatial_config*c){calls++;assert(c->output_width==2128&&c->input_width==1696);return driver_accepts;}
static void* fake_dlsym(void *lib,const char*name){(void)lib;return driver_present&&!strcmp(name,"vkHuskSpatialConfigure")?(void*)configure:NULL;}
#define dlsym fake_dlsym
'''+body+r'''
int main(void){
 int w=2128,h=1600;float x=1064,y=800;
 assert(!tl_vk_spatial_prepare((void*)1,NULL,NULL)&&!calls);
 husk_ue4_set_spatial_upscaling(true);
 husk_ue4_set_spatial_input_percent(95);assert(spatial_input_percent==95);
 husk_ue4_set_spatial_input_percent(5);assert(spatial_input_percent==80);
 assert(!tl_vk_spatial_prepare("Other",&w,&h));assert(w==2128&&h==1600&&!calls);
 sharp=0;assert(!tl_vk_spatial_prepare("Dungeons",&w,&h));sharp=1;
 driver_present=0;assert(!tl_vk_spatial_prepare("Dungeons",&w,&h));assert(w==2128&&h==1600);
 driver_present=1;driver_accepts=0;assert(!tl_vk_spatial_prepare("Dungeons",&w,&h));assert(w==2128&&h==1600);
 tl_vk_spatial_touch(&x,&y);assert(x==1064&&y==800);
 driver_accepts=1;assert(tl_vk_spatial_prepare("Dungeons",&w,&h)&&w==1696&&h==1280);
 tl_vk_spatial_touch(&x,&y);assert(x==848&&y==640&&tl_vk_spatial_active());
 tl_spatial_stats s;tl_vk_spatial_snapshot(&s);assert(s.version==1&&s.size==sizeof(s)&&s.configured==0);
 tl_spatial_observations o;assert(!tl_vk_spatial_observations(&o)&&o.version==1&&o.size==64);
 return 0;}
''',extra=[TL/"husk-tl-spatial.c"])
    def test_real_driver_swapchain_guards(self):
        inc=(ROOT/"patches/metalfx/HuskSpatial.inc").read_text()
        body=inc[inc.index("static int huskSpatialPlan("):inc.index("void* huskSpatialNewImage(")]
        self.compile_run(r'''
#include "husk-tl-spatial.h"
#include <atomic>
#include <mutex>
#include <cassert>
static std::mutex huskSpatialConfigLock;
static tl_spatial_config huskSpatialConfig={};
static std::atomic<unsigned> huskSpatialFailures{0},huskSpatialUnsupported{0};
enum{VK_COLOR_SPACE_SRGB_NONLINEAR_KHR=0,VK_FORMAT_B8G8R8A8_UNORM=44,VK_FORMAT_B8G8R8A8_SRGB=50,
 VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR=1,VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR=1};
struct VkSwapchainCreateInfoKHR{struct{unsigned width,height;}imageExtent;unsigned imageArrayLayers,imageColorSpace,imageFormat,preTransform,compositeAlpha,flags;void*pNext;};
'''+body+r'''
int main(){
 VkSwapchainCreateInfoKHR ci={{1696,1280},1,0,44,1,1,0,nullptr};tl_spatial_config out={};
 assert(huskSpatialPlan(&ci,&out)==0);
 huskSpatialConfig={1,sizeof(out),1696,1280,2128,1600,1,0};
 assert(huskSpatialPlan(&ci,&out)==1&&out.output_width==2128);
 auto good=ci;ci.imageArrayLayers=2;assert(huskSpatialPlan(&ci,&out)==-1);ci=good;
 ci.imageColorSpace=100;assert(huskSpatialPlan(&ci,&out)==-1);ci=good;
 ci.imageFormat=99;assert(huskSpatialPlan(&ci,&out)==-1);ci=good;
 ci.preTransform=2;assert(huskSpatialPlan(&ci,&out)==-1);ci=good;
 ci.compositeAlpha=2;assert(huskSpatialPlan(&ci,&out)==-1);ci=good;
 ci.flags=1;assert(huskSpatialPlan(&ci,&out)==-1);ci=good;
 ci.pNext=(void*)1;assert(huskSpatialPlan(&ci,&out)==-1);ci=good;
 ci.imageExtent.width=2128;assert(huskSpatialPlan(&ci,&out)==-1);ci=good;
 ci.imageFormat=50;assert(huskSpatialPlan(&ci,&out)==1);
 return 0;}
''',cpp=True)
    @unittest.skipUnless(sys.platform=="darwin","Apple MetalFX SDK required; CI runs this check")
    def test_actual_scaler_code_abi_and_failure_paths_compile(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"HuskSpatialABI.h").write_text((TL/"husk-tl-spatial.h").read_text())
            inc=ROOT/"patches/metalfx/HuskSpatial.inc"
            main=r'''
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cassert>
enum{VK_COLOR_SPACE_SRGB_NONLINEAR_KHR=0,VK_FORMAT_B8G8R8A8_UNORM=44,VK_FORMAT_B8G8R8A8_SRGB=50,VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR=1,VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR=1};
struct VkSwapchainCreateInfoKHR{struct{unsigned width,height;}imageExtent;unsigned imageArrayLayers,imageColorSpace,imageFormat,preTransform,compositeAlpha,flags;void*pNext;};
#include "HuskSpatial.inc"
int main(){@autoreleasepool{
 tl_spatial_config c={1,sizeof(c),0,0,0,0,0,0};assert(vkHuskSpatialConfigure(&c)==1);
 c.version=2;assert(!vkHuskSpatialConfigure(&c));c.version=1;c.enabled=1;assert(!vkHuskSpatialConfigure(&c));
 tl_spatial_stats s={1,sizeof(s),0,0,0,0,0,0,0,0,0};assert(vkHuskSpatialSnapshot(&s)&&!s.configured);
 tl_spatial_observations o={};o.version=1;o.size=sizeof(o);assert(vkHuskSpatialObservations(&o)&&!o.observed_images);
 o.version=2;assert(!vkHuskSpatialObservations(&o));o.version=1;
 assert(!huskSpatialEncode(nullptr,nil,nil));assert(vkHuskSpatialObservations(&o)&&o.encode_validation_failures==1);assert(vkHuskSpatialSnapshot(&s)&&s.failures==1);
 c.enabled=0;assert(!huskSpatialNewImage(nil,MTLPixelFormatBGRA8Unorm,MTLTextureUsageRenderTarget,c));
 return 0;}}
'''
            (p/"main.mm").write_text(main)
            subprocess.run(["clang++","-std=c++17","-fno-objc-arc","-fblocks","-I",str(p),"-I",str(inc.parent),str(p/"main.mm"),"-framework","Foundation","-framework","Metal","-framework","MetalFX","-o",str(p/"check")],check=True)
            subprocess.run([str(p/"check")],check=True)
if __name__=="__main__":unittest.main()
