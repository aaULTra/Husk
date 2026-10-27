#!/usr/bin/env python3
"""Compile the actual opt-in driver reader with deterministic API substitutes."""
import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DriverProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        root = Path(cls.tmp.name)
        source = r'''
#define _DARWIN_C_SOURCE 1
#define _POSIX_C_SOURCE 200809L
#include <stdarg.h>
#include <stdio.h>
#include "husk-tl-driver-profile.c"
#include "husk-tl-swapchain-budget.h"
#include "husk-tl-vulkan-routing.h"
static void tl_npa_device(void *device){(void)device;}
static char output[32768];
static unsigned used, api_calls, event_count;
static size_t reported_size;
static int read_failure;
void tl_log_line(const char *format, ...) {
 if (used>=sizeof(output)-2) return;
 va_list args;va_start(args,format);
 int n=vsnprintf(output+used,sizeof(output)-used,format,args);va_end(args);
 if (n<0) return;
 unsigned remaining=(unsigned)sizeof(output)-used;
 used+=(unsigned)n<remaining?(unsigned)n:remaining-1;
 if(used<sizeof(output)-1)output[used++]='\n';
 output[used]=0;
}
static int fake_api(void *device,void *out,size_t *size) {
 (void)device;++api_calls;
 if(!out){*size=reported_size;return 0;}
 statistics *s=out;memset(s,0,sizeof(*s));
 for(unsigned i=0;i<24;i++)s->values[i]=(tracker){event_count,5,4,3,1,10};
 s->values[23].average=999999; /* memory is not a duration */
 *size=read_failure==2?sizeof(*s)-8:sizeof(*s);
 if(read_failure==3)s->values[1].average=NAN;
 return read_failure==1?5:0;
}
void setup(int on,int bytes,const char *version) {
 enabled=compatible=false;profile_device=NULL;used=api_calls=event_count=0;
 output[0]=0;reported_size=(size_t)bytes;read_failure=0;
 unsetenv("MVK_CONFIG_PERFORMANCE_TRACKING");unsetenv("MVK_CONFIG_PERFORMANCE_LOGGING_FRAME_COUNT");
 tl_dp_set_api(fake_api,version);husk_ue4_set_driver_profiling(on!=0);
}
void clear_log(void){used=0;output[0]=0;}
const char *log_text(void){return output;}
unsigned calls(void){return api_calls;}
void events(unsigned count){event_count=count;}
void fail_read(int mode){read_failure=mode;}
int environment_enabled(void){const char *s=getenv("MVK_CONFIG_PERFORMANCE_TRACKING");return s&&!strcmp(s,"1");}
int structured_copy(int mode){
 tl_dp_device((void*)1);event_count=4;tl_dp_report();unsigned before=api_calls;
 tl_dp_phase rows[24];tl_dp_info info;unsigned n=tl_dp_copy(rows,24,&info);
 if(n!=23||!info.available||info.serial!=1||info.previous_query_ns||!info.queried_ns||api_calls!=before)return 1;
 for(unsigned i=0;i<n;i++)if(rows[i].phase>=23||rows[i].new_calls!=4||!rows[i].values_valid||!rows[i].estimated_total_valid||rows[i].estimated_new_total_ms!=12)return 2;
 if(mode==1){event_count=5;tl_dp_report();n=tl_dp_copy(rows,24,&info);if(n!=23||info.serial!=2||!info.previous_query_ns||rows[0].new_calls!=1||rows[0].estimated_new_total_ms!=3)return 3;}
 if(mode==2){event_count=1;tl_dp_report();n=tl_dp_copy(rows,24,&info);if(n!=23||!rows[0].reset||rows[0].estimated_total_valid)return 4;}
 if(mode==3){event_count=5;read_failure=3;tl_dp_report();n=tl_dp_copy(rows,24,&info);if(n!=22||info.invalid_values!=1)return 5;for(unsigned i=0;i<n;i++)if(rows[i].phase==1)return 6;}
 return 0;
}
int exercise_busy_mutex(void){unsigned before=api_calls;pthread_mutex_lock(&profile_mu);tl_dp_report();pthread_mutex_unlock(&profile_mu);return api_calls==before;}
'''
        vulkan = (ROOT/'src/translation-layer-next/husk-tl-vulkan.m').read_text()
        start = vulkan.index('static pfn_create_device g_real_create_device;')
        device_prefix = vulkan[start:vulkan.index('    uint32_t base[N_FEATURES]',start)]
        source += r'''
#define VK_SUCCESS 0
#include "husk-tl-pipeline-feedback.h"
typedef tl_pf_device_info vk_device_ci;
typedef tl_pf_create_fn pfn_create_device;
static tl_pf_enum_fn g_real_enum_dev_ext;
static struct { void *lib; } V = {.lib=(void *)1};
static int create_status, forwarded, store_devices;
static bool dxvk_game(void){return false;}
static void properties(void *pd,void *out){(void)pd;memset(out,0,4096);}
static void *fake_dlsym(void *lib,const char *name){(void)lib;(void)name;return (void *)properties;}
#define dlsym fake_dlsym
void tl_pc_device(void *d,uint32_t v,uint32_t id,const uint8_t uuid[16]){(void)d;(void)v;(void)id;(void)uuid;++store_devices;}
static int host_create(void *pd,const tl_pf_device_info *ci,const void *a,void **out){
 forwarded=pd==(void *)3&&ci==(void *)5&&a==(void *)7;*out=(void *)1;return create_status;
}
''' + device_prefix + '    return -4;\n}\n' + r'''
int exercise_create(int status){
 create_status=status;store_devices=forwarded=0;g_real_create_device=host_create;
 void *out=NULL;int result=w_vkCreateDevice((void *)3,(void *)5,(void *)7,&out);
 if(result!=status||out!=(void *)1||!forwarded)return 1;
 if(status==0)return profile_device==(void *)1&&store_devices==1?0:2;
 return profile_device==NULL&&store_devices==0?0:3;
}
'''
        (root / 'test.c').write_text(source)
        tl = ROOT / 'src/translation-layer-next'
        subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-shared', '-fPIC', '-pthread', '-I', str(tl), str(root/'test.c'), str(tl/'husk-tl-pipeline-feedback.c'), str(tl/'husk-tl-swapchain-budget.c'),
                        '-o', str(root/'profile.so')], check=True)
        cls.lib = ctypes.CDLL(str(root/'profile.so'))
        cls.lib.setup.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p]
        cls.lib.tl_dp_device.argtypes = [ctypes.c_void_p]
        cls.lib.tl_dp_forget.argtypes = [ctypes.c_void_p]
        cls.lib.log_text.restype = ctypes.c_char_p

    def setUp(self):
        self.lib.setup(1, 1152, b'1.4.2')

    def log(self):
        return self.lib.log_text().decode()

    def test_off_mode_has_no_driver_queries_or_tracking_environment(self):
        self.lib.setup(0, 1152, b'1.4.2')
        self.lib.tl_dp_device(1); self.lib.tl_dp_report(); self.lib.tl_dp_forget(1)
        self.assertEqual(self.lib.calls(), 0)
        self.assertEqual(self.lib.environment_enabled(), 0)

    def test_exact_abi_and_known_version_are_required_before_reading_statistics(self):
        for size, version in ((1144,b'1.4.2'), (1160,b'1.4.2'), (1152,b'1.4.3'), (1152,None)):
            self.lib.setup(1,size,version); self.lib.tl_dp_device(1)
            before=self.lib.calls(); self.lib.tl_dp_report()
            self.assertEqual(self.lib.calls(),before)
            self.assertIn('unavailable/mismatched',self.log())

    def test_stats_labels_distinguish_activity_latency_and_lifetime_aggregates(self):
        self.lib.tl_dp_device(1); self.lib.events(3); self.lib.tl_dp_report()
        log=self.log()
        for phase in ('SPIR-V-to-MSL','Metal-library-compile','Metal-pipeline-compile','command-encoding',
                      'submit-to-encoding-wait','drawable-retrieval','commit-to-completion-callback-latency'):
            self.assertIn(phase+' new 3 total 3, avg 3.000 ms',log)
        self.assertIn('NOT pure GPU execution',log)
        self.assertIn('avg/max=lifetime',log)
        self.assertNotIn('GPU-memory-KiB new',log)
        self.assertEqual(self.lib.environment_enabled(),1)

    def test_only_new_activities_are_reported_and_counter_resets_are_explicit(self):
        self.lib.tl_dp_device(1); self.lib.events(4); self.lib.tl_dp_report(); self.lib.clear_log()
        self.lib.tl_dp_report(); self.assertNotIn('ue4 driver phase:',self.log())
        self.lib.events(5); self.lib.tl_dp_report(); self.assertIn('new 1 total 5',self.log())
        self.lib.events(1); self.lib.tl_dp_report(); self.assertIn('counter reset/wrap',self.log())

    def test_incomplete_reads_stop_sampling_without_interpreting_prefixes(self):
        for mode in (1,2):
            self.setUp(); self.lib.tl_dp_device(1); self.lib.events(3); self.lib.fail_read(mode)
            self.lib.tl_dp_report(); before=self.lib.calls(); self.lib.tl_dp_report()
            self.assertEqual(self.lib.calls(),before)
            self.assertIn('no prefix interpretation',self.log())
            self.assertNotIn('ue4 driver phase:',self.log())

    def test_teardown_removes_handle_and_new_device_restarts_counters(self):
        self.lib.tl_dp_device(1); self.lib.events(4); self.lib.tl_dp_report(); self.lib.tl_dp_forget(1)
        before=self.lib.calls(); self.lib.tl_dp_report(); self.assertEqual(self.lib.calls(),before)
        self.lib.tl_dp_device(2); self.lib.clear_log(); self.lib.events(1); self.lib.tl_dp_report()
        self.assertIn('new 1 total 1',self.log()); self.assertNotIn('counter reset/wrap',self.log())

    def test_busy_diagnostic_mutex_skips_instead_of_waiting(self):
        self.lib.tl_dp_device(1)
        self.assertEqual(self.lib.exercise_busy_mutex(),1)

    def test_real_android_device_creation_path_registers_only_successful_device(self):
        for status in (0,-4):
            self.setUp()
            self.assertEqual(self.lib.exercise_create(status),0)

    def test_nonfinite_counters_are_not_emitted_as_valid_timings(self):
        self.lib.tl_dp_device(1); self.lib.events(1); self.lib.fail_read(3); self.lib.tl_dp_report()
        self.assertNotIn('SPIR-V-to-MSL new',self.log())
        self.assertIn('Metal-library-compile new',self.log())


    def test_structured_copy_reuses_queries_and_distinguishes_estimates_resets_invalid_values(self):
        for mode in range(4):
            self.setUp()
            self.assertEqual(self.lib.structured_copy(mode),0)


if __name__ == '__main__':
    unittest.main()
