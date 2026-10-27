/* SPDX-License-Identifier: GPL-2.0-or-later */
// Optional diagnostics at the existing drawable callback. No scheduling change.
#include "HuskDisplayABI.h"
#include <atomic>
#include <mutex>
#include <cstring>
static std::atomic<bool> huskDisplayGate{false};
static std::atomic<uint64_t> huskDisplayEpoch{0},huskDisplayAttempts{0},huskDisplayDrops{0},huskDisplayGenerationCounter{0};
static std::mutex huskDisplayLock;
static tl_display_stats huskDisplayStats={1,sizeof(tl_display_stats)};
static tl_display_record huskDisplayRows[TL_DISPLAY_CAPACITY]={};
static uint32_t huskDisplayHead=0,huskDisplayCount=0;
static uint64_t huskDisplayAfter=0,huskDisplayLastSequence=0,huskDisplayLastGeneration=0,huskDisplayLastTime=0;
static bool huskDisplaySession=false,huskDisplayExcluded=true;
uint64_t huskDisplayNewGeneration(){return huskDisplayGenerationCounter.fetch_add(1,std::memory_order_relaxed)+1;}
bool huskDisplayMonitoring(){return huskDisplayGate.load(std::memory_order_relaxed);}
extern "C" __attribute__((visibility("default"))) int vkHuskDisplayConfigure(const tl_display_config *c){
 if(!c||c->version!=1||c->size!=sizeof(*c)||c->enabled>1||c->excluded>1)return 0;
 huskDisplayGate.store(false);std::lock_guard<std::mutex> guard(huskDisplayLock);
 if(c->enabled&&!huskDisplaySession){
  huskDisplayStats={1,sizeof(tl_display_stats)};huskDisplayHead=huskDisplayCount=0;
  huskDisplayAttempts.store(0);huskDisplayDrops.store(0);memset(huskDisplayRows,0,sizeof(huskDisplayRows));
 }
 huskDisplaySession=c->enabled;huskDisplayExcluded=c->excluded;
 huskDisplayAfter=c->include_after_media_ns;huskDisplayLastSequence=huskDisplayLastGeneration=huskDisplayLastTime=0;
 huskDisplayStats.epoch=huskDisplayEpoch.fetch_add(1)+1;
 huskDisplayStats.enabled=c->enabled;huskDisplayStats.excluded=c->excluded;
 huskDisplayGate.store(c->enabled&&!c->excluded);return 1;
}
void huskDisplayObserve(uint64_t generation,uint32_t googleID,uint64_t desiredUnused,uint64_t raw,uint64_t effective,uint64_t begin,uint64_t observed){
 (void)desiredUnused;if(!huskDisplayMonitoring())return;
 uint64_t epoch=huskDisplayEpoch.load(),sequence=huskDisplayAttempts.fetch_add(1)+1;
 std::unique_lock<std::mutex> guard(huskDisplayLock,std::try_to_lock);
 if(!guard.owns_lock()){huskDisplayDrops.fetch_add(1);return;}
 if(epoch!=huskDisplayEpoch.load()||!huskDisplaySession||huskDisplayExcluded){huskDisplayStats.boundary_events++;return;}
 if(!generation||!observed||observed<huskDisplayAfter||
    (raw&&(raw<huskDisplayAfter||raw>observed))){huskDisplayStats.boundary_events++;huskDisplayLastSequence=0;return;}
 if(!effective){huskDisplayStats.invalid_events++;huskDisplayLastSequence=0;return;}
 uint32_t source=raw?1u:2u;
 if(raw){
  huskDisplayStats.direct_events++;
  if(huskDisplayLastSequence+1==sequence&&huskDisplayLastGeneration==generation&&raw>huskDisplayLastTime){
   uint64_t dt=raw-huskDisplayLastTime;huskDisplayStats.intervals++;huskDisplayStats.interval_ns+=dt;
   if(dt>huskDisplayStats.worst_interval_ns)huskDisplayStats.worst_interval_ns=dt;
   huskDisplayStats.above20+=dt>20000000;huskDisplayStats.above33+=dt>33333333;huskDisplayStats.above50+=dt>50000000;
   uint64_t bucket=dt/100000+(dt%100000!=0);if(bucket>=TL_DISPLAY_BINS)bucket=TL_DISPLAY_BINS-1;huskDisplayStats.histogram[bucket]++;
  }
  if(huskDisplayLastSequence&&huskDisplayLastGeneration==generation&&raw<=huskDisplayLastTime){huskDisplayStats.invalid_events++;huskDisplayLastSequence=0;}
  else {huskDisplayLastSequence=sequence;huskDisplayLastGeneration=generation;huskDisplayLastTime=raw;}
 }else {huskDisplayStats.estimated_events++;huskDisplayLastSequence=0;}
 if(huskDisplayCount==TL_DISPLAY_CAPACITY){huskDisplayHead=(huskDisplayHead+1)%TL_DISPLAY_CAPACITY;huskDisplayCount--;huskDisplayStats.overwrites++;}
 huskDisplayRows[(huskDisplayHead+huskDisplayCount++)%TL_DISPLAY_CAPACITY]={sequence,generation,raw,effective,begin,observed,googleID,source};
}
extern "C" __attribute__((visibility("default"))) int vkHuskDisplaySnapshot(tl_display_stats *out,tl_display_record *rows,uint32_t capacity){
 if(!out||out->version!=1||out->size!=sizeof(*out)||capacity>TL_DISPLAY_CAPACITY||(capacity&&!rows))return -1;
 std::lock_guard<std::mutex> guard(huskDisplayLock);*out=huskDisplayStats;
 out->retained=huskDisplayCount;out->capacity=TL_DISPLAY_CAPACITY;out->attempts=huskDisplayAttempts.load();out->contention_drops=huskDisplayDrops.load();
 uint32_t n=capacity<huskDisplayCount?capacity:huskDisplayCount;
 for(uint32_t i=0;i<n;i++)rows[i]=huskDisplayRows[(huskDisplayHead+i)%TL_DISPLAY_CAPACITY];
 return (int)n;
}
