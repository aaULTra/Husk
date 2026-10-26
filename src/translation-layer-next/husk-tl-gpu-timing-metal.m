/* SPDX-License-Identifier: GPL-2.0-or-later */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <QuartzCore/QuartzCore.h>
#import <objc/runtime.h>
#include <pthread.h>
#include "husk-tl-gpu-timing.h"
/* Opt-in adapter for direct MoltenVK queues only. Factory interception is
 * concrete-class scoped, chained, and filters the exact registered queue before
 * attaching a handler. Other host/ANGLE queues are passed through unchanged.
 * No command-buffer commit/present operation or encoder is replaced. */
@interface HuskGPUQueueTag : NSObject
@property(nonatomic) void *device;
@property(nonatomic) uint64_t identity;
@property(atomic) BOOL hooked;
@end
@implementation HuskGPUQueueTag
@end
static char queue_key;
static pthread_mutex_t registry_mu=PTHREAD_MUTEX_INITIALIZER;
static NSMutableArray *queues;
static Class hooked_classes[8];
static unsigned class_count, failures;
static uint64_t next_queue;
static _Thread_local unsigned factory_depth;
static void observe(id buffer,id queue){
    if(!buffer||!tl_gput_active())return;
    HuskGPUQueueTag *tag=objc_getAssociatedObject(queue,&queue_key);
    if(!tag||!tag.hooked)return;
    tl_gput_ticket ticket;
    if(!tl_gput_capture(CACurrentMediaTime(),tag.identity,&ticket))return;
    [buffer addCompletedHandler:^(id<MTLCommandBuffer> cb){
        NSString *label=[cb respondsToSelector:@selector(label)]?cb.label:nil;
        uint32_t kind=TL_GPUT_UNKNOWN;
        if([label hasPrefix:@"vkAcquireNextImage"])kind=TL_GPUT_ACQUIRE;
        else if([label hasPrefix:@"vkQueueSubmit"]||[label hasPrefix:@"vkBeginCommandBuffer"])kind=TL_GPUT_SUBMIT;
        else if([label hasPrefix:@"vkQueuePresent"])kind=TL_GPUT_PRESENT;
        else if(label.length)kind=TL_GPUT_OTHER;
        tl_gput_complete_kind(ticket,cb.GPUStartTime,cb.GPUEndTime,CACurrentMediaTime(),cb.status==MTLCommandBufferStatusCompleted,kind);
    }];
}
/* Called off the rendering path during session start or rare queue discovery. */
static bool install(id queue){
    Class cls=object_getClass(queue);
    for(unsigned i=0;i<class_count;i++)if(hooked_classes[i]==cls)return true;
    if(class_count==8){failures++;return false;}
    SEL sel=@selector(commandBufferWithDescriptor:);
    Method method=class_getInstanceMethod(cls,sel);
    if(!method||method_getNumberOfArguments(method)!=3){failures++;return false;}
    char ret[8]={0},arg[8]={0};method_getReturnType(method,ret,sizeof(ret));method_getArgumentType(method,2,arg,sizeof(arg));
    if(ret[0]!='@'||arg[0]!='@'){failures++;return false;}
    IMP original=method_getImplementation(method);
    IMP replacement=imp_implementationWithBlock(^id(id receiver,id descriptor){
        factory_depth++;
        id buffer=((id(*)(id,SEL,id))original)(receiver,sel,descriptor);
        factory_depth--;
        if(!factory_depth)observe(buffer,receiver);
        return buffer;
    });
    /* Add on this class if inherited; never replace an inherited base method. */
    if(!class_addMethod(cls,sel,replacement,method_getTypeEncoding(method))){
        Method own=class_getInstanceMethod(cls,sel);
        if(method_getImplementation(own)!=original){imp_removeBlock(replacement);failures++;return false;}
        method_setImplementation(own,replacement);
    }
    hooked_classes[class_count++]=cls;return true;
}
static void publish(void){
    unsigned hooked=0;for(id queue in queues){HuskGPUQueueTag *t=objc_getAssociatedObject(queue,&queue_key);hooked+=t.hooked;}
    tl_gput_queue_state((uint32_t)queues.count,hooked,failures);
}
void tl_gput_native_register(void *device,void *raw){
    if(!device||!raw)return;
    id queue=(__bridge id)raw;
    pthread_mutex_lock(&registry_mu);
    if(!queues)queues=[NSMutableArray new];
    HuskGPUQueueTag *tag=objc_getAssociatedObject(queue,&queue_key);
    if(!tag&&queues.count<16){
        tag=[HuskGPUQueueTag new];tag.device=device;tag.identity=++next_queue;
        objc_setAssociatedObject(queue,&queue_key,tag,OBJC_ASSOCIATION_RETAIN_NONATOMIC);[queues addObject:queue];
    }
    if(tag&&tl_gput_active())tag.hooked=install(queue);
    if(!tag)failures++;
    publish();pthread_mutex_unlock(&registry_mu);
}
void tl_gput_native_start(bool requested){
    tl_gput_begin(requested,CACurrentMediaTime());
    pthread_mutex_lock(&registry_mu);
    if(requested)for(id queue in queues){HuskGPUQueueTag *tag=objc_getAssociatedObject(queue,&queue_key);tag.hooked=install(queue);}
    publish();pthread_mutex_unlock(&registry_mu);
}
void tl_gput_native_exclude(bool value,double *before,double *after){
    double a=CACurrentMediaTime();tl_gput_exclude(value);double b=CACurrentMediaTime();
    if(before)*before=a;if(after)*after=b;
}
void tl_gput_native_forget(void *device){
    pthread_mutex_lock(&registry_mu);
    for(NSInteger i=(NSInteger)queues.count-1;i>=0;i--){id queue=queues[(NSUInteger)i];HuskGPUQueueTag *tag=objc_getAssociatedObject(queue,&queue_key);if(tag.device==device){objc_setAssociatedObject(queue,&queue_key,nil,OBJC_ASSOCIATION_RETAIN_NONATOMIC);[queues removeObjectAtIndex:(NSUInteger)i];}}
    publish();pthread_mutex_unlock(&registry_mu);
}
