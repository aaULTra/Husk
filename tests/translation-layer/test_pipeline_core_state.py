#!/usr/bin/env python3
"""Real core-state observer: semantic identity, lifetime, ignored pointers and wrapper forwarding."""
import ctypes,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];TL=ROOT/'src/translation-layer-next'
class CoreStateTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);p=Path(cls.tmp.name)
  wrapper=(TL/'husk-tl-vulkan.m').read_text().split('#define PI_OBJECT_WRAPPERS',1)[1].split('/* Direct MoltenVK handles',1)[0]
  wrapper='#define PI_OBJECT_WRAPPERS'+wrapper
  (p/'check.c').write_text(r'''
#include <assert.h>
#include <stdarg.h>
#include "husk-tl-pipeline-diagnostics.c"
void tl_log_line(const char*f,...){(void)f;}
static unsigned last_full,last_coverage;
uint64_t variant(int mode){
 husk_ue4_set_pipeline_diagnostics(true);memset(modules,0,sizeof(modules));memset(pi_objects,0,sizeof(pi_objects));
 void *device=(void*)1;uint32_t code[]={0x07230203,1,2};tl_pi_module_ci module={.type=16,.size=sizeof(code),.code=code};tl_pi_shader(device,4,&module);
 pi_sampler sampler={.type=31,.mag=(uint32_t)(mode==4?1:0),.min_lod=0,.max_lod=1};tl_pi_object(TL_PI_SAMPLER,device,50,&sampler);
 uint64_t immutable=50;pi_binding binding={.binding=0,.type=1,.count=1,.stages=16,.samplers=&immutable};
 if(mode==9){binding.type=6;binding.samplers=(void*)1;}
 pi_descriptor_layout descriptor={.type=32,.count=1,.bindings=&binding};tl_pi_object(TL_PI_DESCRIPTOR_LAYOUT,device,60,&descriptor);
 uint64_t set=60;pi_push push={.stages=1,.size=(uint32_t)(mode==3?8:4)};
 pi_pipeline_layout layout={.type=30,.sets=1,.layouts=&set,.pushes=1,.ranges=&push};
 uint64_t lh=mode==1?800:80,rh=mode==1?900:90;tl_pi_object(TL_PI_PIPELINE_LAYOUT,device,lh,&layout);
 uint32_t attachment[9]={0,(uint32_t)(mode==2?50:44),1,0,0,0,0,0,2};pi_attachment_ref color={0,2};pi_subpass subpass={.colors=1,.color=&color};
 pi_render_pass pass={.type=38,.attachments=1,.attachment_data=attachment,.subpasses=1,.subpass_data=&subpass};tl_pi_object(TL_PI_RENDER_PASS,device,rh,&pass);
 tl_pi_stage stages[2]={{.type=18,.stage=1,.module=4,.name="main"},{.type=18,.stage=16,.module=4,.name="main"}};
 pi_vertex vertex={.type=19};pi_assembly assembly={.type=20,.topology=3};pi_raster raster={.type=23,.line=1};
 uint32_t dynamic_states[2]={0,1};pi_dynamic dynamic={.type=27,.count=2,.states=dynamic_states};
 pi_viewport viewport={.type=22,.viewports=1,.viewport_data=(void*)1,.scissors=1,.scissor_data=(void*)1};
 pi_multi multi={.type=24,.samples=1};pi_depth depth={.type=25};uint32_t blend_attachment[8]={0,0,0,0,0,0,0,15};pi_blend blend={.type=26,.count=1,.attachments=blend_attachment};
 tl_pi_graphics ci={.type=28,.count=2,.stages=stages,.vertex=&vertex,.assembly=&assembly,.raster=&raster,.viewport=&viewport,.multisample=&multi,.depth=&depth,.blend=&blend,.dynamic=&dynamic,.layout=lh,.renderpass=rh,.base_index=-1};
 if(mode==5||mode==6)ci.layout=mode==5?8888:9999;
 if(mode==7)tl_pi_forget_object(TL_PI_PIPELINE_LAYOUT,device,lh);
 if(mode==8){raster.next=(void*)1;ci.multisample=(void*)1;}
 if(mode==10){descriptor.next=(void*)1;descriptor.bindings=(void*)1;tl_pi_object(TL_PI_DESCRIPTOR_LAYOUT,device,60,&descriptor);tl_pi_object(TL_PI_PIPELINE_LAYOUT,device,lh,&layout);}
 uint32_t format=mode==12?50:44;pi_rendering rendering={.type=1000044002,.colors=1,.formats=&format};
 if(mode==11||mode==12){ci.renderpass=0;ci.next=&rendering;}
 tl_pi_request r=tl_pi_identify(false,device,1,&ci);last_full=r.full_core[0];last_coverage=r.coverage[0];
 if(mode==13){uint64_t handles[1]={100};tl_pi_pipeline_objects(r,device,handles);ci.flags=4;ci.base=100;return tl_pi_identify(false,device,1,&ci).full_core[0];}
 if(mode==14){uint64_t handles[1]={100};tl_pi_pipeline_objects(r,device,handles);tl_pi_forget_object(TL_PI_PIPELINE,device,100);ci.flags=4;ci.base=100;return tl_pi_identify(false,device,1,&ci).full_core[0];}
 if(mode==15){tl_pi_forget_device(device);return pi_find_object(TL_PI_RENDER_PASS,device,rh)!=NULL;}
 return r.id[0];
}
unsigned full(void){return last_full;}unsigned coverage(void){return last_coverage;}

int registry_collisions_and_bounds(void){
 husk_ue4_set_pipeline_diagnostics(true);memset(pi_objects,0,sizeof(pi_objects));void *dev=(void*)1;
 uint64_t a=1,b=2;while(pi_bucket(TL_PI_SAMPLER,dev,a)!=pi_bucket(TL_PI_SAMPLER,dev,b))b++;
 pi_store_object(TL_PI_SAMPLER,dev,a,11,1);pi_store_object(TL_PI_SAMPLER,dev,b,22,1);
 tl_pi_forget_object(TL_PI_SAMPLER,dev,a);assert(pi_find_object(TL_PI_SAMPLER,dev,b)->key==22);
 pi_store_object(TL_PI_SAMPLER,dev,b,33,1);assert(pi_find_object(TL_PI_SAMPLER,dev,b)->key==33);
 pi_store_object(TL_PI_SAMPLER,dev,a,44,1);assert(pi_find_object(TL_PI_SAMPLER,dev,a)->key==44);
 pi_binding binding={.type=1,.count=257,.samplers=(void*)1};pi_descriptor_layout d={.type=32,.count=1,.bindings=&binding};
 tl_pi_object(TL_PI_DESCRIPTOR_LAYOUT,dev,999,&d);assert(!pi_find_object(TL_PI_DESCRIPTOR_LAYOUT,dev,999)->complete);
 return 1;
}
int order_independent(void){
 husk_ue4_set_pipeline_diagnostics(true);memset(pi_objects,0,sizeof(pi_objects));
 pi_binding b[2]={{.binding=0,.type=6,.count=1,.stages=1},{.binding=3,.type=7,.count=2,.stages=16}};
 pi_descriptor_layout d={.type=32,.count=2,.bindings=b};tl_pi_object(TL_PI_DESCRIPTOR_LAYOUT,(void*)1,1,&d);
 uint64_t first=pi_find_object(TL_PI_DESCRIPTOR_LAYOUT,(void*)1,1)->key;
 pi_binding tmp=b[0];b[0]=b[1];b[1]=tmp;tl_pi_object(TL_PI_DESCRIPTOR_LAYOUT,(void*)1,2,&d);
 return first==pi_find_object(TL_PI_DESCRIPTOR_LAYOUT,(void*)1,2)->key;
}
#define VK_SUCCESS 0
static struct{void*lib;}V={(void*)1};static int returned;static const void *expected_ci,*expected_alloc;static unsigned calls;
static int create(void*d,const void*c,const void*a,uint64_t*out){assert(d==(void*)1&&c==expected_ci&&a==expected_alloc);calls++;*out=200;return returned;}
static void destroy(void*d,uint64_t o,const void*a){assert(d==(void*)1&&o==200&&a==expected_alloc);calls++;}
static void *lookup(void*l,const char*n){(void)l;return strstr(n,"Create")?(void*)create:(void*)destroy;}
#define dlsym lookup
/* WRAPPERS */
int forwarding(void){
 calls=0;returned=0;husk_ue4_set_pipeline_diagnostics(true);pi_sampler sampler={.type=31};uint64_t out=0;
 expected_ci=&sampler;expected_alloc=(void*)17;assert(w_vkCreateSampler((void*)1,expected_ci,expected_alloc,&out)==0&&out==200);
 assert(pi_find_object(TL_PI_SAMPLER,(void*)1,200));w_vkDestroySampler((void*)1,200,expected_alloc);assert(!pi_find_object(TL_PI_SAMPLER,(void*)1,200));
 returned=-4;assert(w_vkCreateSampler((void*)1,expected_ci,expected_alloc,&out)==-4&&!pi_find_object(TL_PI_SAMPLER,(void*)1,200));
 husk_ue4_set_pipeline_diagnostics(false);expected_ci=(void*)1;returned=0;assert(w_vkCreateDescriptorSetLayout((void*)1,expected_ci,expected_alloc,&out)==0);w_vkDestroyDescriptorSetLayout((void*)1,200,expected_alloc);
 assert(w_vkCreatePipelineLayout((void*)1,expected_ci,expected_alloc,&out)==0);w_vkDestroyPipelineLayout((void*)1,200,expected_alloc);
 assert(w_vkCreateRenderPass((void*)1,expected_ci,expected_alloc,&out)==0);w_vkDestroyRenderPass((void*)1,200,expected_alloc);w_vkDestroyPipeline((void*)1,200,expected_alloc);
 return calls==10;
}
'''.replace('/* WRAPPERS */',wrapper))
  exe=p/'check.so';subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fPIC','-shared','-I',str(TL),str(p/'check.c'),'-pthread','-o',str(exe)],check=True)
  cls.lib=ctypes.CDLL(str(exe));cls.lib.variant.restype=ctypes.c_uint64
 def test_tracked_core_state_complete_and_handles_do_not_change_identity(self):
  a=self.lib.variant(0);self.assertEqual(self.lib.full(),1);self.assertEqual(self.lib.coverage(),31);self.assertEqual(a,self.lib.variant(1))
 def test_render_format_push_constants_and_immutable_sampler_distinguish_variants(self):
  a=self.lib.variant(0)
  for mode in [2,3,4]:self.assertNotEqual(a,self.lib.variant(mode));self.assertEqual(self.lib.full(),1)
 def test_missing_or_destroyed_layout_cannot_be_marked_complete_or_use_handle_as_identity(self):
  a=self.lib.variant(5);self.assertEqual(self.lib.full(),0);self.assertTrue(self.lib.coverage()&131072)
  self.assertEqual(a,self.lib.variant(6));self.lib.variant(7);self.assertEqual(self.lib.full(),0)
 def test_unknown_nested_state_and_object_extensions_do_not_read_ignored_pointers(self):
  for mode in [8,10]:self.lib.variant(mode);self.assertEqual(self.lib.full(),0)
 def test_non_sampler_descriptor_ignores_immutable_sampler_pointer(self):self.lib.variant(9);self.assertEqual(self.lib.full(),1)
 def test_dynamic_rendering_formats_are_identified(self):
  a=self.lib.variant(11);self.assertEqual(self.lib.full(),1);self.assertNotEqual(a,self.lib.variant(12));self.assertEqual(self.lib.full(),1)
 def test_base_pipeline_tracking_and_destroy_prevent_stale_full_identity(self):self.assertEqual(self.lib.variant(13),1);self.assertEqual(self.lib.variant(14),0)
 def test_device_destroy_clears_object_registry(self):self.assertEqual(self.lib.variant(15),0)
 def test_registry_collisions_tombstones_and_bounded_immutable_sampler_reads(self):self.assertEqual(self.lib.registry_collisions_and_bounds(),1)
 def test_descriptor_binding_array_order_is_semantic_not_pointer_or_order(self):self.assertEqual(self.lib.order_independent(),1)
 def test_actual_wrappers_preserve_arguments_results_lifetime_and_disabled_fast_path(self):self.assertEqual(self.lib.forwarding(),1)
if __name__=='__main__':unittest.main()
