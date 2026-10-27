#!/usr/bin/env python3
"""Execute production PCM/audio code against a deterministic AudioQueue facade."""
import os, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];TL=ROOT/'src/translation-layer-next'
HEADER=r'''
#include <stdint.h>
#include <stdbool.h>
typedef uint32_t UInt32;typedef int32_t OSStatus;
typedef struct Queue *AudioQueueRef;
typedef struct Buffer { UInt32 mAudioDataBytesCapacity;void *mAudioData;UInt32 mAudioDataByteSize; } *AudioQueueBufferRef;
typedef struct {double mSampleRate;UInt32 mFormatID,mFormatFlags,mBytesPerPacket,mFramesPerPacket,mBytesPerFrame,mChannelsPerFrame,mBitsPerChannel;} AudioStreamBasicDescription;
enum {noErr=0,kAudioFormatLinearPCM=1,kLinearPCMFormatFlagIsSignedInteger=1,kLinearPCMFormatFlagIsPacked=2};
OSStatus AudioQueueNewOutput(const AudioStreamBasicDescription*,void(*)(void*,AudioQueueRef,AudioQueueBufferRef),void*,void*,void*,UInt32,AudioQueueRef*);
OSStatus AudioQueueAllocateBuffer(AudioQueueRef,UInt32,AudioQueueBufferRef*);
OSStatus AudioQueueEnqueueBuffer(AudioQueueRef,AudioQueueBufferRef,UInt32,const void*);
OSStatus AudioQueueStart(AudioQueueRef,const void*);OSStatus AudioQueuePause(AudioQueueRef);OSStatus AudioQueueDispose(AudioQueueRef,bool);
'''
HARNESS=r'''
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <time.h>
#include <sched.h>
static int allocations,fail_allocation;
static void *audio_calloc(size_t n,size_t s){allocations++;return fail_allocation?NULL:calloc(n,s);}
#define calloc audio_calloc
#include "audio.c"
#undef calloc
void (*tl_cocos_audio_hook)(const int16_t*,int,int,int);
void tl_log_line(const char *fmt,...){(void)fmt;}
struct Queue {void(*callback)(void*,AudioQueueRef,AudioQueueBufferRef);AudioQueueBufferRef buffers[3];unsigned count;};
static int new_calls,dispose_calls,start_calls,pause_calls,enqueue_calls,fail_new,fail_buffer,fail_enqueue,fail_start,fail_pause;
static void unlocked(void){int rc=pthread_mutex_trylock(&A.mu);assert(!rc);pthread_mutex_unlock(&A.mu);}
OSStatus AudioQueueNewOutput(const AudioStreamBasicDescription*f,void(*cb)(void*,AudioQueueRef,AudioQueueBufferRef),void*u,void*l,void*m,UInt32 flags,AudioQueueRef*out){
 (void)u;(void)l;(void)m;(void)flags;unlocked();new_calls++;assert(f->mFramesPerPacket==1&&f->mBitsPerChannel==16);
 if(fail_new)return -1;*out=calloc(1,sizeof(**out));(*out)->callback=cb;return 0;
}
OSStatus AudioQueueAllocateBuffer(AudioQueueRef q,UInt32 bytes,AudioQueueBufferRef*out){unlocked();if(fail_buffer)return -2;*out=calloc(1,sizeof(**out));(*out)->mAudioData=calloc(1,bytes);(*out)->mAudioDataBytesCapacity=bytes;q->buffers[q->count++]=*out;return 0;}
OSStatus AudioQueueEnqueueBuffer(AudioQueueRef q,AudioQueueBufferRef b,UInt32 n,const void*d){(void)q;(void)b;(void)n;(void)d;unlocked();enqueue_calls++;return fail_enqueue?-3:0;}
OSStatus AudioQueueStart(AudioQueueRef q,const void*t){(void)t;unlocked();start_calls++;if(fail_start)return -4;if(q->count)q->callback(NULL,q,q->buffers[0]);return 0;}
OSStatus AudioQueuePause(AudioQueueRef q){unlocked();pause_calls++;if(q->count)q->callback(NULL,q,q->buffers[0]);return fail_pause?-5:0;}
OSStatus AudioQueueDispose(AudioQueueRef q,bool immediate){unlocked();assert(immediate);dispose_calls++;for(unsigned i=0;i<q->count;i++){free(q->buffers[i]->mAudioData);free(q->buffers[i]);}free(q);return 0;}
static void drain(void){AudioQueueRef q=A.q;assert(q);on_buffer(NULL,q,q->buffers[0]);}
static int16_t input[20000];
static _Atomic int entered,done;
static void *writer(void*unused){(void)unused;atomic_store(&entered,1);host_write(input,1,2,44100);atomic_store(&done,1);return NULL;}
static void pause_ms(void){struct timespec t={0,20000000};nanosleep(&t,NULL);}
static void blocked_writer(bool cancel){pthread_t t;assert(!pthread_create(&t,NULL,writer,NULL));while(!atomic_load(&entered))sched_yield();pause_ms();assert(!atomic_load(&done));if(cancel){pthread_cancel(t);void *result;pthread_join(t,&result);assert(result==PTHREAD_CANCELED);unlocked();}else{tl_audio_set_paused(false);pthread_join(t,NULL);assert(atomic_load(&done));}}
static void pcm(void){
 int16_t ring[17*8],out[17*8],source[17*8];
 for(unsigned c=1;c<=8;c++)for(unsigned head=0;head<17;head++)for(unsigned n=0;n<=17;n++){
  for(unsigned i=0;i<17*c;i++){ring[i]=(int16_t)(i*3-100);source[i]=(int16_t)(i*5+100);out[i]=-123;}
  tl_pcm_ring_read(out,ring,head,n,17,c);
  for(unsigned i=0;i<n;i++)for(unsigned j=0;j<c;j++)assert(out[i*c+j]==ring[((head+i)%17)*c+j]);
  tl_pcm_ring_write(ring,head,source,n,17,c);
  for(unsigned i=0;i<n;i++)for(unsigned j=0;j<c;j++)assert(ring[((head+i)%17)*c+j]==source[i*c+j]);
 }
}
int main(int argc,char**argv){assert(argc==2);for(unsigned i=0;i<20000;i++)input[i]=(int16_t)(i*97-32000);
 if(!strcmp(argv[1],"pcm")){pcm();return 0;}
 if(!strcmp(argv[1],"invalid")){host_write(NULL,1,2,44100);host_write(input,0,2,44100);host_write(input,1,0,44100);host_write(input,1,9,44100);host_write(input,1,2,0);host_write(input,1,2,1000000);assert(!allocations&&!new_calls);return 0;}
 if(!strcmp(argv[1],"interpolation")){
  host_write(input,2000,2,22050);assert(allocations==1&&A.count==4000&&A.rate==44100);
  int16_t expected[8000];
  /* Independent reference: the previous whole-buffer interpolation, including
     the first frame and the production chunk boundary at1024. */
  for(unsigned f=0;f<2000;f++)for(unsigned c=0;c<2;c++){
   int16_t current=input[f*2+c],before=f?input[(f-1)*2+c]:current;
   expected[(2*f)*2+c]=(int16_t)(((int)before+current)/2);expected[(2*f+1)*2+c]=current;
  }
  for(unsigned i=0;i<4;i++){drain();int16_t *data=A.bufs[0]->mAudioData;for(unsigned j=0;j<2048;j++){unsigned at=i*2048+j;assert(data[j]==(at<8000?expected[at]:0));}}
  assert(!A.count&&allocations==1);
 }else if(!strcmp(argv[1],"control")){
  host_write(input,4,2,44100);assert(start_calls==1);tl_audio_recover_if_needed();assert(!dispose_calls&&start_calls==1);tl_audio_set_paused(true);assert(pause_calls==1);
  tl_audio_set_paused(true);assert(pause_calls==1);tl_audio_set_interrupted(true);tl_audio_set_paused(false);assert(start_calls==1);
  tl_audio_recover();assert(dispose_calls==1&&start_calls==1&&!A.running&&A.interrupted);
  tl_audio_set_interrupted(false);assert(start_calls==2&&A.running&&!A.failed);
 }else if(!strcmp(argv[1],"paused-first")){
  tl_audio_set_paused(true);assert(ensure_queue(44100,2));assert(!start_calls&&A.paused);blocked_writer(false);assert(start_calls==1);
 }else if(!strcmp(argv[1],"cancel")){
  assert(ensure_queue(44100,2));tl_audio_set_paused(true);blocked_writer(true);tl_audio_set_paused(false);host_write(input,1,2,44100);assert(A.count==1);
 }else if(!strcmp(argv[1],"failure")){
  fail_buffer=1;assert(!ensure_queue(44100,2));assert(A.failed&&!A.q&&!A.ring&&dispose_calls==1);fail_buffer=0;tl_audio_recover();assert(A.q&&A.ready&&!A.failed&&A.running);
 }else if(!strcmp(argv[1],"allocation")){
  fail_allocation=1;assert(!ensure_queue(44100,2));assert(!new_calls&&A.failed&&!A.ring);fail_allocation=0;tl_audio_recover();assert(A.ready&&!A.failed);
 }else if(!strcmp(argv[1],"start-failure")){
  fail_start=1;assert(!ensure_queue(44100,2));assert(A.failed&&!A.q&&!A.ring);fail_start=0;tl_audio_recover();assert(A.ready&&A.running&&!A.failed);
 }else if(!strcmp(argv[1],"enqueue-failure")){
  assert(ensure_queue(44100,2));host_write(input,1,2,44100);fail_enqueue=1;drain();assert(A.failed);fail_enqueue=0;tl_audio_recover();assert(A.ready&&!A.failed);
 }else if(!strcmp(argv[1],"silence")){
  assert(ensure_queue(44100,2));drain();int16_t *data=A.bufs[0]->mAudioData;for(unsigned i=0;i<2048;i++)assert(!data[i]);
 }else assert(0);
 int cancellation=control_enter();dispose_queue();control_leave(cancellation);assert(!A.q&&!A.ring);return 0;
}
'''
class AudioTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);p=Path(cls.tmp.name);(p/'AudioToolbox').mkdir();(p/'AudioToolbox/AudioToolbox.h').write_text(HEADER)
  (p/'husk-tl-bionic.h').write_text('void tl_log_line(const char*,...);\n');(p/'husk-tl-cocos.h').write_text('#include <stdint.h>\nextern void (*tl_cocos_audio_hook)(const int16_t*,int,int,int);\n')
  (p/'audio.c').write_bytes((TL/'husk-tl-audio.c').read_bytes());(p/'test.c').write_text(HARNESS);cls.exe=p/'check'
  subprocess.run([os.environ.get('CC','cc'),'-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-pthread','-I',str(p),'-I',str(TL),str(p/'test.c'),'-o',str(cls.exe)],check=True)
 def case(self,name):subprocess.run([str(self.exe),name],check=True,timeout=10)
 def test_ring_wrap_all_spans_channels_preserve_pcm(self):self.case('pcm')
 def test_streamed_interpolation_has_identical_samples_without_per_write_allocation(self):self.case('interpolation')
 def test_control_apis_and_synchronous_callbacks_run_outside_sample_lock(self):self.case('control')
 def test_pause_before_first_write_never_starts_hidden_output(self):self.case('paused-first')
 def test_cancelled_writer_releases_sample_mutex(self):self.case('cancel')
 def test_partial_buffer_failure_disposes_everything_and_can_recover(self):self.case('failure')
 def test_allocation_failure_can_recover_without_invalid_queue(self):self.case('allocation')
 def test_start_failure_quiesces_and_releases_resources_before_recovery(self):self.case('start-failure')
 def test_callback_enqueue_failure_has_a_recovery_path(self):self.case('enqueue-failure')
 def test_empty_ring_produces_silence_without_waiting(self):self.case('silence')
 def test_invalid_input_does_not_allocate_or_touch_audio_queue(self):self.case('invalid')
if __name__=='__main__':unittest.main()
