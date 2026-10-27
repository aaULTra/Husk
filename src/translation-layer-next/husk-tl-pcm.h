/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_PCM_H
#define HUSK_TL_PCM_H
#include <stddef.h>
#include <stdint.h>
#include <string.h>
/* Callers hold the ring lock. At most two contiguous copies, no per-frame
 * division/modulo, allocation or format conversion in the output callback. */
static inline void tl_pcm_ring_read(int16_t *out,const int16_t *ring,size_t head,size_t frames,size_t capacity,size_t channels){
 if(!frames)return;
 size_t first=capacity-head;if(first>frames)first=frames;
 memcpy(out,ring+head*channels,first*channels*sizeof(*out));
 if(frames>first)memcpy(out+first*channels,ring,(frames-first)*channels*sizeof(*out));
}
static inline void tl_pcm_ring_write(int16_t *ring,size_t tail,const int16_t *input,size_t frames,size_t capacity,size_t channels){
 if(!frames)return;
 size_t first=capacity-tail;if(first>frames)first=frames;
 memcpy(ring+tail*channels,input,first*channels*sizeof(*input));
 if(frames>first)memcpy(ring,input+first*channels,(frames-first)*channels*sizeof(*input));
}
/* Same linear2x sequence as the previous implementation. Chunk boundaries carry
 * the last frame, and source-format changes reset only interpolation history. */
static inline void tl_pcm_double(int16_t *out,const int16_t *input,size_t frames,unsigned channels,int16_t previous[2],int have_previous){
 for(size_t f=0;f<frames;f++)for(unsigned c=0;c<channels;c++){
  int16_t current=input[f*channels+c];
  int16_t before=f?input[(f-1)*channels+c]:(have_previous?previous[c]:current);
  out[(2*f)*channels+c]=(int16_t)(((int)before+current)/2);
  out[(2*f+1)*channels+c]=current;
 }
 if(frames)for(unsigned c=0;c<channels;c++)previous[c]=input[(frames-1)*channels+c];
}
#endif
