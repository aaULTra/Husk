/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Private partial-v2 state hashing; included after number()/bytes(). This is
 * diagnostic grouping, not a complete Vulkan compatibility/cache/replay key. */
typedef struct {uint32_t type;const void *next;uint32_t flags;} pi_prefix;
typedef struct {uint32_t type;const void *next;uint32_t flags,count;const uint32_t *states;} pi_dynamic;
typedef struct {uint32_t type;const void *next;uint32_t flags,bindings;const uint32_t *binding_data;uint32_t attributes;const uint32_t *attribute_data;} pi_vertex;
typedef struct {uint32_t type;const void *next;uint32_t flags,topology,restart;} pi_assembly;
typedef struct {uint32_t type;const void *next;uint32_t flags,points;} pi_tess;
typedef struct {uint32_t type;const void *next;uint32_t flags,clamp,discard,polygon,cull,front,bias;float constant,clamp_factor,slope,line;} pi_raster;
typedef struct {uint32_t type;const void *next;uint32_t flags,samples,shading;float minimum;const uint32_t *mask;uint32_t coverage,one;} pi_multi;
typedef struct {uint32_t type;const void *next;uint32_t flags,test,write,compare,bounds,stencil,front[7],back[7];float minimum,maximum;} pi_depth;
typedef struct {uint32_t type;const void *next;uint32_t flags,logic,op,count;const uint32_t *attachments;float constants[4];} pi_blend;
typedef struct {uint32_t type;const void *next;uint32_t flags,viewports;const float *viewport_data;uint32_t scissors;const uint32_t *scissor_data;} pi_viewport;
_Static_assert(sizeof(pi_vertex)==48&&sizeof(pi_dynamic)==32&&sizeof(pi_assembly)==32&&sizeof(pi_tess)==24&&sizeof(pi_raster)==64&&sizeof(pi_multi)==48&&sizeof(pi_depth)==104&&sizeof(pi_blend)==56&&sizeof(pi_viewport)==48,"Vulkan fixed state ABI");
static uint64_t pi_float(uint64_t h,float value){uint32_t word;memcpy(&word,&value,4);return number(h,word);}
static bool pi_state(uint64_t *h,const void *raw,uint32_t type,unsigned *known){
 *h=number(*h,raw!=NULL);if(!raw)return false;
 const pi_prefix *p=raw;if(p->type!=type){*known=0;return false;}
 *h=number(*h,p->flags);if(p->next)*known=0;return true;
}
static uint64_t fixed_state(uint64_t h,const tl_pi_graphics *p,unsigned *known){
 /* Unknown top-level extensions (e.g. pipeline libraries) change which nested
  * pointers are meaningful. Read only feedback nodes; keep other state unknown. */
 const pi_prefix *chain=p->next;unsigned nodes=0;
 while(chain&&nodes++<32){if(chain->type!=1000192000u){*known=0;return h;}chain=chain->next;}
 if(chain){*known=0;return h;}
 uint32_t dynamic=0;bool unknown_dynamic=false;
 if(pi_state(&h,p->dynamic,27,known)){
  const pi_dynamic *d=p->dynamic;
  h=number(h,d->count);
  if(d->count>128||(d->count&&!d->states)){*known=0;return h;}
  for(unsigned i=0;i<d->count;i++){h=number(h,d->states[i]);if(d->states[i]<9)dynamic|=1u<<d->states[i];else unknown_dynamic=true;}
 }
 /* Extended dynamic state can make otherwise ignored pointers invalid to read.
  * Keep a partial shader group instead of guessing those extension semantics. */
 if(unknown_dynamic){*known=0;return h;}
 bool mesh=false,tess=false;
 if(p->count<=16&&p->stages)for(unsigned i=0;i<p->count;i++){mesh|=!!(p->stages[i].stage&0xc0);tess|=!!(p->stages[i].stage&6);}
 if(!mesh&&pi_state(&h,p->vertex,19,known)){
  const pi_vertex *v=p->vertex;h=number(number(h,v->bindings),v->attributes);
  if(v->bindings>128||v->attributes>128||(v->bindings&&!v->binding_data)||(v->attributes&&!v->attribute_data))*known=0;
  else{for(unsigned i=0;i<v->bindings*3;i++)h=number(h,v->binding_data[i]);for(unsigned i=0;i<v->attributes*4;i++)h=number(h,v->attribute_data[i]);}
 }
 if(!mesh&&pi_state(&h,p->assembly,20,known)){const pi_assembly *v=p->assembly;h=number(number(h,v->topology),v->restart);}
 if(tess&&pi_state(&h,p->tessellation,21,known))h=number(h,((const pi_tess *)p->tessellation)->points);
 bool discard=false;
 if(pi_state(&h,p->raster,23,known)){
  const pi_raster *v=p->raster;discard=v->discard!=0;
  h=number(number(number(number(number(number(h,v->clamp),v->discard),v->polygon),v->cull),v->front),v->bias);
  if(!(dynamic&(1u<<3))&&v->bias){h=pi_float(pi_float(pi_float(h,v->constant),v->clamp_factor),v->slope);}
  if(!(dynamic&(1u<<2)))h=pi_float(h,v->line);
 }
 /* Rasterizer discard ignores viewport, multisample, depth and blend pointers. */
 if(discard)return h;
 if(pi_state(&h,p->viewport,22,known)){
  const pi_viewport *v=p->viewport;h=number(number(h,v->viewports),v->scissors);
  if(v->viewports>16||v->scissors>16){*known=0;return h;}
  if(!(dynamic&1)){if(v->viewports&&!v->viewport_data)*known=0;else for(unsigned i=0;i<v->viewports*6;i++)h=pi_float(h,v->viewport_data[i]);}
  if(!(dynamic&2)){if(v->scissors&&!v->scissor_data)*known=0;else for(unsigned i=0;i<v->scissors*4;i++)h=number(h,v->scissor_data[i]);}
 }
 if(pi_state(&h,p->multisample,24,known)){
  const pi_multi *v=p->multisample;h=number(number(number(number(h,v->samples),v->shading),v->coverage),v->one);
  if(v->shading)h=pi_float(h,v->minimum);
  if(!v->samples||v->samples>64||(v->samples&(v->samples-1)))*known=0;
  else for(unsigned i=0;i<(v->samples+31)/32;i++)h=number(h,v->mask?v->mask[i]:UINT32_MAX);
 }
 if(pi_state(&h,p->depth,25,known)){
  const pi_depth *v=p->depth;h=number(number(number(number(number(h,v->test),v->write),v->compare),v->bounds),v->stencil);
  if(v->stencil)for(unsigned side=0;side<2;side++){const uint32_t *words=side?v->back:v->front;for(unsigned i=0;i<7;i++)if(i<4||!(dynamic&(1u<<(i+2))))h=number(h,words[i]);}
  if(v->bounds&&!(dynamic&(1u<<5)))h=pi_float(pi_float(h,v->minimum),v->maximum);
 }
 if(pi_state(&h,p->blend,26,known)){
  const pi_blend *v=p->blend;h=number(number(number(h,v->logic),v->op),v->count);
  if(v->count>16||(v->count&&!v->attachments))*known=0;else for(unsigned i=0;i<v->count*8;i++)h=number(h,v->attachments[i]);
  if(!(dynamic&(1u<<4)))for(unsigned i=0;i<4;i++)h=pi_float(h,v->constants[i]);
 }
 return h;
}
