/* SPDX-License-Identifier: GPL-2.0-or-later */
// Included only in the exact pinned MVKPipeline.mm. MRC, full native descriptors.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include "HuskArchiveABI.h"
#include <mutex>
#include <atomic>
#include <vector>
#include <chrono>
#include <sys/file.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstdio>
#include <cstring>
#include <new>
#ifndef HUSK_ARCHIVE_PATCH_ID
#define HUSK_ARCHIVE_PATCH_ID "unidentified-patch"
#endif
static std::mutex huskArchiveLock;
static tl_na_stats huskArchiveStats={1,sizeof(tl_na_stats)};
static NSString *huskArchiveDirectory=nil,*huskArchivePath=nil;
static id<MTLDevice> huskArchiveDevice=nil;
static id<MTLBinaryArchive> huskArchiveRead=nil;
static bool huskArchiveConfigured=false;
static std::atomic<bool> huskArchiveEnabled{false};
static uint64_t huskArchiveGeneration=0;
struct HuskArchiveCandidate {
 id descriptor=nil;bool compute=false;
 HuskArchiveCandidate(id d,bool c):descriptor([d retain]),compute(c){}
 ~HuskArchiveCandidate(){[descriptor release];}
};
static std::vector<HuskArchiveCandidate*> huskArchivePending;
static uint64_t huskArchiveNow(){return (uint64_t)std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
static uint64_t huskArchiveHash(NSString *value){
 uint64_t h=14695981039346656037ULL;const unsigned char *s=(const unsigned char*)value.UTF8String;
 for(;s&&*s;s++){h^=*s;h*=1099511628211ULL;}return h;
}
static uint64_t huskArchiveFileSize(NSString *path){struct stat s={};return path&&stat(path.fileSystemRepresentation,&s)==0&&s.st_size>0?(uint64_t)s.st_size:0;}
static constexpr uint64_t huskArchiveMaxBytes=64ULL*1024*1024;
static bool huskArchiveName(NSString *name){
 if(name.length!=32||![name hasPrefix:@"native-"]||![name hasSuffix:@".metalarc"])return false;
 NSCharacterSet *bad=[[NSCharacterSet characterSetWithCharactersInString:@"0123456789abcdef"] invertedSet];
 return [[name substringWithRange:NSMakeRange(7,16)]rangeOfCharacterFromSet:bad].location==NSNotFound;
}
// Called only under the directory writer lock, outside rendering. Keep at most
// four owned archives/128MiB; never remove unrelated data or the current file.
static void huskArchivePrune(NSString *directory,NSString *current){
 NSMutableArray *files=[NSMutableArray array];uint64_t bytes=0;
 NSFileManager *fm=[NSFileManager defaultManager];
 for(NSString *name in [fm contentsOfDirectoryAtPath:directory error:NULL]){
  NSString *path=[directory stringByAppendingPathComponent:name];
  if([name hasSuffix:@".next"]&&huskArchiveName([name substringToIndex:name.length-5])){[fm removeItemAtPath:path error:NULL];continue;}
  if(!huskArchiveName(name))continue;
  uint64_t size=huskArchiveFileSize(path);bytes+=size;
  NSDictionary *attrs=[fm attributesOfItemAtPath:path error:NULL];
  [files addObject:@{@"path":path,@"size":@(size),@"date":attrs[NSFileModificationDate]?:[NSDate distantPast]}];
 }
 [files sortUsingComparator:^NSComparisonResult(NSDictionary *a,NSDictionary *b){return [a[@"date"] compare:b[@"date"]];}];
 uint64_t removed=0,freed=0;NSUInteger count=files.count;
 for(NSDictionary *entry in files){
  if(count<=4&&bytes<=128ULL*1024*1024)break;
  NSString *path=entry[@"path"];if([path isEqual:current])continue;
  if([fm removeItemAtPath:path error:NULL]){uint64_t size=[entry[@"size"]unsignedLongLongValue];bytes-=size;freed+=size;removed++;count--;}
 }
 if(removed){std::lock_guard<std::mutex> guard(huskArchiveLock);huskArchiveStats.evicted_files+=removed;huskArchiveStats.evicted_bytes+=freed;}
}
static id<MTLBinaryArchive> huskArchiveOpen(id<MTLDevice> device,NSString *path){
 MTLBinaryArchiveDescriptor *d=[MTLBinaryArchiveDescriptor new];
 if(path)d.url=[NSURL fileURLWithPath:path];
 NSError *error=nil;id<MTLBinaryArchive> archive=[device newBinaryArchiveWithDescriptor:d error:&error];
 [d release];return archive; // retained; error is reported through bounded counters
}
// Called under lock. A different device is declined, never mixed into its archive.
static bool huskArchiveBind(id<MTLDevice> device){
 if(!huskArchiveConfigured||!device)return false;
 if(huskArchiveDevice)return huskArchiveDevice==device&&huskArchiveStats.supported;
 if(![device respondsToSelector:@selector(newBinaryArchiveWithDescriptor:error:)]){huskArchiveEnabled.store(false);return false;}
 huskArchiveDevice=[device retain];
 NSString *identity=[NSString stringWithFormat:@"v1|%s|%@|%llu|%@",HUSK_ARCHIVE_PATCH_ID,device.name,(unsigned long long)device.registryID,NSProcessInfo.processInfo.operatingSystemVersionString];
 huskArchivePath=[[huskArchiveDirectory stringByAppendingPathComponent:[NSString stringWithFormat:@"native-%016llx.metalarc",(unsigned long long)huskArchiveHash(identity)]] copy];
 uint64_t bytes=huskArchiveFileSize(huskArchivePath);
 if(bytes&&bytes<=huskArchiveMaxBytes){
  huskArchiveRead=huskArchiveOpen(device,huskArchivePath);
  if(huskArchiveRead)huskArchiveStats.restored_bytes=bytes;else huskArchiveStats.read_failures++;
 }else if(bytes)huskArchiveStats.read_failures++;
 // Probe archive creation once without compiling or writing any pipeline.
 id<MTLBinaryArchive> probe=huskArchiveRead?[huskArchiveRead retain]:huskArchiveOpen(device,nil);
 huskArchiveStats.supported=probe!=nil;[probe release];if(!huskArchiveStats.supported)huskArchiveEnabled.store(false);return huskArchiveStats.supported;
}
extern "C" __attribute__((visibility("default"))) int vkHuskArchiveConfigure(const tl_na_config *c){
 if(!c||c->version!=1||c->size!=sizeof(*c)||c->reserved||c->enabled>1)return 0;
 std::lock_guard<std::mutex> guard(huskArchiveLock);
 if(huskArchiveDevice||huskArchiveStats.preparing)return 0; // launch-only configuration
 if(c->enabled&&(!c->directory||!c->directory[0]||strlen(c->directory)>900))return 0;
 huskArchiveStats=(tl_na_stats){1,sizeof(tl_na_stats)};huskArchiveGeneration++;
 [huskArchiveDirectory release];huskArchiveDirectory=c->enabled?[[NSString stringWithUTF8String:c->directory] copy]:nil;
 huskArchiveConfigured=c->enabled&&huskArchiveDirectory;
 huskArchiveStats.requested=c->enabled;huskArchiveEnabled.store(huskArchiveConfigured);return !c->enabled||huskArchiveConfigured;
}
// The descriptor copy is owned until the async Metal compiler has accepted it.
static id huskArchiveDescriptor(id<MTLDevice> device,id descriptor){
 if(!descriptor)return nil;
 std::lock_guard<std::mutex> guard(huskArchiveLock);
 if(!huskArchiveBind(device)||!huskArchiveRead)return [descriptor retain];
 id copy=[descriptor copy];
 if(copy){[copy setBinaryArchives:@[huskArchiveRead]];huskArchiveStats.archive_attachments++;}
 return copy?:[descriptor retain];
}
static void huskArchiveCapture(id<MTLDevice> device,id descriptor,bool compute,uint64_t elapsed,bool success){
 if(!success||elapsed<16666667ULL||!descriptor)return;
 std::lock_guard<std::mutex> guard(huskArchiveLock);
 if(!huskArchiveBind(device))return;
 if(huskArchiveStats.preparing||huskArchivePending.size()>=8){huskArchiveStats.descriptors_dropped++;return;}
 // Native descriptor copies retain Metal functions/resources, not guest handles.
 id copy=[descriptor copy];if(!copy){huskArchiveStats.descriptors_dropped++;return;}
 [copy setBinaryArchives:@[]];
 auto *candidate=new(std::nothrow) HuskArchiveCandidate(copy,compute);[copy release];
 if(!candidate||!candidate->descriptor){delete candidate;huskArchiveStats.descriptors_dropped++;return;}
 huskArchivePending.push_back(candidate);huskArchiveStats.descriptors_captured++;
}
extern "C" __attribute__((visibility("default"))) int vkHuskArchiveSnapshot(tl_na_stats *out){
 if(!out||out->version!=1||out->size!=sizeof(*out))return 0;
 std::lock_guard<std::mutex> guard(huskArchiveLock);*out=huskArchiveStats;out->pending=(uint32_t)huskArchivePending.size();return 1;
}
extern "C" __attribute__((visibility("default"))) int vkHuskArchivePrepare(void){
 std::vector<HuskArchiveCandidate*> pending;id<MTLDevice> device=nil;NSString *path=nil;uint64_t generation=0;
 {
  std::lock_guard<std::mutex> guard(huskArchiveLock);
  if(!huskArchiveStats.supported||huskArchiveStats.preparing||huskArchivePending.empty())return 0;
  huskArchiveStats.preparing=1;huskArchiveStats.prepare_calls++;
  device=[huskArchiveDevice retain];path=[huskArchivePath copy];generation=huskArchiveGeneration;pending.swap(huskArchivePending);
 }
 uint64_t started=huskArchiveNow(),prepared=0,failures=0,saved=0;bool wrote=false;
 @autoreleasepool {
  NSString *directory=[path stringByDeletingLastPathComponent];
  NSError *error=nil;[[NSFileManager defaultManager] createDirectoryAtPath:directory withIntermediateDirectories:YES attributes:nil error:&error];
  NSString *lockPath=[directory stringByAppendingPathComponent:@".archive-writer.lock"],*next=[path stringByAppendingString:@".next"];
  int fd=open(lockPath.fileSystemRepresentation,O_CREAT|O_RDWR,0600);
  bool writer=fd>=0&&flock(fd,LOCK_EX|LOCK_NB)==0;
  id<MTLBinaryArchive> archive=nil;
  if(writer){
   uint64_t bytes=huskArchiveFileSize(path);
   if(bytes&&bytes<=huskArchiveMaxBytes)archive=huskArchiveOpen(device,path);
   if(!archive)archive=huskArchiveOpen(device,nil);
  }
  if(archive){
   // At most8 items and2seconds between starts. One Metal API call cannot be
   // preempted; host keeps the guest paused through its completion.
   for(auto *candidate:pending){
    if(huskArchiveNow()-started>2000000000ULL)break;
    {std::lock_guard<std::mutex> guard(huskArchiveLock);if(generation!=huskArchiveGeneration)break;}
    error=nil;BOOL ok=candidate->compute?[archive addComputePipelineFunctionsWithDescriptor:(MTLComputePipelineDescriptor*)candidate->descriptor error:&error]:[archive addRenderPipelineFunctionsWithDescriptor:(MTLRenderPipelineDescriptor*)candidate->descriptor error:&error];
    if(ok)prepared++;else failures++;
   }
   error=nil;
   if(prepared&&[archive serializeToURL:[NSURL fileURLWithPath:next] error:&error]){
    saved=huskArchiveFileSize(next);
    if(saved&&saved<=huskArchiveMaxBytes){
     int contents=open(next.fileSystemRepresentation,O_RDONLY);if(contents>=0){fsync(contents);close(contents);}
     wrote=rename(next.fileSystemRepresentation,path.fileSystemRepresentation)==0;
    }
   }
   [archive release];
  }else failures++;
  if(writer){unlink(next.fileSystemRepresentation);if(wrote)huskArchivePrune(directory,path);}
  if(fd>=0){if(writer)flock(fd,LOCK_UN);close(fd);}
  id<MTLBinaryArchive> replacement=wrote?huskArchiveOpen(device,path):nil;
  {
   std::lock_guard<std::mutex> guard(huskArchiveLock);
   huskArchiveStats.prepared+=prepared;huskArchiveStats.prepare_failures+=failures;
   if(pending.size()>prepared+failures)huskArchiveStats.descriptors_dropped+=pending.size()-prepared-failures;
   huskArchiveStats.prepare_ns+=huskArchiveNow()-started;
   // A successful disk write remains successful if teardown cancels publishing
   // its live read archive. Keep I/O failures separate from that lifecycle case.
   if(wrote)huskArchiveStats.saved_bytes=saved;
   else if(prepared||!writer)huskArchiveStats.write_failures++;
   if(wrote&&!replacement)huskArchiveStats.read_failures++;
   if(wrote&&replacement&&generation==huskArchiveGeneration){[huskArchiveRead release];huskArchiveRead=replacement;}
   else [replacement release];
   huskArchiveStats.preparing=0;
  }
 }
 for(auto *candidate:pending)delete candidate;
 [device release];[path release];return wrote?1:-1;
}

extern "C" __attribute__((visibility("default"))) void vkHuskArchiveForget(void){
 std::lock_guard<std::mutex> guard(huskArchiveLock);
 huskArchiveEnabled.store(false);huskArchiveConfigured=false;huskArchiveGeneration++;
 for(auto *candidate:huskArchivePending)delete candidate;huskArchivePending.clear();
 [huskArchiveRead release];huskArchiveRead=nil;[huskArchiveDevice release];huskArchiveDevice=nil;
 [huskArchivePath release];huskArchivePath=nil;huskArchiveStats.supported=0;
 // In-flight preparation owns independent native retains and cannot republish
 // into this generation. No wait for a Metal compiler from Vulkan destruction.
}
static void huskArchiveNewRender(id<MTLDevice> device,MTLRenderPipelineDescriptor *descriptor,
                                void (^completion)(id<MTLRenderPipelineState>,NSError*)){ 
 if(!huskArchiveEnabled.load(std::memory_order_relaxed)){
  [device newRenderPipelineStateWithDescriptor:descriptor completionHandler:completion];return;
 }
 MTLRenderPipelineDescriptor *request=(MTLRenderPipelineDescriptor*)huskArchiveDescriptor(device,descriptor);uint64_t started=huskArchiveNow();
 [device newRenderPipelineStateWithDescriptor:request completionHandler:^(id<MTLRenderPipelineState> state,NSError *error){
  if(!state&&request!=descriptor){
   {std::lock_guard<std::mutex> guard(huskArchiveLock);huskArchiveStats.archive_fallbacks++;}
   @synchronized(device){[device newRenderPipelineStateWithDescriptor:descriptor completionHandler:^(id<MTLRenderPipelineState> fallback,NSError *fallbackError){
    huskArchiveCapture(device,descriptor,false,huskArchiveNow()-started,fallback!=nil);completion(fallback,fallbackError);
   }];}
  }else {huskArchiveCapture(device,descriptor,false,huskArchiveNow()-started,state!=nil);completion(state,error);}
 }];
 [request release];
}
static void huskArchiveNewCompute(id<MTLDevice> device,MTLComputePipelineDescriptor *descriptor,
                                 MTLPipelineOption options,void (^completion)(id<MTLComputePipelineState>,MTLComputePipelineReflection*,NSError*)){
 if(!huskArchiveEnabled.load(std::memory_order_relaxed)){
  [device newComputePipelineStateWithDescriptor:descriptor options:options completionHandler:completion];return;
 }
 MTLComputePipelineDescriptor *request=(MTLComputePipelineDescriptor*)huskArchiveDescriptor(device,descriptor);uint64_t started=huskArchiveNow();
 [device newComputePipelineStateWithDescriptor:request options:options completionHandler:^(id<MTLComputePipelineState> state,MTLComputePipelineReflection *reflection,NSError *error){
  if(!state&&request!=descriptor){
   {std::lock_guard<std::mutex> guard(huskArchiveLock);huskArchiveStats.archive_fallbacks++;}
   @synchronized(device){[device newComputePipelineStateWithDescriptor:descriptor options:options completionHandler:^(id<MTLComputePipelineState> fallback,MTLComputePipelineReflection *fallbackReflection,NSError *fallbackError){
    huskArchiveCapture(device,descriptor,true,huskArchiveNow()-started,fallback!=nil);completion(fallback,fallbackReflection,fallbackError);
   }];}
  }else {huskArchiveCapture(device,descriptor,true,huskArchiveNow()-started,state!=nil);completion(state,reflection,error);}
 }];
 [request release];
}
