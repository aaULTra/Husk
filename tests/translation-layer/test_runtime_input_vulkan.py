#!/usr/bin/env python3
"""Production controller fast path and Vulkan dispatch, with host API facades."""
from pathlib import Path
import os,re,subprocess,tempfile,unittest
from test_lifecycle_resilience import function
ROOT=Path(__file__).resolve().parents[2];TL=ROOT/'src/translation-layer-next'
class RuntimeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);p=Path(cls.tmp.name)
  pad=(TL/'husk-tl-gamepad.c').read_text();pad=pad[pad.index('#define MAX_AXES'):pad.index('/* ------------------------------------------------------------- InputDevice */')]
  (p/'pad.c').write_text(r'''
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <math.h>
#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "husk-tl-gamepad.h"
static unsigned clocks,downs,ups,motions;static int last_key;
static int counted_clock(clockid_t clock,struct timespec*t){clocks++;return clock_gettime(clock,t);}
#define clock_gettime counted_clock
void tl_log_line(const char *fmt,...){(void)fmt;}
static jobj event;
jobj *tl_input_key_event(int a,int k,int d,int s,int r,int64_t down,int64_t ms){(void)a;(void)k;(void)d;(void)s;(void)r;(void)down;(void)ms;return &event;}
jobj *tl_input_joystick_event(int d,int s,int64_t down,int64_t ms,const float*axes){(void)d;(void)s;(void)down;(void)ms;(void)axes;return &event;}
'''+pad+r'''
static void key(jobj*ev,int dev,int action,int code,int64_t down,int64_t ms){(void)ev;(void)dev;(void)down;(void)ms;last_key=code;if(action==0)downs++;else ups++;tl_pad_state copy;assert(tl_pad_read(0,&copy));}
static void motion(jobj*ev,int dev,int src,int64_t down,int64_t ms){(void)ev;(void)dev;(void)src;(void)down;(void)ms;motions++;}
int main(int argc,char**argv){assert(argc==2);tl_pad_sink sink={key,motion};tl_pad_connect(0,"fixture");tl_pad_set_sink(&sink);tl_pad_state state={0};
 if(!strcmp(argv[1],"fast")){
  state.buttons=1u<<TL_PAD_A;state.lx=.25f;tl_pad_update(0,&state);assert(downs==1&&motions==1);
  unsigned before=clocks;for(unsigned i=0;i<100000;i++)tl_pad_update(0,&state);assert(clocks==before&&downs==1&&motions==1);
  state.buttons=0;tl_pad_update(0,&state);assert(ups==1&&last_key==96);
 }else if(!strcmp(argv[1],"accumulate")){
  tl_pad_update(0,&state);motions=0;state.lx=.002f;tl_pad_update(0,&state);assert(!motions);tl_pad_update(0,&state);assert(!motions);state.lx=.004f;tl_pad_update(0,&state);assert(motions==1);
 }else if(!strcmp(argv[1],"sink")){
  tl_pad_set_sink(NULL);state.buttons=1u<<TL_PAD_A;state.lt=.6f;state.lx=.5f;tl_pad_update(0,&state);assert(!downs&&!motions);
  tl_pad_set_sink(&sink);tl_pad_update(0,&state);assert(downs==2&&motions==1);
  tl_pad_update(0,&state);assert(downs==2&&motions==1);
 }else if(!strcmp(argv[1],"trigger")){
  state.lt=.6f;tl_pad_update(0,&state);assert(downs==1&&last_key==104);state.lt=.4f;tl_pad_update(0,&state);assert(!ups);state.lt=.2f;tl_pad_update(0,&state);assert(ups==1);
 }else if(!strcmp(argv[1],"mapping")){
  setenv("TL_PAD_DPAD","both",1);state.buttons=1u<<TL_PAD_DPAD_RIGHT;tl_pad_update(0,&state);assert(downs==1&&P.axes[0][AXIS_HAT_X]==1);
  setenv("TL_PAD_DPAD","keys",1);tl_pad_set_sink(&sink);tl_pad_update(0,&state);assert(P.axes[0][AXIS_HAT_X]==0&&downs==2);
 }else if(!strcmp(argv[1],"neutral")){
  state.buttons=1u<<TL_PAD_A;state.lt=.6f;state.rx=1;tl_pad_update(0,&state);assert(downs==2);
  state=(tl_pad_state){0};tl_pad_update(0,&state);assert(ups==2&&P.axes[0][AXIS_RZ]==0);tl_pad_disconnect(0);assert(!tl_pad_connected(0)&&!tl_pad_read(0,&state));
 }else assert(0);
 assert(!tl_pad_connected(-1)&&!tl_pad_connected(TL_PADS)&&!tl_pad_read(0,NULL));return 0;
}
''')
  vk=(TL/'husk-tl-vulkan.m').read_text();table=vk[vk.index('static const struct { const char *name; void *fn; } k_over[]'):vk.index('static void *overridden(')]
  names=re.findall(r'\{ "[^"]+", (\w+) \}',table);query_names={'w_vkGetInstanceProcAddr','w_vkGetDeviceProcAddr'}
  declarations='\n'.join('static void '+name+'(void){}'for name in names if name not in query_names)
  source=r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include "husk-tl-vulkan-routing.h"
