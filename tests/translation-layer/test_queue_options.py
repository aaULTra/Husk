#!/usr/bin/env python3
"""Actual launch environment controls and size-checked runtime observation."""
import subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];TL=ROOT/'src/translation-layer-next'
class QueueOptionsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);p=Path(cls.tmp.name)
  (p/'main.c').write_text(r'''
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <string.h>
#include <stdlib.h>
#include "husk-tl-queue-options.h"
int main(int argc,char**argv){assert(argc==2);int mode=atoi(argv[1]);
 setenv("MVK_CONFIG_PREFILL_METAL_COMMAND_BUFFERS","1",1);setenv("MVK_CONFIG_MAX_ACTIVE_METAL_COMMAND_BUFFERS_PER_QUEUE","32",1);
 if(mode==0)husk_ue4_set_queue_options(-1,0);
 else if(mode==1)husk_ue4_set_queue_options(0,8);
 else if(mode==2)husk_ue4_set_queue_options(1,16);
 else if(mode==3)husk_ue4_set_queue_options(2,64);
 else husk_ue4_set_queue_options(3,7);
 tl_queue_options_environment();tl_queue_options_stats s;tl_queue_options_snapshot(&s);
 assert(s.applied&&!s.observed&&!s.environment_error);
 if(mode==0||mode==4){assert(s.requested_prefill==-1&&s.requested_limit==0);assert(!strcmp(getenv("MVK_CONFIG_PREFILL_METAL_COMMAND_BUFFERS"),"1")&&!strcmp(getenv("MVK_CONFIG_MAX_ACTIVE_METAL_COMMAND_BUFFERS_PER_QUEUE"),"32"));}
 else {assert(atoi(getenv("MVK_CONFIG_PREFILL_METAL_COMMAND_BUFFERS"))==s.requested_prefill&&atoi(getenv("MVK_CONFIG_MAX_ACTIVE_METAL_COMMAND_BUFFERS_PER_QUEUE"))==(int)s.requested_limit);}
 int pre=s.requested_prefill;unsigned limit=s.requested_limit;husk_ue4_set_queue_options(2,32);tl_queue_options_environment();tl_queue_options_snapshot(&s);assert(s.requested_prefill==pre&&s.requested_limit==limit);
 uint32_t prefix[]={0,1,1,2,8};tl_queue_options_observe(5,prefix,sizeof(prefix));tl_queue_options_snapshot(&s);assert(s.observed&&s.actual_synchronous==1&&s.actual_prefill==2&&s.actual_limit==8);
 tl_queue_options_observe(0,prefix,16);tl_queue_options_snapshot(&s);assert(!s.observed);
 tl_queue_options_observe(-3,(void*)1,20);tl_queue_options_snapshot(&s);assert(!s.observed&&s.query_result==-3);
 tl_queue_options_observe(0,NULL,20);tl_queue_options_snapshot(&s);assert(!s.observed);return 0;
}
''')
  cls.exe=p/'check';subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(TL),str(p/'main.c'),str(TL/'husk-tl-queue-options.c'),'-pthread','-o',str(cls.exe)],check=True)
 def run_case(self,n):subprocess.run([str(self.exe),str(n)],check=True,timeout=10)
 def test_default_preserves_inherited_environment_and_late_changes_are_frozen(self):self.run_case(0)
 def test_explicit_no_prefill_and_eight_buffer_limit(self):self.run_case(1)
 def test_deferred_prefill_and_sixteen_buffer_limit(self):self.run_case(2)
 def test_immediate_prefill_and_sixtyfour_buffer_limit(self):self.run_case(3)
 def test_unsafe_no_autorelease_mode_and_invalid_limit_rejected(self):self.run_case(4)
if __name__=='__main__':unittest.main()
