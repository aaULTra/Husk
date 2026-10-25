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
 uint32_t state[8]={0};state[5]=mode==4?2:1;if(mode==4||mode==5)p.assembly=state;
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
unsigned bounded(void) {for(unsigned i=0;i<100;i++){tl_pi_request r=tl_pi_identify(false,(void *)1,1,&ci);tl_pi_completed(r,false,20000000,1,true,0,&ci);}return length;}
''')
  lib=root/'identity.so';subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC','-pthread','-I',str(ROOT/'src/translation-layer-next'),str(src),'-o',str(lib)],check=True)
  cls.lib=ctypes.CDLL(str(lib));cls.lib.identity.restype=ctypes.c_uint64;cls.lib.emit.restype=ctypes.c_char_p
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
 def test_bounded_slow_events(self):self.assertEqual(self.lib.bounded(),64)
if __name__=='__main__':unittest.main()
