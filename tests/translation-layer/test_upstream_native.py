#!/usr/bin/env python3
"""Actual adapted JNI lookup/registration and libUE4 math binding regressions."""
from pathlib import Path
import subprocess,tempfile,unittest,re
ROOT=Path(__file__).resolve().parents[2];TL=ROOT/'src/translation-layer-next'
class UpstreamNativeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);p=Path(cls.tmp.name)
  jni=(TL/'husk-tl-jni.c').read_text();jni=jni[jni.index('typedef struct { const char *name, *sig; void *fn; } native_method;'):jni.index('void dvm_monitor_enter')]
  dvm=(TL/'husk-tl-dvm.c').read_text();dvm=dvm[dvm.index('static void mangle('):dvm.index('/* A call into a JNI function')]
  math=(TL/'husk-tl-bionic-str.c').read_text();methods='\n'.join(re.findall(r'^static int (?:b_isnan|b___isnanf)\([^\n]+',math,re.M))
  entries=[]
  for name in ['isnan','__isnan','isnanf','__isnanf']:
   match=re.search(r'TL_WRAP\("'+name+r'",\s*(\w+)\)',math);assert match,name
   entries.append('{"'+name+'",(void*)'+match.group(1)+'}')
  (p/'main.c').write_text(r'''
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <math.h>
#include "husk-tl-jni-internal.h"
typedef jobj *jo;
static pthread_mutex_t g_lock=PTHREAD_MUTEX_INITIALIZER;
static tl_jclass cls={.name="Example"};
tl_jclass *tl_jni_class(const char *name){assert(!strcmp(name,cls.name));return &cls;}
bool tl_dvm_declares(tl_jclass *c,const char *name,const char *sig){(void)c;(void)name;(void)sig;return true;}
#define TRACE(...) ((void)0)
static unsigned symbol_queries;static void *exported;
static void *tl_ld_sym(void *library,const char *name){(void)library;(void)name;symbol_queries++;return exported;}
typedef struct{tl_jclass *cls;const char *name,*sig;void *jni;bool jni_looked;unsigned jni_gen;}dvm_method;
'''+jni+dvm+methods+'\nstatic struct{const char*name;void*fn;}math_entries[]={'+','.join(entries)+r'''};
static int first(void){return 1;}static int second(void){return 2;}
int main(int argc,char**argv){assert(argc==2);jobj object={.kind=TL_K_CLASS};object.klass.jc=&cls;dvm_method m={.cls=&cls,.name="run",.sig="()I"};
 if(!strcmp(argv[1],"late")){
  assert(!find_jni(&m));native_method methods[]={ {"run","()I",(void*)first} };unsigned old=tl_jni_natives_generation();assert(!jni_RegisterNatives(NULL,&object,methods,1));assert(tl_jni_natives_generation()!=old);assert(find_jni(&m)==(void*)first);
 }else if(!strcmp(argv[1],"replace")){
  native_method methods[]={ {"run","()I",(void*)first} };assert(!jni_RegisterNatives(NULL,&object,methods,1));assert(find_jni(&m)==(void*)first);methods[0].fn=(void*)second;assert(!jni_RegisterNatives(NULL,&object,methods,1));assert(find_jni(&m)==(void*)second);
 }else if(!strcmp(argv[1],"hit")){
  exported=(void*)first;assert(find_jni(&m)==exported);unsigned before=symbol_queries;assert(find_jni(&m)==exported&&symbol_queries==before);
 }else if(!strcmp(argv[1],"new-export")){
  assert(!find_jni(&m));exported=(void*)second;assert(find_jni(&m)==exported);
 }else if(!strcmp(argv[1],"invalid")){
  native_method methods[]={ {"run","()I",(void*)first} };unsigned before=tl_jni_natives_generation();assert(jni_RegisterNatives(NULL,NULL,methods,1)==-1&&tl_jni_natives_generation()==before);assert(jni_UnregisterNatives(NULL,NULL)==0);
 }else if(!strcmp(argv[1],"math")){
  for(unsigned i=0;i<4;i++){
   if(i<2){int(*f)(double)=math_entries[i].fn;assert(f(NAN)&&f(-NAN)&&!f(INFINITY)&&!f(-INFINITY)&&!f(0.0)&&!f(-0.0)&&!f(1e-300));}
   else{int(*f)(float)=math_entries[i].fn;assert(f(NAN)&&!f(INFINITY)&&!f(0.f)&&!f(-0.f));}
  }
 }else assert(0);
 for(int i=0;i<cls.nnatives;i++){free(cls.natives[i].name);free(cls.natives[i].sig);}free(cls.natives);
 return 0;
}
''')
  cls.exe=p/'check';subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-pthread','-I',str(TL),str(p/'main.c'),'-lm','-o',str(cls.exe)],check=True)
 def case(self,name):subprocess.run([str(self.exe),name],check=True)
 def test_first_miss_does_not_hide_later_registered_native(self):self.case('late')
 def test_later_registration_replaces_cached_function(self):self.case('replace')
 def test_unchanged_successful_lookup_keeps_fast_cache(self):self.case('hit')
 def test_miss_is_retried_after_library_symbols_become_available(self):self.case('new-export')
 def test_failed_registration_does_not_publish_generation(self):self.case('invalid')
 def test_actual_symbol_bindings_classify_double_float_nan_and_finite_values(self):self.case('math')
if __name__=='__main__':unittest.main()
