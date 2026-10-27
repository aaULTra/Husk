#!/usr/bin/env python3
"""Host archive control, lifetime and actual pinned native compiler component."""
from pathlib import Path
import subprocess,tempfile,unittest,sys,importlib.util
ROOT=Path(__file__).resolve().parents[2];TL=ROOT/'src/translation-layer-next'
class ArchiveHostTests(unittest.TestCase):
 def test_scoped_configuration_singleflight_reservation_and_teardown(self):
  with tempfile.TemporaryDirectory() as d:
   source=(TL/'husk-tl-unity-app.c').read_text();resume='void husk_unity_set_paused(bool paused)'+source.split('void husk_unity_set_paused(bool paused)',1)[1].split('\n}',1)[0]+'\n}'
   touch='void husk_unity_touch(int phase, int id, float x, float y)'+source.split('void husk_unity_touch(int phase, int id, float x, float y)',1)[1].split('\n}',1)[0]+'\n}'
   p=Path(d);(p/'main.c').write_text(r'''
#include "husk-tl-native-archive.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <string.h>
static int configs,forgets;static atomic_bool entered,leave;
void tl_log_line(const char*f,...){(void)f;}
static int configure(const tl_na_config*c){assert(c->version==TL_NATIVE_ARCHIVE_ABI&&c->size==sizeof(*c)&&!strcmp(c->directory,"cache"));configs++;return 1;}
static int snapshot(tl_na_stats*s){s->requested=s->supported=1;s->pending=2;return 1;}
static int prepare(void){atomic_store(&entered,true);while(!atomic_load(&leave)){}return 1;}
static void forget(void){forgets++;}
enum{HUSK_UNITY_RUNNING=1,ENGINE_JAVA,ENGINE_GAMEMAKER,ENGINE_FLUTTER,ENGINE_GODOT,ENGINE_GTA,ENGINE_UE4,ENGINE_SDL,ENGINE_GAMEACTIVITY,ENGINE_COCOS};
static struct{_Atomic int state;int engine;}A={1,ENGINE_UE4};static unsigned pauses,resumes,touches;
#define STUB(name) static void name(bool p){(void)p;}
STUB(tl_javaapp_set_paused) STUB(tl_gm_set_paused) STUB(tl_flutter_set_paused) STUB(tl_godot_set_paused) STUB(tl_gta_set_paused)
STUB(tl_sdl_set_paused) STUB(tl_ga_set_paused) STUB(tl_cocos_set_paused) STUB(tl_unity_set_paused)
static void tl_na_set_paused(bool p){if(p)pauses++;else resumes++;}
static void tl_audio_set_paused(bool p){if(p)pauses++;else resumes++;}
#define TOUCH(name) static void name(int phase,int id,float x,float y){(void)phase;(void)id;(void)x;(void)y;touches++;}
TOUCH(tl_javaapp_touch) TOUCH(tl_gm_touch) TOUCH(tl_flutter_touch) TOUCH(tl_godot_touch) TOUCH(tl_gta_touch)
TOUCH(tl_na_touch) TOUCH(tl_sdl_touch) TOUCH(tl_ga_touch) TOUCH(tl_cocos_touch) TOUCH(tl_unity_touch)
/* ACTUAL_TOUCH */
/* ACTUAL_RESUME */
static void*job(void*p){(void)p;assert(tl_vk_archive_prepare()==1);return 0;}
int main(void){
 tl_npa_set_api((tl_npa_api){configure,snapshot,prepare,forget});husk_unity_touch(0,1,5,6);assert(touches==1);
 husk_ue4_set_native_archive(0);tl_npa_configure("Dungeons","cache",true);assert(!configs&&!tl_vk_archive_begin_prepare());
 husk_ue4_set_native_archive(1);tl_npa_configure("Dungeons","cache",true);assert(!configs);
 husk_ue4_set_native_archive(2);tl_npa_configure("Other","cache",true);tl_npa_configure("Dungeons","cache",false);assert(!configs);
 tl_npa_configure("Dungeons","cache",true);assert(configs==1);tl_npa_device((void*)1);
 assert(tl_vk_archive_begin_prepare()&&tl_vk_archive_preparing()&&!tl_vk_archive_begin_prepare());
 husk_unity_set_paused(false);assert(!resumes);husk_unity_set_paused(true);assert(pauses==2);
 husk_unity_touch(1,1,5,6);assert(touches==2); // input forwarding remains unchanged; no unrelated pause variable/guard
 tl_na_stats s;tl_vk_archive_snapshot(&s);assert(s.preparing&&s.pending==2);
 pthread_t t;assert(!pthread_create(&t,0,job,0));while(!atomic_load(&entered)){}
 assert(tl_vk_archive_prepare()==0);assert(tl_vk_archive_preparing());
 tl_npa_forget((void*)2);assert(!forgets);tl_npa_forget((void*)1);assert(forgets==1&&tl_vk_archive_preparing());
 atomic_store(&leave,true);pthread_join(t,0);assert(!tl_vk_archive_preparing());husk_unity_set_paused(false);assert(resumes==2);
 tl_npa_configure("Dungeons","cache",true);tl_npa_device((void*)3);assert(tl_vk_archive_begin_prepare());
 tl_npa_forget((void*)3);assert(!tl_vk_archive_preparing()&&tl_vk_archive_prepare()==0);return 0;
}
'''.replace('/* ACTUAL_RESUME */',resume).replace('/* ACTUAL_TOUCH */',touch))
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(TL),str(p/'main.c'),str(TL/'husk-tl-native-archive.c'),'-pthread','-o',str(p/'check')],check=True);subprocess.run([str(p/'check')],check=True)
 @unittest.skipUnless(sys.platform=='darwin','Apple Metal SDK required; candidate IPA CI runs native ownership/archive tests')
 def test_actual_native_archive_ownership_persistence_fallback_and_bounds(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'HuskArchiveABI.h').write_bytes((TL/'husk-tl-native-archive.h').read_bytes())
   (p/'main.mm').write_text(r'''
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cassert>
#include <unistd.h>
#include "HuskArchive.inc"
static unsigned preparedCalls=0,compiledCalls=0,attachedCalls=0,descriptorsFreed=0;
static bool failArchive=false,failWrite=false,largeWrite=false,forgetDuringPrepare=false;
@interface Descriptor:NSObject<NSCopying>
@property(retain) NSArray *binaryArchives;
@end
@implementation Descriptor
-(id)copyWithZone:(NSZone*)zone{(void)zone;Descriptor*d=[Descriptor new];d.binaryArchives=self.binaryArchives;return d;}
-(void)dealloc{++descriptorsFreed;[_binaryArchives release];[super dealloc];}
@end
@interface Archive:NSObject
-(BOOL)addRenderPipelineFunctionsWithDescriptor:(id)d error:(NSError**)e;
-(BOOL)addComputePipelineFunctionsWithDescriptor:(id)d error:(NSError**)e;
-(BOOL)serializeToURL:(NSURL*)url error:(NSError**)error;
@end
@implementation Archive
-(BOOL)addRenderPipelineFunctionsWithDescriptor:(id)d error:(NSError**)e{(void)e;assert(d&&![[d binaryArchives] count]);preparedCalls++;if(forgetDuringPrepare){forgetDuringPrepare=false;vkHuskArchiveForget();}return YES;}
-(BOOL)addComputePipelineFunctionsWithDescriptor:(id)d error:(NSError**)e{return[self addRenderPipelineFunctionsWithDescriptor:d error:e];}
-(BOOL)serializeToURL:(NSURL*)url error:(NSError**)e{if(failWrite)return NO;if(largeWrite){int fd=open(url.fileSystemRepresentation,O_CREAT|O_RDWR,0600);assert(fd>=0);ftruncate(fd,(off_t)huskArchiveMaxBytes+1);close(fd);return YES;}return [@"validarchive" writeToURL:url atomically:NO encoding:NSUTF8StringEncoding error:e];}
@end
@interface Device:NSObject
@property unsigned long long registryID;
@property BOOL defer;
@property(copy) NSString *name;
-(id)newBinaryArchiveWithDescriptor:(MTLBinaryArchiveDescriptor*)d error:(NSError**)e;
-(void)newRenderPipelineStateWithDescriptor:(id)d completionHandler:(void(^)(id,NSError*))h;
-(void)newRenderPipelineStateWithDescriptor:(id)d options:(MTLPipelineOption)o completionHandler:(void(^)(id,id,NSError*))h;
-(void)newComputePipelineStateWithDescriptor:(id)d options:(MTLPipelineOption)o completionHandler:(void(^)(id,id,NSError*))h;
@end
@implementation Device
-(id)newBinaryArchiveWithDescriptor:(MTLBinaryArchiveDescriptor*)d error:(NSError**)e{(void)e;if(d.url&&![[NSString stringWithContentsOfURL:d.url encoding:NSUTF8StringEncoding error:NULL]isEqual:@"validarchive"])return nil;return [Archive new];}
-(void)newRenderPipelineStateWithDescriptor:(id)d completionHandler:(void(^)(id,NSError*))h{
 if(self.defer){self.defer=NO;id keep=[d retain];void(^copy)(id,NSError*)=[h copy];dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY,0),^{@autoreleasepool{[self newRenderPipelineStateWithDescriptor:keep completionHandler:copy];[keep release];[copy release];}});return;}
 compiledCalls++;bool attached=[[d binaryArchives]count]>0;if(attached)attachedCalls++;usleep(18000);if(attached&&failArchive){failArchive=false;h(nil,[NSError errorWithDomain:@"archive" code:9 userInfo:nil]);}else{h((id)@"state",nil);}}
-(void)newRenderPipelineStateWithDescriptor:(id)d options:(MTLPipelineOption)o completionHandler:(void(^)(id,id,NSError*))h{assert(o==MTLPipelineOptionFailOnBinaryArchiveMiss);[self newRenderPipelineStateWithDescriptor:d completionHandler:^(id s,NSError*e){h(s,nil,e);}];}
-(void)newComputePipelineStateWithDescriptor:(id)d options:(MTLPipelineOption)o completionHandler:(void(^)(id,id,NSError*))h{assert((o&~MTLPipelineOptionFailOnBinaryArchiveMiss)==MTLPipelineOptionBufferTypeInfo);[self newRenderPipelineStateWithDescriptor:d completionHandler:^(id s,NSError*e){h(s,(id)@"reflection",e);}];}
-(void)dealloc{[_name release];[super dealloc];}
@end
int main(int argc,char**argv){assert(argc==2);@autoreleasepool{
 Device*device=[Device new];device.name=@"test";device.registryID=42;
 tl_na_config c={TL_NATIVE_ARCHIVE_ABI,sizeof(c),2,0,argv[1]};assert(!vkHuskArchiveConfigure(&c));c.enabled=0;assert(vkHuskArchiveConfigure(&c));
 Descriptor*d=[Descriptor new];unsigned completions=0;__block unsigned complete=0;
 huskArchiveNewRender((id<MTLDevice>)device,(MTLRenderPipelineDescriptor*)d,^(id s,NSError*e){assert(s&&!e);complete++;});assert(complete==1&&huskArchivePending.empty());
 c.enabled=1;assert(vkHuskArchiveConfigure(&c));
 huskArchiveNewRender((id<MTLDevice>)device,(MTLRenderPipelineDescriptor*)d,^(id s,NSError*e){assert(s&&!e);complete++;});
 tl_na_stats stats={TL_NATIVE_ARCHIVE_ABI,sizeof(stats)};assert(vkHuskArchiveSnapshot(&stats)&&stats.supported&&stats.pending==1&&!stats.restored_bytes);
 [d release];assert(huskArchivePending.size()==1);assert(vkHuskArchivePrepare()==1&&preparedCalls==1);
 assert(vkHuskArchiveSnapshot(&stats)&&stats.saved_bytes&&stats.prepared==1&&!stats.pending);
 d=[Descriptor new];huskArchiveVerify.store(true);huskArchiveStats.verification_requested=1;failArchive=true;completions=complete;
 huskArchiveNewRender((id<MTLDevice>)device,(MTLRenderPipelineDescriptor*)d,^(id s,NSError*e){assert(s&&!e);complete++;});
 assert(complete==completions+1&&attachedCalls==1&&stats.archive_fallbacks==0);assert(vkHuskArchiveSnapshot(&stats)&&stats.archive_fallbacks==1);
 assert(vkHuskArchiveSnapshot(&stats)&&stats.verification_attempts==1&&stats.verification_failures==1&&!stats.archive_requirement_satisfied&&stats.last_verification_error_code==9);
 assert(!d.binaryArchives); // caller's descriptor is immutable
 huskArchiveNewCompute((id<MTLDevice>)device,(MTLComputePipelineDescriptor*)d,MTLPipelineOptionBufferTypeInfo,^(id s,id r,NSError*e){assert(s&&r&&!e);complete++;});
 assert(vkHuskArchiveSnapshot(&stats)&&stats.verification_attempts==2&&stats.archive_requirement_satisfied==1);
 for(unsigned i=0;i<12;i++)huskArchiveCapture((id<MTLDevice>)device,d,false,20000000,true,huskArchiveGeneration);
 assert(vkHuskArchiveSnapshot(&stats)&&stats.pending==8&&stats.descriptors_dropped>0);
 tl_na_priority priority={1,sizeof(priority)};assert(vkHuskArchivePriority(&priority)&&priority.requirement_satisfied_skips==1);
 huskArchiveCapture((id<MTLDevice>)device,d,false,500000000,true,huskArchiveGeneration);
 assert(vkHuskArchivePriority(&priority)&&priority.replaced==1&&priority.highest_pending_ns==500000000&&priority.pending==8);
 assert(huskArchivePending.front()->elapsed_ns==500000000);
 for(size_t i=1;i<huskArchivePending.size();i++)assert(huskArchivePending[i-1]->elapsed_ns>=huskArchivePending[i]->elapsed_ns);
 priority.version=2;assert(!vkHuskArchivePriority(&priority));
 NSString *path=[huskArchivePath copy];NSString *directory=[path stringByDeletingLastPathComponent];
 for(unsigned i=0;i<6;i++){NSString *old=[directory stringByAppendingPathComponent:[NSString stringWithFormat:@"native-%016llx.metalarc",(unsigned long long)i]];assert([@"old" writeToFile:old atomically:YES encoding:NSUTF8StringEncoding error:NULL]);}
 NSString *unrelated=[directory stringByAppendingPathComponent:@"notes.keep"];assert([@"keep" writeToFile:unrelated atomically:YES encoding:NSUTF8StringEncoding error:NULL]);
 huskArchivePrune(directory,path);assert([[NSFileManager defaultManager]fileExistsAtPath:unrelated]);assert(vkHuskArchiveSnapshot(&stats)&&stats.evicted_files>=3);
 NSData*before=[NSData dataWithContentsOfFile:path];
 failWrite=true;assert(vkHuskArchivePrepare()==-1);assert([[NSData dataWithContentsOfFile:path]isEqual:before]);failWrite=false;
 huskArchiveCapture((id<MTLDevice>)device,d,false,20000000,true,huskArchiveGeneration);largeWrite=true;assert(vkHuskArchivePrepare()==-1);largeWrite=false;assert([[NSData dataWithContentsOfFile:path]isEqual:before]);
 huskArchiveCapture((id<MTLDevice>)device,d,false,20000000,true,huskArchiveGeneration);unsigned long long oldWriteFailures=huskArchiveStats.write_failures;
 forgetDuringPrepare=true;assert(vkHuskArchivePrepare()==1);assert(!huskArchiveRead&&!huskArchiveDevice&&!huskArchiveEnabled.load());
 assert(vkHuskArchiveSnapshot(&stats)&&stats.saved_bytes&&stats.write_failures==oldWriteFailures); // teardown is not a failed disk write
 assert(vkHuskArchiveConfigure(&c));
 huskArchiveNewRender((id<MTLDevice>)device,(MTLRenderPipelineDescriptor*)d,^(id s,NSError*e){assert(s&&!e);complete++;});assert(vkHuskArchiveSnapshot(&stats)&&stats.restored_bytes);
 Descriptor*asyncDescriptor=[Descriptor new];device.defer=YES;dispatch_semaphore_t done=dispatch_semaphore_create(0);
 huskArchiveNewRender((id<MTLDevice>)device,(MTLRenderPipelineDescriptor*)asyncDescriptor,^(id s,NSError*e){assert(s&&!e);dispatch_semaphore_signal(done);});[asyncDescriptor release];
 assert(dispatch_semaphore_wait(done,dispatch_time(DISPATCH_TIME_NOW,5*NSEC_PER_SEC))==0);
 vkHuskArchiveForget();assert([@"badarchive" writeToFile:path atomically:YES encoding:NSUTF8StringEncoding error:NULL]);assert(vkHuskArchiveConfigure(&c));
 huskArchiveNewRender((id<MTLDevice>)device,(MTLRenderPipelineDescriptor*)d,^(id s,NSError*e){assert(s&&!e);complete++;});assert(vkHuskArchiveSnapshot(&stats)&&stats.read_failures&&!stats.restored_bytes);
 vkHuskArchiveForget();[d release];[device release];[path release];c.enabled=0;assert(vkHuskArchiveConfigure(&c));assert(descriptorsFreed>8);return 0;
}}
''')
   exe=p/'check';subprocess.run(['clang++','-std=c++17','-fno-objc-arc','-fblocks','-I',str(p),'-I',str(ROOT/'patches/metalfx'),str(p/'main.mm'),'-framework','Foundation','-framework','Metal','-o',str(exe)],check=True);subprocess.run([str(exe),str(p/'cache')],check=True)
if __name__=='__main__':unittest.main()
