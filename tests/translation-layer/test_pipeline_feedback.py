#!/usr/bin/env python3
"""Actual capability/request helper: never invent cache hits or mutate guest input."""
import ctypes, os, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class PipelineFeedbackTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);p=Path(cls.tmp.name)
  (p/'test.c').write_text(r'''
#include <stdlib.h>
static int allocations,fail_at;
static void *allocate(size_t n,size_t size){if(++allocations==fail_at)return NULL;return calloc(n,size);}
#define calloc allocate
#include "husk-tl-pipeline-feedback.c"
static int offers,calls,enumerations,errors,failure;
static const tl_pf_device_info *original;
static int create(void*p,const tl_pf_device_info *ci,const void*a,void**out){
 calls++;if(p!=(void *)1||a!=(void *)3||ci->queues!=original->queues||ci->features!=original->features||ci->pNext!=original->pNext||ci->flags!=original->flags)errors++;
 *out=(void *)7;
 bool added=ci->extCount!=original->extCount;
 if(added&&(ci->extCount!=original->extCount+1||strcmp(ci->exts[ci->extCount-1],extension_name)))errors++;
 return added?failure:0;
}
static int enumerate(void*p,const char*layer,uint32_t*n,tl_pf_extension*out){
 enumerations++;if(p!=(void *)1||layer)errors++;
 if(!out){*n=offers?1:0;return 0;}*n=1;snprintf(out[0].name,256,"%s",extension_name);return 0;
}
static tl_pi_graphics ci[2];static tl_pi_stage stages[2];
static void init(void){
 allocations=fail_at=calls=enumerations=errors=failure=0;offers=1;
 husk_ue4_set_pipeline_feedback(true);tl_pf_activate("Dungeons");
 stages[0]=(tl_pi_stage){.type=18,.stage=1};stages[1]=(tl_pi_stage){.type=18,.stage=16};
 ci[0]=(tl_pi_graphics){.type=28,.count=1,.stages=stages,.flags=9,.base_index=-1};
 ci[1]=(tl_pi_graphics){.type=28,.count=2,.stages=stages,.flags=17,.base_index=0};
}
int run(int mode){
 init();const char *names[]={"Other",extension_name};
 tl_pf_device_info info={.sType=3,.pNext=(void *)23,.flags=37,.queues=(void *)41,.features=(void *)43,.extCount=mode==3?2:1,.exts=names};
 original=&info;tl_pf_device_info saved=info;void*device=NULL;
 if(mode==0)husk_ue4_set_pipeline_feedback(false),tl_pf_activate("Dungeons");
 if(mode==2){offers=0;}
 if(mode==4){failure=-7;}
 if(mode==5){failure=-4;}
 if(mode==6)fail_at=2;
 if(mode==12)tl_pf_activate("Other");
 int result=tl_pf_create_device((void *)1,&info,(void *)3,&device,create,enumerate);
 if(memcmp(&saved,&info,sizeof(info))||errors)return 1;
 if(mode==5)return result==-4&&calls==1?0:2;
 if(result||device!=(void *)7)return 3;
 if(mode==4&&calls!=2)return 4;
 if((mode==0||mode==3||mode==12)&&enumerations)return 5;
 tl_pf_stats st;tl_pf_snapshot(&st);tl_pf_batch batch;
 if(mode==0||mode==2||mode==4||mode==6||mode==12){const void*view=tl_pf_prepare(false,device,65,(void *)1,&batch);tl_pf_release(&batch);return view==(void *)1&&!st.enabled_devices?0:6;}
 if(mode==7){allocations=0;fail_at=1;const void*view=tl_pf_prepare(false,device,2,ci,&batch);tl_pf_release(&batch);return view==ci?0:7;}
 if(mode==8){tl_pf_info guest={.type=FEEDBACK_TYPE};ci[0].next=&guest;tl_pi_graphics copy[2];memcpy(copy,ci,sizeof(ci));const tl_pi_graphics *view=tl_pf_prepare(false,device,2,ci,&batch);int ok=view!=ci&&view[0].next==&guest&&view[1].next!=ci[1].next&&batch.injected==1&&!memcmp(ci,copy,sizeof(ci));tl_pf_release(&batch);return ok?0:8;}
 if(mode==9){struct node {uint32_t type;const void*next;}chain={1,NULL};chain.next=&chain;ci[0].next=ci[1].next=&chain;const void*view=tl_pf_prepare(false,device,2,ci,&batch);tl_pf_release(&batch);return view==ci?0:9;}
 if(mode==10){tl_pf_forget_device(device);const void*view=tl_pf_prepare(false,device,2,ci,&batch);tl_pf_release(&batch);tl_pf_snapshot(&st);return view==ci&&!st.enabled_devices?0:10;}
 if(mode==11){tl_pi_compute compute={.type=29,.stage=stages[0],.flags=55};const tl_pi_compute *view=tl_pf_prepare(true,device,1,&compute,&batch);const tl_pf_info *f=view->next;int ok=view!=&compute&&view->flags==55&&compute.next==NULL&&f&&f->count==1&&f->stages&&f->pipeline;tl_pf_release(&batch);return ok?0:11;}
 tl_pi_graphics saved_ci[2];memcpy(saved_ci,ci,sizeof(ci));
 const tl_pi_graphics *view=tl_pf_prepare(false,device,2,ci,&batch);
 if(view==ci||batch.injected!=2||memcmp(ci,saved_ci,sizeof(ci)))return 12;
 for(unsigned i=0;i<2;i++){
  tl_pi_graphics expected=ci[i],actual=view[i];const tl_pf_info*f=actual.next;actual.next=expected.next;
  if(memcmp(&actual,&expected,sizeof(actual))||!f||f->count!=ci[i].count||f->next!=ci[i].next||!f->stages||!f->pipeline)return 13;
  for(unsigned j=0;j<f->count;j++)if(f->stages[j].flags||f->stages[j].duration)return 14;
 }
 tl_pf_release(&batch);tl_pf_release(&batch);return 0;
}
'''.replace('#include <stdlib.h>','#include <stdlib.h>\n#include <stdio.h>'))
  lib=p/'test.so';subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC','-pthread','-I',str(ROOT/'src/translation-layer-next'),str(p/'test.c'),'-o',str(lib)],check=True);cls.lib=ctypes.CDLL(str(lib))
 def test_off_passes_original_and_never_reads_pipeline_input(self):self.assertEqual(self.lib.run(0),0)
 def test_supported_extension_and_feedback_copy_preserve_guest_fields_order_and_lifetimes(self):self.assertEqual(self.lib.run(1),0)
 def test_unsupported_driver_keeps_original_device_and_pipeline_inputs(self):self.assertEqual(self.lib.run(2),0)
 def test_guest_extension_is_not_duplicated(self):self.assertEqual(self.lib.run(3),0)
 def test_only_extension_not_present_allows_diagnostic_fallback(self):self.assertEqual(self.lib.run(4),0)
 def test_device_loss_is_not_retried(self):self.assertEqual(self.lib.run(5),0)
 def test_device_extension_allocation_failure_falls_back(self):self.assertEqual(self.lib.run(6),0)
 def test_batch_allocation_failure_leaves_original_infos(self):self.assertEqual(self.lib.run(7),0)
 def test_guest_feedback_chain_is_preserved_without_duplicate(self):self.assertEqual(self.lib.run(8),0)
 def test_unbounded_chain_is_not_injected(self):self.assertEqual(self.lib.run(9),0)
 def test_device_teardown_invalidates_feedback_capability(self):self.assertEqual(self.lib.run(10),0)
 def test_compute_has_valid_stage_feedback_storage(self):self.assertEqual(self.lib.run(11),0)
 def test_other_project_never_changes_device_extensions(self):self.assertEqual(self.lib.run(12),0)
if __name__=='__main__':unittest.main()
