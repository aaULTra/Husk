#!/usr/bin/env python3
"""Compile actual queue adapter on Apple; fake queues verify host isolation/chaining."""
import shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
@unittest.skipUnless(sys.platform=='darwin' and shutil.which('clang'),'Apple ObjC/Metal SDK required; IPA CI runs adapter check')
class MetalAdapterTests(unittest.TestCase):
 def test_registered_queue_scope_factory_chaining_and_device_teardown(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'main.m').write_text(r'''
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <QuartzCore/QuartzCore.h>
#include "husk-tl-gpu-timing.h"
#include <assert.h>
@interface TestBuffer:NSObject
@property(copy) void (^handler)(id);
@property double GPUStartTime;
@property double GPUEndTime;
@property MTLCommandBufferStatus status;
-(void)addCompletedHandler:(void (^)(id))handler;
@end
@implementation TestBuffer
-(void)addCompletedHandler:(void (^)(id))handler{self.handler=handler;}
@end
@interface TestQueue:NSObject
@property unsigned calls;
-(id)commandBufferWithDescriptor:(id)descriptor;
@end
@implementation TestQueue
-(id)commandBufferWithDescriptor:(id)descriptor{assert(descriptor);self.calls++;return [TestBuffer new];}
@end
int main(){@autoreleasepool{
 TestQueue *game=[TestQueue new],*host=[TestQueue new];
 tl_gput_native_register((void *)1,(__bridge void *)game);
 tl_gput_native_start(false);tl_gput_exclude(false);
 TestBuffer *off=[game commandBufferWithDescriptor:@1];assert(!off.handler);
 tl_gput_native_start(true);tl_gput_exclude(false);
 TestBuffer *a=[game commandBufferWithDescriptor:@2];TestBuffer *b=[host commandBufferWithDescriptor:@3];
 assert(a.handler&&!b.handler&&game.calls==2&&host.calls==1);
 a.GPUStartTime=CACurrentMediaTime();a.GPUEndTime=a.GPUStartTime+0.001;a.status=MTLCommandBufferStatusCompleted;a.handler(a);
 tl_gput_stats s;tl_gput_snapshot(&s);assert(s.completed==1&&s.registered_queues==1&&s.hooked_queues==1);
 tl_gput_native_forget((void *)1);TestBuffer *removed=[game commandBufferWithDescriptor:@4];assert(!removed.handler);
 tl_gput_snapshot(&s);assert(s.registered_queues==0);
 tl_gput_end();return 0;
}}
''')
   binary=p/'check';tl=ROOT/'src/translation-layer-next'
   subprocess.run(['clang','-fobjc-arc','-fblocks','-Wall','-Wextra','-Werror','-I',str(tl),str(p/'main.m'),str(tl/'husk-tl-gpu-timing-metal.m'),str(tl/'husk-tl-gpu-timing.c'),'-framework','Foundation','-framework','Metal','-framework','QuartzCore','-o',str(binary)],check=True)
   subprocess.run([str(binary)],check=True)
if __name__=='__main__':unittest.main()