static int identification,inventory;static void host(void){}
static void *gdpa(void*d,const char*n){(void)d;(void)n;return(void*)host;}
static void *gipa(void*d,const char*n){(void)d;(void)n;return(void*)host;}
static struct{void *lib;void*(*gipa)(void*,const char*);}V={(void*)1,gipa};
static bool vk_ready(void){return true;}static bool tl_pi_active(void){return identification;}static bool tl_ri_active(void){return inventory;}
static void resolve_feature_hooks(void*i){(void)i;}
#define LOG(...) do{}while(0)
static void *lookup(void*l,const char*n){(void)l;return !strcmp(n,"vkGetDeviceProcAddr")?(void*)gdpa:(void*)host;}
#define dlsym lookup
static void *w_vkGetInstanceProcAddr(void*,const char*);static void *w_vkGetDeviceProcAddr(void*,const char*);
'''+declarations+'\n'+table+'\n'+function(vk,'static void *overridden(')+'\n'+function(vk,'static void *w_vkGetInstanceProcAddr(void *instance, const char *name)\n{')+'\n'+function(vk,'static void *w_vkGetDeviceProcAddr(void *device, const char *name)\n{')+'\n'+function(vk,'void *tl_vk_resolve(')+r'''
int main(void){const char*pure[]={"vkCreateShaderModule","vkDestroyShaderModule","vkCreateSampler","vkDestroySampler","vkCreateDescriptorSetLayout","vkDestroyDescriptorSetLayout","vkCreatePipelineLayout","vkDestroyPipelineLayout","vkCreateRenderPass","vkCreateRenderPass2","vkCreateRenderPass2KHR","vkDestroyRenderPass","vkDestroyPipeline"};
 for(unsigned enabled=0;enabled<2;enabled++){identification=enabled;
  for(unsigned i=0;i<sizeof(pure)/sizeof(*pure);i++){
   void *a=w_vkGetInstanceProcAddr((void*)1,pure[i]),*b=w_vkGetDeviceProcAddr((void*)1,pure[i]),*c=tl_vk_resolve(pure[i]);
   assert(a==b&&b==c);assert(enabled?a!=(void*)host:a==(void*)host);
  }
 }
 identification=0;const char*functional[]={"vkCreateGraphicsPipelines","vkCreateComputePipelines","vkCreatePipelineCache","vkDestroyPipelineCache","vkMergePipelineCaches","vkGetDeviceQueue","vkQueueSubmit","vkQueuePresentKHR","vkAcquireNextImageKHR","vkDestroyDevice","vkCreateDevice","vkCmdBindVertexBuffers"};
 for(unsigned i=0;i<sizeof(functional)/sizeof(*functional);i++)assert(tl_vk_resolve(functional[i])!=(void*)host);
 inventory=0;assert(tl_vk_resolve("vkCmdBeginRenderPass")==host);inventory=1;assert(tl_vk_resolve("vkCmdBeginRenderPass")!=host);
 assert(!w_vkGetInstanceProcAddr(NULL,NULL)&&!w_vkGetDeviceProcAddr(NULL,NULL));
 const char*bind="vkCmdBindVertexBuffers";
 assert(w_vkGetDeviceProcAddr((void*)5,bind)!=(void*)host);
 tl_vk_route_device((void*)5,false);assert(w_vkGetDeviceProcAddr((void*)5,bind)==(void*)host);
 assert(w_vkGetInstanceProcAddr((void*)5,bind)!=(void*)host&&tl_vk_resolve(bind)!=(void*)host);
 tl_vk_route_device((void*)6,true);assert(w_vkGetDeviceProcAddr((void*)6,bind)!=(void*)host);
 tl_vk_route_forget((void*)5);assert(w_vkGetDeviceProcAddr((void*)5,bind)!=(void*)host);
 tl_vk_route_device((void*)5,true);assert(w_vkGetDeviceProcAddr((void*)5,bind)!=(void*)host);
 for(uintptr_t i=10;i<30;i++)tl_vk_route_device((void*)i,false);
 assert(w_vkGetDeviceProcAddr((void*)29,bind)!=(void*)host);return 0;}
'''
  (p/'vulkan.c').write_text(source);cls.pad=p/'pad';cls.vk=p/'vulkan'
  for name,exe in [('pad',cls.pad),('vulkan',cls.vk)]:subprocess.run([os.environ.get('CC','cc'),'-std=c11','-O2','-Wall','-Wextra','-Werror','-pthread','-I',str(TL),str(p/(name+'.c')),'-lm','-o',str(exe)],check=True)
 def case(self,name):subprocess.run([str(self.pad),name],check=True,timeout=5)
 def test_identical_updates_skip_timestamp_and_axis_work(self):self.case('fast')
 def test_small_axis_changes_accumulate_against_last_emitted_axes(self):self.case('accumulate')
 def test_initial_sink_receives_held_buttons_triggers_and_motion(self):self.case('sink')
 def test_trigger_hysteresis_is_preserved(self):self.case('trigger')
 def test_mapping_epoch_forces_correct_republication(self):self.case('mapping')
 def test_frontend_neutralisation_releases_buttons_and_axes_before_disconnect(self):self.case('neutral')
 def test_all_proc_lookup_paths_bypass_only_disabled_observational_wrappers(self):subprocess.run([str(self.vk)],check=True,timeout=5)
if __name__=='__main__':unittest.main()
