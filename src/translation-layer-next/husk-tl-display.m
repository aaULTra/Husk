/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "husk-tl-display.h"
#include <dlfcn.h>
#include <pthread.h>
#include <string.h>
#import <QuartzCore/QuartzCore.h>
_Static_assert(sizeof(tl_display_config)==24 && sizeof(tl_display_record)==56 && sizeof(tl_display_stats)==4232,"native display ABI1 LP64");
static pthread_mutex_t display_api_lock=PTHREAD_MUTEX_INITIALIZER;
static int (*configure_display)(const tl_display_config*);
static int (*snapshot_display)(tl_display_stats*,tl_display_record*,uint32_t);
static bool display_requested,display_excluded=true;
static void apply_display(void){
 if(configure_display){tl_display_config c={1,sizeof(c),display_requested,display_excluded,(uint64_t)(CACurrentMediaTime()*1e9)};configure_display(&c);}
}
void tl_vk_display_driver(void *library){
 pthread_mutex_lock(&display_api_lock);
 configure_display=library?(int(*)(const tl_display_config*))dlsym(library,"vkHuskDisplayConfigure"):NULL;
 snapshot_display=library?(int(*)(tl_display_stats*,tl_display_record*,uint32_t))dlsym(library,"vkHuskDisplaySnapshot"):NULL;
 apply_display();pthread_mutex_unlock(&display_api_lock);
}
void tl_vk_display_monitor(bool enabled){pthread_mutex_lock(&display_api_lock);display_requested=enabled;display_excluded=true;apply_display();pthread_mutex_unlock(&display_api_lock);}
void tl_vk_display_exclude(bool excluded){pthread_mutex_lock(&display_api_lock);if(display_excluded!=excluded){display_excluded=excluded;apply_display();}pthread_mutex_unlock(&display_api_lock);}
bool tl_vk_display_snapshot(tl_display_stats *out,tl_display_record *rows,uint32_t capacity,uint32_t *copied){
 if(!out||!copied||capacity>TL_DISPLAY_CAPACITY||(capacity&&!rows))return false;
 memset(out,0,sizeof(*out));out->version=1;out->size=sizeof(*out);*copied=0;
 pthread_mutex_lock(&display_api_lock);int n=snapshot_display?snapshot_display(out,rows,capacity):-1;pthread_mutex_unlock(&display_api_lock);
 if(n<0||(uint32_t)n>capacity)return false;
 *copied=(uint32_t)n;return true;
}
