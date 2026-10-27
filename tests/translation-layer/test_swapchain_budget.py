#!/usr/bin/env python3
"""Actual surface-checked swapchain wrapper: ownership, forwarding, counts, no retry."""
import subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];TL=ROOT/'src/translation-layer-next'
class SwapchainBudgetTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);p=Path(cls.tmp.name)
  vulkan=(TL/'husk-tl-vulkan.m').read_text();body=vulkan[vulkan.index('static int w_vkCreateSwapchainKHR('):vulkan.index('typedef int (*pfn_acquire)')].replace('[CATransaction flush];','flush_mock();')
  (p/'main.c').write_text(r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <stdatomic.h>
#include "husk-tl-swapchain-budget.h"
#define VK_SUCCESS 0
typedef int(*pfn_create_swapchain)(void*,const void*,const void*,uint64_t*);
static struct{void *lib;}V={(void*)1};static void *g_swapchain_layer;
static unsigned creates,queries,expected_min,actual_images=3,mode;
static const void *original;
static int host_caps(void *physical,uint64_t surface,tl_sb_caps *out){assert(physical==(void*)1&&surface==11);queries++;*out=(tl_sb_caps){.min_images=mode==2?3:2,.max_images=mode==3?0:mode==10?1:3};return mode==4?-3:0;}
static int host_create(void *device,const void *raw,const void *alloc,uint64_t *out){
 creates++;assert(device==(void*)2&&alloc==(void*)5);const tl_sb_create *c=raw;
 assert(c->width==2128&&c->height==1600&&c->present_mode==2&&c->min_images==expected_min&&c->old_swapchain==88);
 if(expected_min==3&&mode!=1)assert(raw==original);else assert(raw!=original);
 if(mode==5){return -3;}*out=99;return 0;
}
static int host_images(void *device,uint64_t swapchain,uint32_t *count,uint64_t *images){
 assert(device==(void*)2&&swapchain==99);
 if(mode==7)return -4;
 if(!images){*count=actual_images;return 0;}
 unsigned cap=*count;*count=cap<actual_images?cap:actual_images;for(unsigned i=0;i<*count;i++)images[i]=100+i;return cap<actual_images?5:0;
}
static void *lookup(void *lib,const char *name){(void)lib;if(!strcmp(name,"vkCreateSwapchainKHR"))return(void*)host_create;if(!strcmp(name,"vkGetSwapchainImagesKHR"))return(void*)host_images;if(!strcmp(name,"vkGetPhysicalDeviceSurfaceCapabilitiesKHR"))return(void*)host_caps;return NULL;}
#define dlsym lookup
static void tl_log_line(const char *s,...){(void)s;}
static void tl_em_size(unsigned w,unsigned h){assert(w==2128&&h==1600);}
static bool tl_ue4_sharp_graphics_enabled(void){return true;}
static void flush_mock(void){}
static void log_layer_state(void*l,const char*s){(void)l;(void)s;}
/* ACTUAL_WRAPPERS */
int main(int argc,char **argv){assert(argc==2);mode=(unsigned)atoi(argv[1]);
 unsigned wanted=mode==0?0:mode==1?3:2;husk_ue4_set_swapchain_images((int)wanted);tl_sb_device((void*)1,(void*)2);
 tl_sb_create ci={.type=1000001000,.surface=11,.min_images=mode==1?2:3,.format=44,.width=2128,.height=1600,.layers=1,.usage=0x16,.transform=1,.alpha=1,.present_mode=2,.clipped=1,.old_swapchain=88};
 if(mode==8){
  tl_sb_create a,b;uint64_t ta,tb;
  tl_sb_prepare((void*)2,&ci,host_caps,&a,&ta);tl_sb_prepare((void*)2,&ci,host_caps,&b,&tb);
  tl_sb_created((void*)2,99,0,ta);tl_sb_images((void*)2,99,0,3,true);tl_sb_stats s;tl_sb_snapshot(&s);assert(!s.create_completed&&!s.images_complete);
  tl_sb_created((void*)2,101,0,tb);tl_sb_images((void*)2,99,0,3,true);tl_sb_snapshot(&s);assert(!s.images_complete);
  tl_sb_images((void*)2,101,0,2,true);tl_sb_snapshot(&s);assert(s.images_complete&&s.returned_images==2&&s.generation==tb);return 0;
 }
 if(mode==9){
  for(uintptr_t i=3;i<=18;i++)tl_sb_device((void*)1,(void*)i);
  tl_sb_create copy;uint64_t ticket;assert(tl_sb_prepare((void*)18,&ci,host_caps,&copy,&ticket)==&ci);tl_sb_stats s;tl_sb_snapshot(&s);assert(s.device_capacity_drops==1&&!queries);return 0;
 }
 if(mode==6)ci.next=(void*)1;
 tl_sb_create before=ci;original=&ci;expected_min=(mode==0||mode==2||mode==4||mode==6||mode==10)?3:wanted;
 uint64_t out=0;int result=w_vkCreateSwapchainKHR((void*)2,&ci,(void*)5,&out);
 assert(!memcmp(&before,&ci,sizeof(ci))&&creates==1&&result==(mode==5?-3:0));
 tl_sb_stats s;tl_sb_snapshot(&s);assert(s.create_completed&&s.create_result==result&&s.selected_min==expected_min);
 assert(queries==(mode==0||mode==6?0:1));
 if(mode==5){assert(!s.images_complete&&!out);return 0;}
 uint32_t count=0;int r=w_vkGetSwapchainImagesKHR((void*)2,out,&count,NULL);assert(r==(mode==7?-4:0));
 tl_sb_snapshot(&s);
 if(mode==7){assert(!s.images_complete&&s.images_result==-4);return 0;}
 assert(s.images_complete&&s.returned_images==actual_images);
 uint64_t images[3];count=1;assert(w_vkGetSwapchainImagesKHR((void*)2,out,&count,images)==5&&count==1);tl_sb_snapshot(&s);assert(!s.images_complete&&s.returned_images==1);
 count=3;assert(w_vkGetSwapchainImagesKHR((void*)2,out,&count,images)==0);tl_sb_snapshot(&s);assert(s.images_complete&&s.returned_images==3);
 tl_sb_forget((void*)2);tl_sb_snapshot(&s);assert(!s.images_complete);
 return 0;
}
'''.replace('/* ACTUAL_WRAPPERS */',body))
  cls.exe=p/'check';subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(TL),str(p/'main.c'),str(TL/'husk-tl-swapchain-budget.c'),'-pthread','-o',str(cls.exe)],check=True)
 def run_case(self,n):subprocess.run([str(self.exe),str(n)],check=True,timeout=10)
 def test_default_exact_forwarding_and_actual_image_count(self):self.run_case(0)
 def test_three_image_override_preserves_every_other_field(self):self.run_case(1)
 def test_two_images_rejected_below_reported_surface_minimum(self):self.run_case(2)
 def test_unbounded_surface_maximum_allows_two_image_request(self):self.run_case(3)
 def test_failed_caps_query_preserves_original_request(self):self.run_case(4)
 def test_failed_changed_creation_is_never_retried_with_old_swapchain(self):self.run_case(5)
 def test_unknown_chain_is_not_dereferenced_or_changed(self):self.run_case(6)
 def test_failed_image_query_does_not_report_stale_complete_count(self):self.run_case(7)
 def test_overlapping_generations_cannot_mix_old_image_query_with_new_creation(self):self.run_case(8)
 def test_device_registry_capacity_preserves_original_when_mapping_unavailable(self):self.run_case(9)
 def test_invalid_reported_surface_range_declines_override(self):self.run_case(10)
if __name__=='__main__':unittest.main()
