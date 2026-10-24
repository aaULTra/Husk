#!/usr/bin/env python3
"""Compile actual Vulkan wrappers with a fake host: forwarding and no double cap."""
import ctypes
import os
import struct
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class VulkanTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        source = (ROOT / "src/translation-layer-next/husk-tl-vulkan.m").read_text()
        counters = source[source.index("static int64_t monotonic_ns(void);"):source.index("static int w_vkCreateSwapchainKHR(")]
        acquire = source[source.index("typedef int (*pfn_acquire)"):source.index("static int64_t monotonic_ns(void)\n{")]
        pacing = source[source.index("static int compare_frame_ms("):source.index("/* ------------------------------------------------------------ Direct3D 11")]
        harness = r"""
#define _POSIX_C_SOURCE 200809L
#include <stdbool.h>
#include <stdint.h>
#include <stdatomic.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
#include <time.h>
#include "husk-tl-ue4-graphics.h"
#include "husk-tl-pipeline-store.h"
#undef TARGET_OS_IOS
#undef TARGET_OS_OSX
#define TARGET_OS_IOS 0
#define TARGET_OS_OSX 0
#define VK_SUCCESS 0
static struct { void *lib; atomic_ulong frames; bool probe_frames; } V = {.lib=(void *)1};
static void *g_swapchain_layer;
static int64_t fake_clock;
static unsigned sleep_calls, acquire_calls, submit_calls, present_calls;
static int native_status, forwarding_failures;
static int reject_seed, seed_attempts;
static unsigned cache_create_calls, cache_data_calls, graphics_calls, compute_calls;
static int64_t monotonic_ns(void) { fake_clock += 1000000; return fake_clock; }
static int test_nanosleep(const struct timespec *delay, struct timespec *remaining) {
    (void)remaining; ++sleep_calls;
    fake_clock += delay->tv_sec * 1000000000LL + delay->tv_nsec;
    return 0;
}
#define nanosleep test_nanosleep
static double CACurrentMediaTime(void) { return 1; }
void tl_log_line(const char *fmt, ...) { (void)fmt; }
static void probe_frame(void *q, const void *i, unsigned long n) { (void)q; (void)i; (void)n; }
static void log_layer_state(void *l, const char *s) { (void)l; (void)s; }
static int host_acquire(void *d, uint64_t s, uint64_t t, uint64_t sem, uint64_t fence, uint32_t *index) {
    ++acquire_calls;
    if (d!=(void *)7 || s!=11 || t!=13 || sem!=17 || fence!=19) ++forwarding_failures;
    *index=2; return native_status;
}
static int host_submit(void *q, uint32_t n, const void *s, uint64_t f) {
    ++submit_calls;
    if (q!=(void *)7 || n!=3 || s!=(void *)23 || f!=29) ++forwarding_failures;
    return native_status;
}
static int host_present(void *q, const void *i) {
    ++present_calls;
    if (q!=(void *)7 || !i) ++forwarding_failures;
    return native_status;
}
static int host_cache_create(void *device, const void *ci, const void *alloc, uint64_t *out) {
    ++cache_create_calls;
    const tl_pc_create_info *info=ci;
    if (info && info->size && info->data) { ++seed_attempts; if (reject_seed) return -3; }
    if (device!=(void *)7 || !ci || alloc!=(void *)31) ++forwarding_failures;
    *out=37; return native_status;
}
static int host_cache_data(void *device, uint64_t cache, size_t *size, void *data) {
    ++cache_data_calls;
    if (device!=(void *)7 || cache!=37 || !size) ++forwarding_failures;
    if (data) memset(data, 0xab, *size);
    *size=64; return native_status;
}
static int host_graphics(void *device, uint64_t cache, uint32_t count, const void *ci, const void *alloc, uint64_t *out) {
    ++graphics_calls;
    if (device!=(void *)7 || (cache!=37 && cache!=0) || count!=2 || ci!=(void *)41 || alloc!=(void *)31) ++forwarding_failures;
    out[0]=43; out[1]=47; return native_status;
}
static int host_compute(void *device, uint64_t cache, uint32_t count, const void *ci, const void *alloc, uint64_t *out) {
    ++compute_calls;
    if (device!=(void *)7 || cache!=37 || count!=1 || ci!=(void *)41 || alloc!=(void *)31) ++forwarding_failures;
    *out=53; return native_status;
}
static int host_merge(void *d, uint64_t c, uint32_t n, const uint64_t *s) { (void)d;(void)c;(void)n;(void)s;return native_status; }
static void host_destroy_cache(void *d, uint64_t c, const void *a) { (void)d;(void)c;(void)a; }
static void host_destroy_device(void *d, const void *a) { (void)d;(void)a; }
static void *fake_dlsym(void *lib, const char *name) {
    (void)lib;
    if (!strcmp(name,"vkAcquireNextImageKHR")) return (void *)host_acquire;
    if (!strcmp(name,"vkQueueSubmit")) return (void *)host_submit;
    if (!strcmp(name,"vkQueuePresentKHR")) return (void *)host_present;
    if (!strcmp(name,"vkCreatePipelineCache")) return (void *)host_cache_create;
    if (!strcmp(name,"vkGetPipelineCacheData")) return (void *)host_cache_data;
    if (!strcmp(name,"vkCreateGraphicsPipelines")) return (void *)host_graphics;
    if (!strcmp(name,"vkCreateComputePipelines")) return (void *)host_compute;
    if (!strcmp(name,"vkMergePipelineCaches")) return (void *)host_merge;
    if (!strcmp(name,"vkDestroyPipelineCache")) return (void *)host_destroy_cache;
    if (!strcmp(name,"vkDestroyDevice")) return (void *)host_destroy_device;
    return NULL;
}
#define dlsym fake_dlsym
"""
        harness += counters + acquire + pacing + r"""
void configure_store(const char *path) {
    tl_pc_set_api((tl_pc_api){host_cache_create,host_cache_data,host_merge,host_destroy_cache});
    tl_pc_configure(path);
    uint8_t uuid[16];memset(uuid,3,sizeof(uuid));tl_pc_device((void *)7,1,2,uuid);
}
int exercise_seed(int reject, int status) {
    reject_seed=reject;seed_attempts=cache_create_calls=0;native_status=status;
    tl_pc_create_info ci={.type=17};uint64_t cache=0;
    int result=w_vkCreatePipelineCache((void *)7,&ci,(void *)31,&cache);
    reject_seed=0;
    if (ci.size || ci.data || result!=status || seed_attempts!=1) return -1;
    return cache_create_calls;
}
int exercise_cache(int status) {
    husk_ue4_set_sharp_graphics(true);
    native_status=status; forwarding_failures=0;
    cache_create_calls=cache_data_calls=graphics_calls=compute_calls=0;
    uint8_t ci[40]={0}, original[40], bytes[64];
    size_t seed=64, size=64;
    memcpy(ci+24, &seed, sizeof(seed)); memcpy(original,ci,sizeof(ci));
    uint64_t cache=0, out[2]={0};
    if (w_vkCreatePipelineCache((void *)7,ci,(void *)31,&cache)!=status || cache!=37) return 1;
    if (memcmp(ci,original,sizeof(ci))) return 2;
    if (w_vkGetPipelineCacheData((void *)7,37,&size,NULL)!=status || size!=64) return 3;
    if (w_vkGetPipelineCacheData((void *)7,37,&size,bytes)!=status || bytes[0]!=0xab) return 4;
    if (w_vkCreateGraphicsPipelines((void *)7,37,2,(void *)41,(void *)31,out)!=status || out[1]!=47) return 5;
    if (w_vkCreateGraphicsPipelines((void *)7,0,2,(void *)41,(void *)31,out)!=status) return 6;
    if (w_vkCreateComputePipelines((void *)7,37,1,(void *)41,(void *)31,out)!=status || out[0]!=53) return 7;
    if (cache_create_calls!=1 || cache_data_calls!=2 || graphics_calls!=2 || compute_calls!=1 || forwarding_failures) return 8;
    if (w_vkMergePipelineCaches((void *)7,37,1,&cache)!=status) return 9;
    w_vkDestroyPipelineCache((void *)7,37,(void *)31);
    w_vkDestroyDevice((void *)7,(void *)31);
    return 0;
}
int exercise(int enabled, int efficient, int fps, int status) {
    husk_ue4_set_sharp_graphics(enabled);
    husk_ue4_set_efficiency(efficient, fps);
    native_status=status; sleep_calls=acquire_calls=submit_calls=present_calls=0;
    forwarding_failures=0; fake_clock += 10000000000LL;
    uint8_t info[64]={0};
    for (unsigned i=0;i<700;++i) {
        fake_clock += 40000000; /* Already slower than either working cap. */
        uint32_t index=0;
        if (w_vkAcquireNextImageKHR((void *)7,11,13,17,19,&index)!=status || index!=2) return 1;
        if (w_vkQueueSubmit((void *)7,3,(void *)23,29)!=status) return 2;
        if (w_vkQueuePresentKHR((void *)7,info)!=status) return 3;
    }
    if (acquire_calls!=700 || submit_calls!=700 || present_calls!=700 || forwarding_failures) return 4;
    if (sleep_calls) return 5;
    return 0;
}
"""
        root = Path(cls.tmp.name)
        (root / "timing.c").write_text(harness)
        tl = ROOT / "src/translation-layer-next"
        subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
                        "-I", str(tl), str(root / "timing.c"), str(tl / "husk-tl-ue4-graphics.c"), str(tl / "husk-tl-pipeline-store.c"), "-pthread",
                        "-o", str(root / "timing.so")], check=True)
        cls.lib = ctypes.CDLL(str(root / "timing.so"))
        cls.lib.exercise.argtypes = [ctypes.c_int] * 4

    def test_original_sharp_passes_through_without_added_host_sleeps(self):
        self.assertEqual(self.lib.exercise(1, 0, 60, 0), 0)

    def test_existing_limiter_does_not_add_wait_when_frames_already_exceed_budget(self):
        for fps in (30, 60):
            self.assertEqual(self.lib.exercise(1, 1, fps, 0), 0)

    def test_cache_and_pipeline_observation_preserves_inputs_results_and_outputs(self):
        for status in (0, 5, -4):
            self.assertEqual(self.lib.exercise_cache(status), 0)

    def test_host_seed_fallback_is_limited_to_initialization_failure(self):
        self.lib.configure_store.argtypes=[ctypes.c_char_p]
        for reject, status, calls in ((0,0,1),(1,0,2),(0,-4,1),(0,-1,1)):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'cache'
                self.lib.configure_store(os.fsencode(root))
                header=struct.pack('<4I',32,1,1,2)+bytes([3])*16
                payload=header+b'cached shader data'
                hash_value=14695981039346656037
                for value in payload: hash_value=((hash_value^value)*1099511628211)&((1<<64)-1)
                path=root/(header.hex()+'.bin')
                path.write_bytes(payload+struct.pack('<Q',hash_value))
                self.assertEqual(self.lib.exercise_seed(reject,status),calls)
                self.assertEqual(path.exists(),not reject)

    def test_status_codes_and_arguments_are_forwarded_without_retry_or_gpu_wait(self):
        for status in (-4, 1000001003):
            self.assertEqual(self.lib.exercise(1, 1, 60, status), 0)
        self.assertEqual(self.lib.exercise(0, 0, 60, 0), 0)


if __name__ == "__main__":
    unittest.main()
