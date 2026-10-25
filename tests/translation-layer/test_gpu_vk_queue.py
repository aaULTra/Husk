#!/usr/bin/env python3
"""Compile actual Vulkan queue discovery wrappers, including absent optional export."""
import ctypes, os, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class QueueDiscoveryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);p=Path(cls.tmp.name)
  source=(ROOT/'src/translation-layer-next/husk-tl-vulkan.m').read_text()
  wrappers=source[source.index('static void observe_game_queue('):source.index('/* M9 observation only')]
  harness=r'''
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
static struct{void *lib;}V={(void *)1};
static int sharp,available,calls,registered,failures;
bool tl_ue4_sharp_graphics_enabled(void){return sharp;}
void tl_gput_native_register(void *device,void *metal){registered++;if(device!=(void *)7||metal!=(void *)13)failures++;}
static void host1(void*d,uint32_t f,uint32_t i,void **out){calls++;if(d!=(void *)7||f!=2||i!=3)failures++;*out=(void *)11;}
static void host2(void*d,const void*info,void **out){calls++;if(d!=(void *)7||info!=(void *)17)failures++;*out=(void *)11;}
static void export_queue(void*q,void **out){if(q!=(void *)11)failures++;*out=(void *)13;}
static void *fake_dlsym(void*lib,const char*name){(void)lib;if(!strcmp(name,"vkGetDeviceQueue"))return(void *)host1;if(!strcmp(name,"vkGetDeviceQueue2"))return(void *)host2;if(available&&!strcmp(name,"vkGetMTLCommandQueueMVK"))return(void *)export_queue;return NULL;}
#define dlsym fake_dlsym
'''
  harness+=wrappers+r'''
int run(int enabled,int export_present){sharp=enabled;available=export_present;calls=registered=failures=0;void*q=NULL;
w_vkGetDeviceQueue((void *)7,2,3,&q);if(q!=(void *)11)return 1;
w_vkGetDeviceQueue2((void *)7,(void *)17,&q);if(q!=(void *)11)return 2;
return calls==2&&!failures&&registered==(enabled&&export_present?2:0)?0:3;}
'''
  (p/'test.c').write_text(harness);subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC',str(p/'test.c'),'-o',str(p/'test.so')],check=True);cls.lib=ctypes.CDLL(str(p/'test.so'))
 def test_queue_calls_and_outputs_are_forwarded(self):self.assertEqual(self.lib.run(1,1),0)
 def test_absent_optional_moltenvk_export_is_safe(self):self.assertEqual(self.lib.run(1,0),0)
 def test_non_sharp_path_is_not_registered(self):self.assertEqual(self.lib.run(0,1),0)
if __name__=='__main__':unittest.main()
