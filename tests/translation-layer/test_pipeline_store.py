#!/usr/bin/env python3
"""Exercise the real portable cache store against a fake Vulkan driver."""
import ctypes
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class PipelineStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.build.cleanup)
        root = Path(cls.build.name)
        (root / 'driver.c').write_text(r'''
#define _POSIX_C_SOURCE 200809L
#include "husk-tl-pipeline-store.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <pthread.h>
#include <time.h>
#include <unistd.h>
static uint32_t payload[256], next_id, header[8];
static int fail_export, creates, merges, reads, destroys;
static int write_action;
void tl_log_line(const char *fmt, ...) { (void)fmt; }
static int create(void *d, const void *raw, const void *a, uint64_t *out) {
 (void)d;(void)a; const tl_pc_create_info *ci=raw;
 if (ci->type!=17 || ci->next || ci->flags) return -3;
 *out=++next_id; ++creates; payload[*out]=0;
 if (ci->size==36) memcpy(&payload[*out],(const char *)ci->data+32,4);
 return 0;
}
static int data(void *d, uint64_t cache, size_t *size, void *out) {
 (void)d; ++reads;
 if (fail_export) { *size=0; return 5; }
 if (!out) { *size=36; return 0; }
 if (*size<36) return 5;
 memcpy(out,header,32); memcpy((char *)out+32,&payload[cache],4); *size=36; return 0;
}
static int merge(void *d, uint64_t dst, uint32_t n, const uint64_t *src) {
 (void)d; ++merges; for (uint32_t i=0;i<n;i++) payload[dst]+=payload[src[i]]; return 0;
}
static void destroy(void *d, uint64_t c, const void *a) { (void)d;(void)c;(void)a;++destroys; }
void setup(const char *path, int uuid) {
 tl_pc_forget_device((void *)1,NULL,NULL);
 memset(payload,0,sizeof(payload)); next_id=0; fail_export=0;
 creates=merges=reads=destroys=0;
 memset(header,0,sizeof(header));header[0]=32;header[1]=1;header[2]=0x1234;header[3]=0x5678;
 memset((char *)header+16,uuid,16);
 tl_pc_set_api((tl_pc_api){create,data,merge,destroy});
 tl_pc_configure(path); tl_pc_device((void *)1,header[2],header[3],(uint8_t *)header+16);
}
uint64_t add(unsigned value) {
 tl_pc_create_info ci={.type=17}; uint64_t cache=0;
 bool locked=tl_pc_enter();create((void *)1,&ci,NULL,&cache);payload[cache]=value;tl_pc_track((void *)1,cache);tl_pc_leave(locked);return cache;
}
unsigned cache_value(uint64_t cache) { return payload[cache]; }
void mutate(uint64_t cache, unsigned value) {
 bool locked=tl_pc_enter();payload[cache]=value;tl_pc_changed((void *)1,cache);tl_pc_leave(locked);
}
void during_write(int action) { write_action=action; }
ssize_t test_write(int fd, const void *bytes, size_t count) {
 int action=write_action;write_action=0;
 if (action==1) mutate(1,23);
 if (action==2) {
  tl_pc_forget_device((void *)1,NULL,NULL);
  tl_pc_device((void *)1,header[2],header[3],(uint8_t *)header+16);
  add(23);
 }
 return write(fd,bytes,count);
}
void unsupported(void) { fail_export=1; }
void supported(void) { fail_export=0; }
void *load(size_t *size) { return tl_pc_load((void *)1,size); }
void counts(int *out) { out[0]=creates;out[1]=merges;out[2]=reads;out[3]=destroys; }
static pthread_mutex_t test_mu=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t test_cv=PTHREAD_COND_INITIALIZER;
static int readers, release_readers;
static void *reader(void *unused) {
 (void)unused; bool locked=tl_pc_enter();pthread_mutex_lock(&test_mu);++readers;pthread_cond_broadcast(&test_cv);
 while(!release_readers) pthread_cond_wait(&test_cv,&test_mu);
 pthread_mutex_unlock(&test_mu);tl_pc_leave(locked);return NULL;
}
int parallel_readers(void) {
 readers=release_readers=0;pthread_t a,b;pthread_create(&a,NULL,reader,NULL);pthread_create(&b,NULL,reader,NULL);
 struct timespec until;clock_gettime(CLOCK_REALTIME,&until);until.tv_sec+=1;
 pthread_mutex_lock(&test_mu);
 while(readers<2) if(pthread_cond_timedwait(&test_cv,&test_mu,&until)) break;
 int result=readers;release_readers=1;pthread_cond_broadcast(&test_cv);pthread_mutex_unlock(&test_mu);
 pthread_join(a,NULL);pthread_join(b,NULL);return result;
}
''')
        tl=ROOT/'src/translation-layer-next'
        (root/'store.c').write_text('#define _DARWIN_C_SOURCE 1\n#define _POSIX_C_SOURCE 200809L\n#include <unistd.h>\nssize_t test_write(int,const void *,size_t);\n#define write test_write\n#include "husk-tl-pipeline-store.c"\n')
        subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC','-pthread','-I',str(tl),str(root/'driver.c'),str(root/'store.c'),'-o',str(root/'store.so')],check=True)
        cls.lib=ctypes.CDLL(str(root/'store.so'))
        cls.lib.setup.argtypes=[ctypes.c_char_p,ctypes.c_int]
        cls.lib.add.argtypes=[ctypes.c_uint];cls.lib.add.restype=ctypes.c_uint64
        cls.lib.cache_value.argtypes=[ctypes.c_uint64];cls.lib.cache_value.restype=ctypes.c_uint
        cls.lib.mutate.argtypes=[ctypes.c_uint64,ctypes.c_uint]
        cls.lib.load.argtypes=[ctypes.POINTER(ctypes.c_size_t)];cls.lib.load.restype=ctypes.c_void_p
        cls.free=ctypes.CDLL(None).free;cls.free.argtypes=[ctypes.c_void_p]

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'cache'
        self.lib.setup(os.fsencode(self.root),7)

    def blob(self):
        size=ctypes.c_size_t();p=self.lib.load(ctypes.byref(size))
        if not p:
            self.assertEqual(size.value,0);return None
        try:return ctypes.string_at(p,size.value)
        finally:self.free(p)

    def test_pause_snapshot_merges_without_changing_game_caches_and_roundtrips(self):
        a=self.lib.add(11);b=self.lib.add(17)
        self.lib.tl_pc_checkpoint()
        self.assertEqual(self.lib.cache_value(a),11);self.assertEqual(self.lib.cache_value(b),17)
        blob=self.blob();self.assertEqual(len(blob),36);self.assertEqual(struct.unpack('<I',blob[32:])[0],28)
        self.assertEqual(len(list(self.root.glob('*.bin'))),1)
        self.assertFalse(list(self.root.glob('*.tmp-*')))

    def test_wrong_device_uuid_does_not_reuse_data(self):
        self.lib.add(7);self.lib.tl_pc_checkpoint()
        self.lib.setup(os.fsencode(self.root),8)
        self.assertIsNone(self.blob())

    def test_corrupt_truncated_and_oversized_files_are_rejected(self):
        self.lib.add(7);self.lib.tl_pc_checkpoint();path=next(self.root.glob('*.bin'));original=path.read_bytes()
        for blob in (b'',original[:32],b'bad!'+original[4:], original[:33]+bytes([original[33]^1])+original[34:]):
            path.write_bytes(blob);self.assertIsNone(self.blob())
        with path.open('wb') as f:f.truncate(32*1024*1024+9)
        self.assertIsNone(self.blob())

    def test_unsupported_serialization_leaves_existing_file_intact(self):
        cache=self.lib.add(7);self.lib.tl_pc_checkpoint();path=next(self.root.glob('*.bin'));original=path.read_bytes()
        self.lib.mutate(cache,9)
        self.lib.unsupported();self.lib.tl_pc_checkpoint();self.assertEqual(path.read_bytes(),original)
        self.lib.supported();self.lib.tl_pc_checkpoint()
        self.assertEqual(struct.unpack('<I',self.blob()[32:])[0],9)

    def counts(self):
        out=(ctypes.c_int*4)();self.lib.counts(out);return tuple(out)

    def test_unchanged_pause_skips_driver_snapshot_and_file_replacement(self):
        cache=self.lib.add(7);self.lib.tl_pc_checkpoint()
        counts=self.counts();path=next(self.root.glob('*.bin'));stat=path.stat()
        self.lib.tl_pc_checkpoint();self.lib.tl_pc_checkpoint_async()
        self.assertEqual(self.counts(),counts)
        self.assertEqual((path.stat().st_ino,path.stat().st_mtime_ns),(stat.st_ino,stat.st_mtime_ns))
        self.lib.mutate(cache,11);self.lib.tl_pc_checkpoint()
        self.assertGreater(self.counts()[1],counts[1])
        self.assertEqual(struct.unpack('<I',self.blob()[32:])[0],11)

    def test_mutation_during_unlocked_disk_write_remains_dirty(self):
        self.lib.add(7);self.lib.during_write(1);self.lib.tl_pc_checkpoint()
        self.assertEqual(struct.unpack('<I',self.blob()[32:])[0],7)
        self.lib.tl_pc_checkpoint()
        self.assertEqual(struct.unpack('<I',self.blob()[32:])[0],23)

    def test_recycled_device_during_disk_write_is_not_marked_saved(self):
        self.lib.add(7);self.lib.during_write(2);self.lib.tl_pc_checkpoint()
        self.assertEqual(struct.unpack('<I',self.blob()[32:])[0],7)
        self.lib.tl_pc_checkpoint()
        self.assertEqual(struct.unpack('<I',self.blob()[32:])[0],23)

    def test_failed_disk_write_does_not_mark_generation_saved(self):
        self.lib.add(7)
        header=struct.pack('<4I',32,1,0x1234,0x5678)+bytes([7])*16
        path=self.root/(header.hex()+'.bin');path.mkdir()
        self.lib.tl_pc_checkpoint();before=self.counts();path.rmdir()
        self.lib.tl_pc_checkpoint()
        self.assertGreater(self.counts()[1],before[1])
        self.assertEqual(struct.unpack('<I',self.blob()[32:])[0],7)

    def test_untracked_cache_is_not_saved_and_parallel_creators_remain_parallel(self):
        self.assertEqual(self.lib.parallel_readers(),2)
        cache=self.lib.add(7)
        self.lib.tl_pc_untrack.argtypes=[ctypes.c_void_p,ctypes.c_uint64]
        self.lib.tl_pc_untrack(ctypes.c_void_p(1),cache)
        self.lib.tl_pc_checkpoint();self.assertFalse(list(self.root.glob('*.bin')))

if __name__=='__main__':unittest.main()
