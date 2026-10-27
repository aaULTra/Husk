/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_VULKAN_ROUTING_H
#define HUSK_TL_VULKAN_ROUTING_H
#include <stdbool.h>
#include <pthread.h>
#include <string.h>
/* Proc lookup is outside drawing. Only a successfully created, known device
 * may bypass DXVK's null-vertex-buffer compatibility adapter. Unknown/global
 * lookup and capacity overflow keep the original adapter. */
static pthread_mutex_t tl_vk_route_lock=PTHREAD_MUTEX_INITIALIZER;
static struct {void *device;bool compatibility;} tl_vk_routes[8];
static inline void tl_vk_route_device(void *device,bool compatibility){
 if(!device)return;
 pthread_mutex_lock(&tl_vk_route_lock);
 int slot=-1;
 for(unsigned i=0;i<8;i++){
  if(tl_vk_routes[i].device==device){slot=(int)i;break;}
  if(!tl_vk_routes[i].device&&slot<0)slot=(int)i;
 }
 if(slot>=0){tl_vk_routes[slot].device=device;tl_vk_routes[slot].compatibility=compatibility;}
 pthread_mutex_unlock(&tl_vk_route_lock);
}
static inline void tl_vk_route_forget(void *device){
 pthread_mutex_lock(&tl_vk_route_lock);
 for(unsigned i=0;i<8;i++)if(tl_vk_routes[i].device==device)tl_vk_routes[i].device=NULL;
 pthread_mutex_unlock(&tl_vk_route_lock);
}
static inline bool tl_vk_route_direct_vertex(void *device,const char *name){
 if(!device||!name||(strcmp(name,"vkCmdBindVertexBuffers")&&strcmp(name,"vkCmdBindVertexBuffers2")&&strcmp(name,"vkCmdBindVertexBuffers2EXT")))return false;
 bool direct=false;
 pthread_mutex_lock(&tl_vk_route_lock);
 for(unsigned i=0;i<8;i++)if(tl_vk_routes[i].device==device){direct=!tl_vk_routes[i].compatibility;break;}
 pthread_mutex_unlock(&tl_vk_route_lock);return direct;
}
#endif
