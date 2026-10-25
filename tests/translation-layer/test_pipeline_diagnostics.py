#!/usr/bin/env python3
"""Compile and exercise actual partial identity/feedback observer, no Vulkan driver."""
import ctypes, os, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class PipelineDiagnosticsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup)
  root=Path(cls.tmp.name);src=root/'identity.c'
  src.write_text(r'''
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "husk-tl-pipeline-diagnostics.c"
static char output[2048];static unsigned lines;
void tl_log_line(const char *fmt,...) { va_list ap;va_start(ap,fmt);vsnprintf(output,sizeof(output),fmt,ap);va_end(ap);lines++; }
static uint32_t code[]={0x07230203,1,2,3};
static tl_pi_stage stage;
static tl_pi_graphics ci;
void setup(void) {
 husk_ue4_set_pipeline_diagnostics(true);memset(modules,0,sizeof(modules));memset(signatures,0,sizeof(signatures));head=length=lines=0;atomic_store(&drops,0);
 stage=(tl_pi_stage){.type=18,.stage=1,.module=4,.name="main"};
 ci=(tl_pi_graphics){.type=28,.count=1,.stages=&stage};
 tl_pi_module_ci m={.type=16,.size=sizeof(code),.code=code};tl_pi_shader((void *)1,4,&m);
}
uint64_t identity(int mode) {
 tl_pi_graphics p=ci;tl_pi_stage st=stage;p.stages=&st;
 if(mode==1) { tl_pi_module_ci m={.type=16,.size=sizeof(code),.code=code};tl_pi_shader((void *)1,99,&m);st.module=99; }
 if(mode==2)st.name="other";
 if(mode==3)p.subpass=1;
 uint32_t state[8]={20};state[5]=mode==4?2:1;if(mode==4||mode==5)p.assembly=state;
 tl_pi_request r=tl_pi_identify(false,(void *)1,1,&p);return r.id[0];
}
int known_after_destroy(void) {tl_pi_forget_shader((void *)1,4);return tl_pi_identify(false,(void *)1,1,&ci).known[0];}
int test_off(void) {husk_ue4_set_pipeline_diagnostics(false);return tl_pi_identify(false,(void *)1,999,(void *)1).sampled;}
int specialization(int value) {
 tl_pi_map entry={.id=2,.offset=0,.size=sizeof(value)};
 tl_pi_specialization spec={.count=1,.entries=&entry,.size=sizeof(value),.data=&value};
 stage.specialization=&spec;
 tl_pi_request r=tl_pi_identify(false,(void *)1,1,&ci);stage.specialization=NULL;return (int)r.id[0];
}
const char *emit(int feedback_flags,int slow) {
 struct {uint32_t flags;uint64_t duration;} f={(uint32_t)feedback_flags,1000};
 struct {uint32_t type;const void *next;const void *pipeline;uint32_t count;const void *stages;} info={1000192000,NULL,&f,0,NULL};
 tl_pi_graphics p=ci;if(feedback_flags>=0)p.next=&info;
 tl_pi_request r=tl_pi_identify(false,(void *)1,1,&p);
 tl_pi_completed(r,false,slow?20000000:1000000,123456789000ULL,true,0,&p);tl_pi_report();return output;
}
int group_collisions(void) {
 tl_pi_request a={.id={1},.known={1},.sampled=1,.count=1},b=a;b.id[0]=2049;
 tl_pi_completed(a,false,20000000,1,true,0,&ci);tl_pi_completed(b,false,30000000,2,true,0,&ci);tl_pi_completed(a,false,1000000,3,true,0,&ci);
 tl_pi_group groups[4];unsigned n=tl_pi_copy_groups(groups,4);if(n!=2)return 1;
 for(unsigned i=0;i<n;i++){
  if(groups[i].signature==1&&(groups[i].calls!=2||groups[i].slow_calls!=1||groups[i].total_ns!=21000000||groups[i].worst_ns!=20000000||groups[i].valid_feedback))return 2;
  if(groups[i].signature==2049&&groups[i].calls!=1)return 3;
 }return 0;
}
uint64_t state_variant(int kind,int variant){
 tl_pi_graphics p=ci;
 pi_vertex vertex={.type=19};pi_raster raster={.type=23,.line=1};
 pi_depth depth={.type=25,.test=1};pi_blend blend={.type=26,.count=1};uint32_t attachment[8]={0};blend.attachments=attachment;
 pi_multi multi={.type=24,.samples=64};uint32_t mask[2]={UINT32_MAX,UINT32_MAX};
 if(kind==0){raster.cull=variant?2:1;p.raster=&raster;}
 if(kind==1){depth.compare=variant?2:1;p.depth=&depth;}
 if(kind==2){attachment[0]=variant?1:0;p.blend=&blend;}
 if(kind==3){multi.mask=mask;mask[1]=variant?1:UINT32_MAX;p.multisample=&multi;}
 if(kind==4){uint32_t binding[3]={0,(uint32_t)(variant?24:16),0};vertex.bindings=1;vertex.binding_data=binding;p.vertex=&vertex;return tl_pi_identify(false,(void *)1,1,&p).id[0];}
 if(kind==5){pi_viewport viewport={.type=22,.viewports=1,.viewport_data=variant?(void *)1:NULL};uint32_t state=0;pi_dynamic dyn={.type=27,.count=1,.states=&state};p.viewport=&viewport;p.dynamic=&dyn;return tl_pi_identify(false,(void *)1,1,&p).id[0];}
 if(kind==6){raster.discard=1;p.raster=&raster;p.viewport=p.multisample=p.depth=p.blend=variant?(void *)1:NULL;}
 if(kind==7){uint32_t state=1000267003;pi_dynamic dyn={.type=27,.count=1,.states=&state};p.dynamic=&dyn;p.raster=(void *)1;return tl_pi_identify(false,(void *)1,1,&p).known[0];}
 return tl_pi_identify(false,(void *)1,1,&p).id[0];
}
int stage_feedback_counts(void){
 struct {uint32_t flags;uint64_t duration;} pipeline={1,1000},stages[3]={{3,100},{1,200},{2,300}};
 struct {uint32_t type;const void*next;void*pipeline;uint32_t count;void*stages;} fb={1000192000,NULL,&pipeline,3,stages};
 tl_pi_graphics p=ci;tl_pi_stage ss[3]={stage,stage,stage};p.stages=ss;p.count=3;p.next=&fb;tl_pi_request r=tl_pi_identify(false,(void *)1,1,&p);
 tl_pi_completed(r,false,20000000,123,true,0,&p);tl_pi_group g[2];
 return tl_pi_copy_groups(g,2)==1&&g[0].valid_feedback==1&&g[0].application_hits==0&&g[0].stage_feedback_valid==2&&g[0].stage_application_hits==1&&g[0].last_stage_valid_mask==3&&g[0].last_stage_hit_mask==1&&g[0].shader_stages==3&&g[0].shader_hashes[0]!=0?0:1;
}
unsigned bounded(void) {for(unsigned i=0;i<100;i++){tl_pi_request r=tl_pi_identify(false,(void *)1,1,&ci);tl_pi_completed(r,false,20000000,1,true,0,&ci);}return length;}
''')
  lib=root/'identity.so';subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC','-pthread','-I',str(ROOT/'src/translation-layer-next'),str(src),'-o',str(lib)],check=True)
  cls.lib=ctypes.CDLL(str(lib));cls.lib.identity.restype=ctypes.c_uint64;cls.lib.emit.restype=ctypes.c_char_p;cls.lib.state_variant.restype=ctypes.c_uint64
 def setUp(self):self.lib.setup()
 def test_identity_ignores_handles_but_distinguishes_entry_subpass_and_topology(self):
  self.assertEqual(self.lib.identity(0),self.lib.identity(1))
  self.assertNotEqual(self.lib.identity(0),self.lib.identity(2));self.assertNotEqual(self.lib.identity(0),self.lib.identity(3))
  self.assertNotEqual(self.lib.identity(4),self.lib.identity(5))
 def test_specialization_values_change_signature(self):self.assertNotEqual(self.lib.specialization(4),self.lib.specialization(5))
 def test_destroy_invalidation_prevents_false_known_identity(self):self.assertEqual(self.lib.known_after_destroy(),0)
 def test_off_does_not_dereference_pipeline_data(self):self.assertEqual(self.lib.test_off(),0)
 def test_cache_presence_is_not_hit_and_only_valid_feedback_is_reported(self):
  self.assertIn(b'feedback-first unavailable',self.lib.emit(-1,1));self.assertIn(b'feedback-first unavailable',self.lib.emit(2,1))
  self.assertIn(b'valid-no-application-hit',self.lib.emit(1,1));self.assertIn(b'application-cache-hit',self.lib.emit(3,1))
 def test_collision_groups_keep_separate_counts_and_host_costs(self):self.assertEqual(self.lib.group_collisions(),0)
 def test_raster_depth_blend_sample_mask_and_vertex_state_distinguish_groups(self):
  for kind in range(5):self.assertNotEqual(self.lib.state_variant(kind,0),self.lib.state_variant(kind,1))
 def test_dynamic_viewport_and_discard_do_not_read_ignored_pointers(self):
  for kind in (5,6):self.assertEqual(self.lib.state_variant(kind,0),self.lib.state_variant(kind,1))
 def test_extended_dynamic_state_is_explicitly_incomplete(self):self.assertEqual(self.lib.state_variant(7,0),0)
 def test_valid_stage_hits_are_separate_from_pipeline_hits(self):self.assertEqual(self.lib.stage_feedback_counts(),0)
 def test_bounded_slow_events(self):self.assertEqual(self.lib.bounded(),64)
if __name__=='__main__':unittest.main()
