#!/usr/bin/env python3
"""Actual process collector handles short public Mach revisions and invalid data."""
import subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class ProcessMetricTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);p=Path(cls.tmp.name)
  source=(ROOT/'src/translation-layer-next/husk-tl-efficiency.c').read_text();body=source[source.index('void tl_em_process_sample('):source.index('void tl_em_cpu_work_enable(')]
  (p/'main.c').write_text(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include "husk-tl-efficiency.h"
#define __APPLE__ 1
#define TARGET_OS_IOS 0
#define KERN_SUCCESS 0
#define TASK_ABSOLUTETIME_INFO 1
#define TASK_ABSOLUTETIME_INFO_COUNT 8
#define TASK_VM_INFO 2
#define TASK_VM_INFO_COUNT 10
#define TASK_VM_INFO_REV3_COUNT 10
typedef int32_t integer_t;typedef uint32_t mach_msg_type_number_t;typedef integer_t*task_info_t;
typedef struct{uint64_t total_user,total_system,other[2];}task_absolutetime_info_data_t;
typedef struct{uint64_t unused[2],phys_footprint;int64_t ledger_phys_footprint_peak;}task_vm_info_data_t;
typedef struct{unsigned numer,denom;}mach_timebase_info_data_t;
static int mode,vm_calls;
static int mach_task_self(void){return 1;}
static int mach_timebase_info(mach_timebase_info_data_t*out){out->numer=1;out->denom=mode==6?0:1;return 0;}
static int task_info(int task,int flavor,task_info_t raw,mach_msg_type_number_t*count){
 assert(task==1);
 if(flavor==TASK_ABSOLUTETIME_INFO){task_absolutetime_info_data_t*out=(void*)raw;out->total_user=1000;out->total_system=2000;*count=mode==5?1:8;return 0;}
 vm_calls++;task_vm_info_data_t*out=(void*)raw;out->phys_footprint=100;out->ledger_phys_footprint_peak=mode==4?50:200;
 if(mode==1)*count=4;else if(mode==2)*count=6;else *count=8;
 return mode==3?-1:0;
}
/* ACTUAL */
int main(int argc,char**argv){assert(argc==2);mode=atoi(argv[1]);tl_em_process s;tl_em_process_sample(mode!=7,&s);
 if(mode==5||mode==6)assert(s.cpu_seconds==-1);else assert(s.cpu_seconds>0);
 if(mode==1||mode==3||mode==7)assert(s.footprint_bytes==-1&&s.peak_bytes==-1);
 else if(mode==2||mode==4)assert(s.footprint_bytes==100&&s.peak_bytes==-1);
 else assert(s.footprint_bytes==100&&s.peak_bytes==200);
 if(mode==7){assert(!vm_calls);}return 0;
}
'''.replace('/* ACTUAL */',body))
  cls.exe=p/'check';subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'src/translation-layer-next'),str(p/'main.c'),'-o',str(cls.exe)],check=True)
 def run_case(self,n):subprocess.run([str(self.exe),str(n)],check=True)
 def test_supported_footprint_and_lifetime_peak(self):self.run_case(0)
 def test_short_revision_cannot_read_current_footprint_or_peak(self):self.run_case(1)
 def test_current_only_revision_keeps_peak_unavailable(self):self.run_case(2)
 def test_failed_vm_read_does_not_fabricate_zero(self):self.run_case(3)
 def test_inconsistent_peak_below_current_is_unavailable(self):self.run_case(4)
 def test_short_cpu_revision_is_unavailable(self):self.run_case(5)
 def test_invalid_timebase_cannot_export_infinity(self):self.run_case(6)
 def test_memory_off_performs_no_vm_query(self):self.run_case(7)
if __name__=='__main__':unittest.main()
