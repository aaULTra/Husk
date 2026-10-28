/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifdef __APPLE__
#define _DARWIN_C_SOURCE 1
#else
#define _POSIX_C_SOURCE 200809L
#endif
#include "husk-tl-crash-signal.h"
#include <signal.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stddef.h>
#include <pthread.h>
#include <unistd.h>
#if defined(__APPLE__) && defined(__aarch64__)
#include <sys/ucontext.h>
#endif
_Static_assert(ATOMIC_INT_LOCK_FREE==2,"Signal metadata requires lock-free int atomics");
static atomic_int main_fd=-1,stream_fd=-1,guest_fd=-1,report_fd=-1;
typedef struct {uintptr_t bias,begin,end;char name[96];} image;
static image images[64];
static atomic_uint image_count;
static pthread_mutex_t image_lock=PTHREAD_MUTEX_INITIALIZER;
void husk_crash_native_sink(int fd){atomic_store(&guest_fd,fd);}
void husk_crash_report_sink(int fd){atomic_store(&report_fd,fd);}
/* Sparse launch checkpoints of our fork's experimental subsystems. Unlike the
 * signal handler this runs in ordinary code, but stays allocation-free. The
 * bounded one-write record and fsync mean a hard crash still leaves the last
 * completed checkpoint in Files; not proof of which subsystem caused it. */
void husk_crash_stage(const char *stage){
 int fd=atomic_load_explicit(&report_fd,memory_order_acquire);
 if(fd<0||!stage)return;
 char rec[192];size_t at=0;
 const char *prefix="[fork-stage] ";
 while(*prefix&&at<sizeof(rec)-2)rec[at++]=*prefix++;
 while(*stage&&at<sizeof(rec)-2) {
  const unsigned char c=(unsigned char)*stage++;
  if(c<32||c>126)break;
  rec[at++]=(char)c;
 }
 rec[at++]='\n';
 (void)!write(fd,rec,at);
 (void)fsync(fd);
}

void husk_crash_note_image(const char *name,uintptr_t bias,uintptr_t begin,uintptr_t end){
 if(!name||begin>=end)return;
 pthread_mutex_lock(&image_lock);unsigned i=atomic_load_explicit(&image_count,memory_order_relaxed);
 if(i<64){
  images[i].bias=bias;images[i].begin=begin;images[i].end=end;
  unsigned n=0;while(n<95&&name[n]){images[i].name[n]=name[n];n++;}images[i].name[n]=0;
  atomic_store_explicit(&image_count,i+1,memory_order_release);
 }
 pthread_mutex_unlock(&image_lock);
}
static size_t literal(char *out,size_t at,const char *text){while(*text&&at<1000)out[at++]=*text++;return at;}
static size_t number(char *out,size_t at,uintptr_t value,unsigned base){
 char digits[32];unsigned n=0;do{digits[n++]="0123456789abcdef"[value%base];value/=base;}while(value&&n<sizeof(digits));
 while(n&&at<1000)out[at++]=digits[--n];
 return at;
}
static size_t address(char *out,size_t at,const char *label,uintptr_t value){
 at=literal(out,at,label);at=literal(out,at,"0x");return number(out,at,value,16);
}
static void fatal(int signal_number,siginfo_t *info,void *context){
 /* No allocation, Swift runtime, logger/loader lock, dladdr, backtrace or
  * arbitrary frame-pointer dereference. SIGKILL/watchdogs cannot be caught. */
 char record[1024];size_t at=literal(record,0,"\n*** FATAL SIGNAL ");
 at=number(record,at,(uintptr_t)signal_number,10);at=literal(record,at," -- process terminating ***\n");
 uintptr_t pc=0;
#if defined(__APPLE__) && defined(__aarch64__)
 ucontext_t *uc=context;if(uc&&uc->uc_mcontext){
  pc=(uintptr_t)uc->uc_mcontext->__ss.__pc;
  at=address(record,at,"pc ",pc);at=address(record,at," lr ",(uintptr_t)uc->uc_mcontext->__ss.__lr);
  at=address(record,at," sp ",(uintptr_t)uc->uc_mcontext->__ss.__sp);at=literal(record,at,"\n");
 }
#else
 (void)context;
#endif
 if(info){at=address(record,at,"fault address ",(uintptr_t)info->si_addr);at=literal(record,at,"\n");}
 unsigned count=atomic_load_explicit(&image_count,memory_order_acquire);
 for(unsigned i=0;i<count;i++)if(pc>=images[i].begin&&pc<images[i].end){
  at=literal(record,at,"guest image ");at=literal(record,at,images[i].name);
  at=address(record,at," offset ",pc-images[i].bias);at=literal(record,at,"\n");break;
 }
 int fds[4]={atomic_load(&main_fd),atomic_load(&stream_fd),atomic_load(&guest_fd),atomic_load(&report_fd)};
 for(unsigned i=0;i<4;i++){
  if(fds[i]<0)continue;
  bool duplicate=false;
  for(unsigned j=0;j<i;j++)if(fds[i]==fds[j])duplicate=true;
  if(duplicate)continue;
  /* No locks, allocation, Swift or Foundation from the signal handler. */
  (void)!write(fds[i],record,at);
 }
 /* The dedicated small crash marker is independent of the normal log reader.
  * Preserve this final record before re-raising the signal. */
 if(fds[3]>=0)(void)fsync(fds[3]);
 struct sigaction action={0};action.sa_handler=SIG_DFL;sigemptyset(&action.sa_mask);
 sigaction(signal_number,&action,NULL);
 if(kill(getpid(),signal_number)!=0)_exit(128+signal_number);
}
int husk_crash_install(int log_fd,int native_fd){
 atomic_store(&main_fd,log_fd);atomic_store(&stream_fd,native_fd);
 const int signals[]={SIGSEGV,SIGABRT,SIGILL,SIGFPE,SIGSYS};int installed=0;
 struct sigaction action={0};action.sa_sigaction=fatal;action.sa_flags=SA_SIGINFO;sigemptyset(&action.sa_mask);
 for(unsigned i=0;i<sizeof(signals)/sizeof(signals[0]);i++)if(sigaction(signals[i],&action,NULL)==0)installed++;
 return installed; /* SIGBUS/SIGTRAP remain owned by the JIT guard. */
}
