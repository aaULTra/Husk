/* SPDX-License-Identifier: GPL-2.0-or-later */
#define _DARWIN_C_SOURCE
#include "husk-tl-audio.h"
#include "husk-tl-pcm.h"
#include <AudioToolbox/AudioToolbox.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <errno.h>
#include "husk-tl-bionic.h"
#include "husk-tl-cocos.h"
#define NBUF 3
#define FRAMES_PER_BUF 1024
#define RING_FRAMES 8192
static struct {
 pthread_mutex_t mu,control;
 pthread_cond_t cv;
 AudioQueueRef q;
 AudioQueueBufferRef bufs[NBUF];
 int rate,channels;
 int16_t *ring;
 size_t head,count;
 bool paused,interrupted,running;
 atomic_bool ready,failed;
} A={.mu=PTHREAD_MUTEX_INITIALIZER,.control=PTHREAD_MUTEX_INITIALIZER,.cv=PTHREAD_COND_INITIALIZER};
static int control_enter(void){int previous;pthread_setcancelstate(PTHREAD_CANCEL_DISABLE,&previous);pthread_mutex_lock(&A.control);return previous;}
static void control_leave(int previous){pthread_mutex_unlock(&A.control);pthread_setcancelstate(previous,NULL);}
static void unlock_samples(void *unused){(void)unused;pthread_mutex_unlock(&A.mu);}

static void on_buffer(void *user,AudioQueueRef q,AudioQueueBufferRef b){
 (void)user;
 pthread_mutex_lock(&A.mu);
 if(q!=A.q||!A.ring||A.failed){pthread_mutex_unlock(&A.mu);return;}
 size_t channels=(size_t)A.channels,want=FRAMES_PER_BUF;
 size_t take=A.paused||A.interrupted?0:(A.count<want?A.count:want);
 int16_t *out=b->mAudioData;
 tl_pcm_ring_read(out,A.ring,A.head,take,RING_FRAMES,channels);
 A.head=(A.head+take)%RING_FRAMES;A.count-=take;
 if(take)pthread_cond_broadcast(&A.cv);
 pthread_mutex_unlock(&A.mu);
 if(take<want)memset(out+take*channels,0,(want-take)*channels*sizeof(*out));
 b->mAudioDataByteSize=(UInt32)(want*channels*sizeof(*out));
 OSStatus status=AudioQueueEnqueueBuffer(q,b,0,NULL);
 if(status){
  pthread_mutex_lock(&A.mu);
  if(q==A.q){A.failed=true;A.running=false;pthread_cond_broadcast(&A.cv);}
  pthread_mutex_unlock(&A.mu);
 }
}
/* control is held; no AudioQueue API is invoked with the sample mutex held.
 * Immediate disposal quiesces callbacks before their ring storage is freed. */
