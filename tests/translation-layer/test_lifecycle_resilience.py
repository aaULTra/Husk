#!/usr/bin/env python3
"""Real mailbox/owner delivery, crash-handler subprocess and Swift policy regressions."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TL = ROOT / 'src/translation-layer-next'
APP = ROOT / 'src/app/Husk'

def function(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    level = 1
    end = opening + 1
    while level:
        level += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]

class NativeTests(unittest.TestCase):
    def run_c(self, source, modules):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p/'test.c').write_text(source)
            subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(TL),str(p/'test.c'),
                            *[str(TL/x) for x in modules],'-pthread','-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True,timeout=15)

    def test_mailbox_startup_latest_state_owner_ack_timeout_and_concurrent_requests(self):
        self.run_c(r'''
#define _POSIX_C_SOURCE 200809L
#include "husk-tl-lifecycle.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <time.h>
static atomic_int wakes;
static void wake(void *p){assert(p==(void*)1);atomic_fetch_add(&wakes,1);tl_lifecycle_stats s;tl_lifecycle_snapshot(&s);}
static void *requests(void *p){(void)p;bool b;uint64_t q;assert(!tl_lifecycle_next(&b,&q));tl_lifecycle_complete(true,1);for(int i=0;i<10000;i++)tl_lifecycle_request(i%2);tl_lifecycle_request(true);return 0;}
static void *timeout(void *p){(void)p;assert(!tl_lifecycle_wait_paused(20));return 0;}
int main(void){
 bool b;uint64_t q;tl_lifecycle_stats s;pthread_t t;
 tl_lifecycle_request(true);assert(!tl_lifecycle_next(&b,&q));
 tl_lifecycle_bind(wake,(void*)1);tl_lifecycle_ready(false);
 assert(tl_lifecycle_next(&b,&q)&&b&&q==1);assert(!tl_lifecycle_next(&b,&q));
 assert(!tl_lifecycle_wait_paused(5000)); // owner never waits for its own callback
 assert(!pthread_create(&t,0,timeout,0));pthread_join(t,0);
 tl_lifecycle_complete(false,q);tl_lifecycle_snapshot(&s);assert(s.applying&&!s.applied_paused); // bad ticket
 assert(!pthread_create(&t,0,requests,0));pthread_join(t,0); // producer responsive while owner callback outstanding
 tl_lifecycle_snapshot(&s);assert(s.applying&&s.applied_sequence==0);
 tl_lifecycle_complete(true,q);assert(tl_lifecycle_wait_paused(0));
 assert(!tl_lifecycle_next(&b,&q));tl_lifecycle_snapshot(&s);assert(s.applied_sequence==s.requested_sequence&&s.transitions==1&&s.requests==10002);
 tl_lifecycle_request(false);tl_lifecycle_request(true);assert(!tl_lifecycle_next(&b,&q)); // transient pair coalesced
 tl_lifecycle_request(false);assert(tl_lifecycle_next(&b,&q)&&!b);tl_lifecycle_complete(b,q);
 assert(!tl_lifecycle_wait_paused(100));tl_lifecycle_snapshot(&s);assert(s.transitions==2&&s.duplicates>0&&wakes>0);
 return 0;
}
''',['husk-tl-lifecycle.c'])

    def test_actual_activity_delivery_is_serial_on_owner_and_runs_callbacks_without_mailbox_lock(self):
        delivery=function((TL/'husk-tl-nativeactivity.c').read_text(),'static void deliver_lifecycle(void)')
        self.run_c(r'''
#include "husk-tl-lifecycle.h"
#include <assert.h>
#include <pthread.h>
#include <stdarg.h>
static pthread_t owner;static int phase,checkpoints,audio;
static struct {int na;struct {void(*onPause)(int*);void(*onResume)(int*);void(*onWindowFocusChanged)(int*,int);}callbacks;}N;
static void tl_log_line(const char *s,...){(void)s;}
static void tl_thread_policy_suspend(void){assert(pthread_equal(owner,pthread_self()));}
static void tl_pc_checkpoint_async(void){checkpoints++;}
static void tl_audio_set_paused(bool b){assert((b&&phase==2)||(!b&&phase==4));audio++;}
static void focus(int*n,int f){assert(n==&N.na);phase=f?4:1;}
static void pause_(int*n){assert(n==&N.na&&phase==1);phase=2;tl_lifecycle_request(false);} // reentrant producer, no lock held
static void resume_(int*n){assert(n==&N.na&&phase==2);phase=3;}
/* DELIVERY */
static void *foreign(void*p){(void)p;deliver_lifecycle();assert(phase==0);return 0;}
int main(void){owner=pthread_self();N.callbacks.onPause=pause_;N.callbacks.onResume=resume_;N.callbacks.onWindowFocusChanged=focus;
 tl_lifecycle_bind(0,0);tl_lifecycle_ready(false);tl_lifecycle_request(true);
 pthread_t t;assert(!pthread_create(&t,0,foreign,0));pthread_join(t,0);deliver_lifecycle();
 tl_lifecycle_stats s;tl_lifecycle_snapshot(&s);assert(phase==4&&audio==2&&checkpoints==1&&s.transitions==2&&!s.applied_paused&&!s.applying);return 0;}
'''.replace('/* DELIVERY */',delivery),['husk-tl-lifecycle.c'])

    def test_fatal_signal_records_re_raises_and_preserves_jit_guards(self):
        self.run_c(r'''
#define _POSIX_C_SOURCE 200809L
#include "husk-tl-crash-signal.h"
#include <assert.h>
#include <signal.h>
#include <string.h>
#include <stdio.h>
#include <sys/wait.h>
#include <unistd.h>
static void guard_(int s){(void)s;}
int main(void){
 struct sigaction a={0},b;a.sa_handler=guard_;sigemptyset(&a.sa_mask);
 sigaction(SIGBUS,&a,0);sigaction(SIGTRAP,&a,0);sigaction(SIGPIPE,&a,0);
 FILE *f=tmpfile();assert(f);int fd=fileno(f);
 assert(husk_crash_install(fd,fd)==5);sigaction(SIGBUS,0,&b);assert(b.sa_handler==guard_);
 sigaction(SIGTRAP,0,&b);assert(b.sa_handler==guard_);sigaction(SIGPIPE,0,&b);assert(b.sa_handler==guard_);
 for(int i=0;i<100;i++)husk_crash_note_image("libUE4.so",100,100,200); // registry stays bounded
 pid_t p=fork();assert(p>=0);if(!p){husk_crash_native_sink(fd);raise(SIGABRT);_exit(99);}
 int status;assert(waitpid(p,&status,0)==p&&WIFSIGNALED(status)&&WTERMSIG(status)==SIGABRT);
 rewind(f);char data[4096];size_t n=fread(data,1,sizeof(data)-1,f);data[n]=0;
 assert(strstr(data,"*** FATAL SIGNAL 6 -- process terminating ***"));
 assert(!strstr(strstr(data,"*** FATAL SIGNAL")+4,"*** FATAL SIGNAL")); // same fd written only once
 p=fork();assert(p>=0);if(!p){husk_crash_install(-1,-1);husk_crash_native_sink(-1);raise(SIGILL);_exit(98);}
 assert(waitpid(p,&status,0)==p&&WIFSIGNALED(status)&&WTERMSIG(status)==SIGILL);fclose(f);return 0;
}
''',['husk-tl-crash-signal.c'])

@unittest.skipUnless(shutil.which('swiftc'),'Swift unavailable; required Apple IPA CI executes actual Swift policy')
class SwiftTests(unittest.TestCase):
    def test_visibility_marker_and_actual_log_classifier(self):
        # Use the complete actual Foundation-only classifier methods, excluding UIKit screens and APK preflight.
        s=(APP/'AppDiagnosis.swift').read_text()
        head=s[s.index('struct AppDiagnosis:'):s.index('    var symbol:')]
        methods=s[s.index('    static func fromLog('):s.index('\n/// ',s.index('    private static func apiName('))]
        # The struct closes immediately before the first view doc comment.
        fixture='import Foundation\n'+head+methods
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'Diagnosis.swift').write_text(fixture)
            (p/'main.swift').write_text(r'''
import Foundation
var policy = NativeGameLifecycle()
precondition(policy.update(attached: true, appActive: true, sceneActive: true) == false)
precondition(policy.update(attached: true, appActive: true, sceneActive: true) == nil)
for a in [false,true] { for b in [false,true] { for c in [false,true] {
 precondition(policy.update(attached:a,appActive:b,sceneActive:c,force:true) == !(a && b && c))
}}}
var session = RunningGameSession(id:"game",label:"Dungeons",build:"source",time:100)
let identity = session.session
for i in 0..<100 { session.note("event \(i)",time:Double(i+101)) }
session.note("ignored",time:.nan)
precondition(session.events.count==32 && session.time==100 && session.session==identity && session.lastState=="event 99")
session.note(String(repeating:"x",count:500),time:201);precondition(session.lastState.count==120)
let json = try JSONSerialization.jsonObject(with: JSONEncoder().encode(session)) as! [String:Any]
precondition(json["schema"] as? Int == 2 && json["build"] as? String == "source")
let patch = "husk: the app's expansion file (OBB) is missing: /path/patch.42.game.obb"
let main = "husk: the app's expansion file (OBB) is missing: /path/main.42.game.obb"
precondition(AppDiagnosis.fromLog(patch)==nil)
precondition(AppDiagnosis.fromLog(main)==nil)
precondition(AppDiagnosis.fromLog(main+"\n the game could not be started")?.title=="Missing game data")
precondition(AppDiagnosis.fromLog(main+"\n the game could not be started\nunity: alive: 33801 frames (+175)")==nil)
precondition(AppDiagnosis.fromLog(patch+"\nunity: alive: 33801 frames (+175)\nue4: pausing")==nil)
precondition(AppDiagnosis.fromLog("[2ms][prev] *** FATAL SIGNAL 11")==nil)
let fatal=patch+"\n*** FATAL SIGNAL 6 -- process terminating ***"
precondition(AppDiagnosis.fromLog(fatal)?.kind == .nativeCrash)
precondition(RuntimeLogEvidence.fatalSignal(RuntimeLogEvidence.currentLines(fatal)) == 6)
precondition(RuntimeLogEvidence.fatalSignal(["=== FATAL signal 11"]) == 11)
precondition(RuntimeLogEvidence.fatalSignal(["=== CRASH: signal 999"]) == nil)
''')
            subprocess.run(['swiftc',str(APP/'NativeGameLifecycle.swift'),str(APP/'RuntimeLogEvidence.swift'),str(p/'Diagnosis.swift'),str(p/'main.swift'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True,timeout=15)

    def test_touch_coordinates_fixed_target_resizing_offsets_and_invalid_geometry(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'main.swift').write_text(r'''import Foundation
import CoreGraphics
let output=CGSize(width:2128,height:1600)
for bounds in [CGRect(x:0,y:0,width:1376,height:1032), CGRect(x:5,y:9,width:688,height:516), CGRect(x:0,y:0,width:1000,height:700)] {
 let centre=CGPoint(x:bounds.midX,y:bounds.midY)
 let p=NativeTouchCoordinates.map(centre,bounds:bounds,surface:output)!
 precondition(p.x==1064 && p.y==800)
 let edge=NativeTouchCoordinates.map(CGPoint(x:bounds.maxX,y:bounds.maxY),bounds:bounds,surface:output)!
 precondition(edge.x==2128 && edge.y==1600)
}
let b=CGRect(x:0,y:0,width:100,height:100)
precondition(NativeTouchCoordinates.map(CGPoint(x:-10,y:120),bounds:b,surface:output)!.x < 0)
precondition(NativeTouchCoordinates.map(.zero,bounds:.zero,surface:output)==nil)
precondition(NativeTouchCoordinates.map(CGPoint(x:CGFloat.infinity,y:0),bounds:b,surface:output)==nil)
precondition(NativeTouchCoordinates.map(.zero,bounds:b,surface:CGSize(width:CGFloat.nan,height:1))==nil)
''')
            subprocess.run(['swiftc',str(APP/'NativeTouchCoordinates.swift'),str(p/'main.swift'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True,timeout=15)

    def test_actual_touch_adapter_cancels_every_pointer_and_ignores_late_events(self):
        source = (APP/'TLUnityView.swift').read_text()
        methods = '\n'.join(function(source, x) for x in ['private func id(for touch:', 'private func send(', 'private func cancelActiveTouches()'])
        harness = r'''import Foundation
import CoreGraphics
var events: [(Int32,Int32,Float,Float)] = []
func husk_unity_touch(_ phase:Int32,_ id:Int32,_ x:Float,_ y:Float){events.append((phase,id,x,y))}
func tl_vk_spatial_touch(_ x:inout Float,_ y:inout Float){x *= 0.8;y *= 0.8}
final class UITouch: Hashable {
 let point:CGPoint
 init(_ x:Double,_ y:Double){point=CGPoint(x:x,y:y)}
 func location(in view:Adapter)->CGPoint {point}
 static func ==(a:UITouch,b:UITouch)->Bool{a === b}
 func hash(into h:inout Hasher){h.combine(ObjectIdentifier(self))}
}
enum Engine { case ue4, unity }
class Adapter {
 var pointers:[ObjectIdentifier:Int32]=[:]
 var pointerPositions:[Int32:CGPoint]=[:]
 var engine:Engine = .ue4
 var contentScaleFactor:CGFloat = 2
 var bounds=CGRect(x:0,y:0,width:100,height:100)
 var touchSurfaceSize=CGSize(width:200,height:200)
 /* METHODS */
 func sendEvent(_ touches:Set<UITouch>,_ phase:Int32){send(touches,phase:phase)}
 func cancel(){cancelActiveTouches()}
}
let a=Adapter(),one=UITouch(10,20),two=UITouch(30,40)
a.sendEvent([one,two],0);precondition(events.count==2 && a.pointers.count==2)
a.cancel();precondition(events.count==3 && events.last!.0==3 && a.pointers.isEmpty && a.pointerPositions.isEmpty)
a.sendEvent([one,two],1);a.sendEvent([one,two],2);precondition(events.count==3)
a.cancel();precondition(events.count==3)
a.engine = .unity;a.sendEvent([one,two],0);a.cancel()
precondition(events.count==7 && events.suffix(2).allSatisfy{$0.0==2})
precondition(Set(events.suffix(2).map{$0.1}) == [0,1])
a.sendEvent([one],0);precondition(events.last!.1==0);a.sendEvent([one],2);precondition(a.pointers.isEmpty)
'''.replace('/* METHODS */',methods)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'main.swift').write_text(harness)
            subprocess.run(['swiftc',str(APP/'NativeTouchCoordinates.swift'),str(p/'main.swift'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True,timeout=15)

if __name__=='__main__': unittest.main()