static void dispose_queue(void){
 atomic_store_explicit(&A.ready,false,memory_order_release);
 pthread_mutex_lock(&A.mu);AudioQueueRef queue=A.q;A.q=NULL;A.running=false;
 pthread_cond_broadcast(&A.cv);pthread_mutex_unlock(&A.mu);
 if(queue)AudioQueueDispose(queue,true);
 pthread_mutex_lock(&A.mu);
 free(A.ring);A.ring=NULL;A.head=A.count=0;memset(A.bufs,0,sizeof(A.bufs));
 pthread_mutex_unlock(&A.mu);
}
static bool open_queue(int rate,int channels){
 pthread_mutex_lock(&A.mu);A.rate=rate;A.channels=channels;pthread_mutex_unlock(&A.mu);
 AudioStreamBasicDescription format={0};
 format.mSampleRate=rate;format.mFormatID=kAudioFormatLinearPCM;
 format.mFormatFlags=kLinearPCMFormatFlagIsSignedInteger|kLinearPCMFormatFlagIsPacked;
 format.mBitsPerChannel=16;format.mChannelsPerFrame=(UInt32)channels;format.mFramesPerPacket=1;
 format.mBytesPerFrame=format.mBytesPerPacket=(UInt32)(channels*sizeof(int16_t));
 int16_t *ring=calloc((size_t)RING_FRAMES*(size_t)channels,sizeof(*ring));
 if(!ring)return false;
 AudioQueueRef queue=NULL;
 OSStatus status=AudioQueueNewOutput(&format,on_buffer,NULL,NULL,NULL,0,&queue);
 if(status||!queue){if(queue)AudioQueueDispose(queue,true);free(ring);return false;}
 pthread_mutex_lock(&A.mu);
 A.q=queue;A.ring=ring;A.rate=rate;A.channels=channels;A.failed=false;A.running=false;A.head=A.count=0;
 bool paused=A.paused||A.interrupted;
 pthread_mutex_unlock(&A.mu);
 for(int i=0;i<NBUF;i++){
  status=AudioQueueAllocateBuffer(queue,FRAMES_PER_BUF*(UInt32)channels*sizeof(int16_t),&A.bufs[i]);
  if(status||!A.bufs[i]||!A.bufs[i]->mAudioData){dispose_queue();return false;}
  memset(A.bufs[i]->mAudioData,0,FRAMES_PER_BUF*(size_t)channels*sizeof(int16_t));
  A.bufs[i]->mAudioDataByteSize=FRAMES_PER_BUF*(UInt32)channels*sizeof(int16_t);
  if(AudioQueueEnqueueBuffer(queue,A.bufs[i],0,NULL)){dispose_queue();return false;}
 }
 if(!paused&&(status=AudioQueueStart(queue,NULL))){dispose_queue();return false;}
 pthread_mutex_lock(&A.mu);bool ok=!A.failed;A.running=ok&&!paused;pthread_mutex_unlock(&A.mu);
 if(!ok){dispose_queue();return false;}
 atomic_store_explicit(&A.ready,true,memory_order_release);
 tl_log_line("audio: output running, %d Hz, %d channel(s)",rate,channels);return true;
}
static bool ensure_queue(int rate,int channels){
 if(atomic_load_explicit(&A.failed,memory_order_acquire))return false;
 if(atomic_load_explicit(&A.ready,memory_order_acquire))return true;
 int cancellation=control_enter();
 pthread_mutex_lock(&A.mu);bool failed=A.failed,exists=A.q!=NULL;pthread_mutex_unlock(&A.mu);
 bool ok=!failed&&(exists||open_queue(rate,channels));
 if(!ok){pthread_mutex_lock(&A.mu);A.failed=true;pthread_cond_broadcast(&A.cv);pthread_mutex_unlock(&A.mu);}
 control_leave(cancellation);return ok;
}
static void sleep_for(int frames,int rate){
 if(frames<=0||rate<=0)return;
 int64_t ns=(int64_t)frames*1000000000LL/rate;
 struct timespec delay={(time_t)(ns/1000000000LL),(long)(ns%1000000000LL)};
 while(nanosleep(&delay,&delay)&&errno==EINTR){}
}
static void ring_write(const int16_t *samples,int frames,int channels,int rate){
 if(!ensure_queue(rate,channels)){sleep_for(frames,rate);return;}
 int remaining=frames;
 pthread_mutex_lock(&A.mu);
 pthread_cleanup_push(unlock_samples,NULL);
 if(!A.failed&&A.q&&channels==A.channels){
  int done=0;
  while(done<frames){
   while(!A.failed&&A.q&&(A.count>=RING_FRAMES||A.paused||A.interrupted))pthread_cond_wait(&A.cv,&A.mu);
   if(A.failed||!A.q)break;
   size_t room=RING_FRAMES-A.count,n=(size_t)(frames-done)<room?(size_t)(frames-done):room;
   size_t tail=(A.head+A.count)%RING_FRAMES;
   tl_pcm_ring_write(A.ring,tail,samples+(size_t)done*(size_t)channels,n,RING_FRAMES,(size_t)channels);
   A.count+=n;done+=(int)n;
  }
  remaining=frames-done;
 }
 pthread_cleanup_pop(1);
 if(remaining)sleep_for(remaining,rate);
}
static void host_write(const int16_t *samples,int frames,int channels,int rate){
 if(!samples||frames<=0||channels<=0||channels>8||rate<=0||rate>768000)return;
 if(rate<=24000&&channels<=2){
  static _Thread_local struct {int16_t previous[2],scratch[1024*2*2];int rate,channels;bool have;} history;
  if(history.rate!=rate||history.channels!=channels){history.rate=rate;history.channels=channels;history.have=false;}
  int16_t *up=history.scratch; // bounded per-mixer storage; no large guest-stack temporary
  for(int done=0;done<frames;){
   int n=frames-done;if(n>1024)n=1024;
   tl_pcm_double(up,samples+(size_t)done*(size_t)channels,(size_t)n,(unsigned)channels,history.previous,history.have);
   history.have=true;ring_write(up,n*2,channels,rate*2);done+=n;
  }
 }else ring_write(samples,frames,channels,rate);
}
static void muted_write(const int16_t *samples,int frames,int channels,int rate){
 static int stats=-1,seen,peak;static long loud,total;
 if(!samples||frames<=0||channels<=0||channels>8||rate<=0||rate>768000)return;
 if(stats<0)stats=getenv("TL_AUDIO_STATS")!=NULL;
 if(stats){
  for(size_t i=0;i<(size_t)frames*(size_t)channels;i++){int v=samples[i]<0?-samples[i]:samples[i];if(v>peak)peak=v;if(v>64)loud++;}
  total+=(long)frames*channels;
  if((seen+=frames)>=rate){tl_log_line("audio: %d Hz x %d, peak %d, %.0f%% of samples audible",rate,channels,peak,100.0*loud/(total?total:1));seen=peak=0;loud=total=0;}
 }
 sleep_for(frames,rate);
}
void tl_audio_install(void){tl_cocos_audio_hook=getenv("TL_AUDIO_MUTE")?muted_write:host_write;}
static void set_pause(bool paused,bool interruption){
 int cancellation=control_enter();pthread_mutex_lock(&A.mu);
 if(interruption)A.interrupted=paused;else A.paused=paused;
 bool effective=A.paused||A.interrupted;AudioQueueRef queue=A.q;
 bool change=queue&&(effective?A.running:!A.running);
 pthread_cond_broadcast(&A.cv);pthread_mutex_unlock(&A.mu);
 if(change){
  OSStatus status=effective?AudioQueuePause(queue):AudioQueueStart(queue,NULL);
  pthread_mutex_lock(&A.mu);if(queue==A.q){A.running=!effective&&!status;if(status&&!effective)A.failed=true;pthread_cond_broadcast(&A.cv);}pthread_mutex_unlock(&A.mu);
  if(status)tl_log_line("audio: %s failed (%d); explicit recovery can rebuild output",effective?"pause":"resume",(int)status);
 }
 control_leave(cancellation);
}
void tl_audio_set_paused(bool paused){set_pause(paused,false);}
void tl_audio_set_interrupted(bool interrupted){set_pause(interrupted,true);}
static void recover_output(bool force){
 int cancellation=control_enter();pthread_mutex_lock(&A.mu);
 int rate=A.rate,channels=A.channels;bool have_format=rate>0&&channels>0&&(force||A.failed||!A.q);
 pthread_mutex_unlock(&A.mu);
 if(have_format){
  dispose_queue();pthread_mutex_lock(&A.mu);A.failed=false;pthread_mutex_unlock(&A.mu);
  bool ok=open_queue(rate,channels);
  pthread_mutex_lock(&A.mu);if(!ok)A.failed=true;pthread_cond_broadcast(&A.cv);pthread_mutex_unlock(&A.mu);
  tl_log_line("audio: output recovery %s",ok?"ready":"failed");
 }
 control_leave(cancellation);
}

void tl_audio_recover(void){recover_output(true);}
void tl_audio_recover_if_needed(void){recover_output(false);}
