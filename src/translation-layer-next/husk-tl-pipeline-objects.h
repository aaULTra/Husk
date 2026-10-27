/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Included inside the M2 observer after the hash helpers. Field-wise LP64 core
 * Vulkan descriptions, never raw object pointers/padding or serialisable replay.
 * Unknown extensions/flags and bounded-out data remain explicitly incomplete. */
#define PI_OBJECTS 4096
static struct pi_object_record {void *device;uint64_t handle,key;unsigned kind,complete,state;} pi_objects[PI_OBJECTS];
typedef struct {uint32_t type;const void *next;uint32_t flags,mag,min,mipmap,u,v,w;float bias;uint32_t anisotropy;float max_anisotropy;uint32_t compare,op;float min_lod,max_lod;uint32_t border,unnormalized;} pi_sampler;
typedef struct {uint32_t binding,type,count,stages;const uint64_t *samplers;} pi_binding;
typedef struct {uint32_t type;const void *next;uint32_t flags,count;const pi_binding *bindings;} pi_descriptor_layout;
typedef struct {uint32_t stages,offset,size;} pi_push;
typedef struct {uint32_t type;const void *next;uint32_t flags,sets;const uint64_t *layouts;uint32_t pushes;const pi_push *ranges;} pi_pipeline_layout;
typedef struct {uint32_t attachment,layout;} pi_attachment_ref;
typedef struct {uint32_t flags,bind_point,inputs;const pi_attachment_ref *input;uint32_t colors;const pi_attachment_ref *color,*resolve,*depth;uint32_t preserves;const uint32_t *preserve;} pi_subpass;
typedef struct {uint32_t type;const void *next;uint32_t flags,attachments;const uint32_t *attachment_data;uint32_t subpasses;const pi_subpass *subpass_data;uint32_t dependencies;const uint32_t *dependency_data;} pi_render_pass;
typedef struct {uint32_t type;const void *next;uint32_t view_mask,colors;const uint32_t *formats;uint32_t depth,stencil;} pi_rendering;
_Static_assert(sizeof(pi_sampler)==80&&sizeof(pi_binding)==24&&sizeof(pi_descriptor_layout)==32&&sizeof(pi_pipeline_layout)==48&&sizeof(pi_subpass)==72&&sizeof(pi_render_pass)==64&&sizeof(pi_rendering)==40,"Core Vulkan object LP64 ABI");
/* Pointer/handle bits choose lookup buckets only; semantic keys never contain them. */
static unsigned pi_bucket(unsigned kind,void *device,uint64_t handle){
 uint64_t x=(uint64_t)(uintptr_t)device^handle^(uint64_t)kind*0x9e3779b97f4a7c15ULL;
 x^=x>>33;x*=0xff51afd7ed558ccdULL;x^=x>>33;return (unsigned)x&(PI_OBJECTS-1);
}
static struct pi_object_record *pi_find_object(unsigned kind,void *device,uint64_t handle){
 unsigned start=pi_bucket(kind,device,handle);
 for(unsigned n=0;n<PI_OBJECTS;n++){
  struct pi_object_record *o=pi_objects+((start+n)&(PI_OBJECTS-1));
  if(!o->state)return NULL;
  if(o->state==1&&o->device==device&&o->handle==handle&&o->kind==kind)return o;
 }return NULL;
}
static void pi_forget_objects(void *device){for(unsigned i=0;i<PI_OBJECTS;i++)if(pi_objects[i].state==1&&pi_objects[i].device==device)pi_objects[i].state=2;}
static void pi_store_object(unsigned kind,void *device,uint64_t handle,uint64_t key,unsigned complete){
 struct pi_object_record *slot=NULL;unsigned start=pi_bucket(kind,device,handle);
 for(unsigned n=0;n<PI_OBJECTS;n++){
  struct pi_object_record *o=pi_objects+((start+n)&(PI_OBJECTS-1));
  if(o->state==1&&o->device==device&&o->handle==handle&&o->kind==kind){slot=o;break;}
  if(o->state!=1&&!slot)slot=o;
  if(!o->state)break;
 }
 if(slot)*slot=(struct pi_object_record){device,handle,key,kind,complete,1};else atomic_fetch_add(&drops,1);
}
static uint64_t pi_reference(uint64_t h,unsigned kind,void *device,uint64_t handle,unsigned *complete){
 struct pi_object_record *o=handle?pi_find_object(kind,device,handle):NULL;
 if(!o){*complete=0;return number(number(h,kind),0);}
 if(!o->complete)*complete=0;
 return number(number(h,kind),o->key);
}
static uint64_t pi_ref(uint64_t h,const pi_attachment_ref *ref){
 h=number(h,ref->attachment);return ref->attachment==UINT32_MAX?h:number(h,ref->layout);
}
/* Vulkan1.2/KHR render-pass core descriptions, field-wise and bounded. */
typedef struct {uint32_t type;const void *next;uint32_t flags,format,samples,load,store,stencil_load,stencil_store,initial_layout,final_layout;} pi_attachment2;
typedef struct {uint32_t type;const void *next;uint32_t attachment,layout,aspects;} pi_ref2;
typedef struct {uint32_t type;const void *next;uint32_t flags,bind_point,view_mask,inputs;const pi_ref2 *input;uint32_t colors;const pi_ref2 *color,*resolve,*depth;uint32_t preserves;const uint32_t *preserve;} pi_subpass2;
typedef struct {uint32_t type;const void *next;uint32_t src,dst,src_stages,dst_stages,src_access,dst_access,flags;int32_t view_offset;} pi_dependency2;
typedef struct {uint32_t type;const void *next;uint32_t flags,attachments;const pi_attachment2 *attachment_data;uint32_t subpasses;const pi_subpass2 *subpass_data;uint32_t dependencies;const pi_dependency2 *dependency_data;uint32_t correlated;const uint32_t *masks;} pi_render_pass2;
_Static_assert(sizeof(pi_attachment2)==56&&sizeof(pi_ref2)==32&&sizeof(pi_subpass2)==88&&sizeof(pi_dependency2)==48&&sizeof(pi_render_pass2)==80,"Vulkan render-pass2 LP64 ABI");
static uint64_t pi_rp2_ref(uint64_t h,const pi_ref2 *r,unsigned *complete){
 if(r->type!=1000109001u){*complete=0;return number(h,0);}
 h=number(h,r->attachment);if(r->attachment==UINT32_MAX)return h;
 if(r->next)*complete=0;
 return number(number(h,r->layout),r->aspects);
}
static uint64_t pi_rp2_key(uint64_t h,const pi_render_pass2 *r,unsigned *complete){
 h=number(number(number(number(number(h,r->type),r->attachments),r->subpasses),r->dependencies),r->correlated);
 if(r->next||r->flags||r->attachments>128||r->subpasses>64||r->dependencies>256||r->correlated>64||
    (r->attachments&&!r->attachment_data)||(r->subpasses&&!r->subpass_data)||(r->dependencies&&!r->dependency_data)||(r->correlated&&!r->masks)){*complete=0;return h;}
 for(unsigned i=0;i<r->attachments;i++){
  const pi_attachment2 *a=r->attachment_data+i;
  if(a->type!=1000109000u||a->next||(a->flags&~1u))*complete=0;
  h=number(number(number(number(number(number(number(number(number(h,a->flags),a->format),a->samples),a->load),a->store),a->stencil_load),a->stencil_store),a->initial_layout),a->final_layout);
 }
 unsigned budget=2048;
 for(unsigned i=0;i<r->subpasses;i++){
  const pi_subpass2 *s=r->subpass_data+i;
  h=number(number(number(number(number(number(h,s->flags),s->bind_point),s->view_mask),s->inputs),s->colors),s->preserves);
  if(s->type!=1000109002u||s->next||s->flags||s->bind_point||s->inputs>128||s->colors>128||s->preserves>128||
     (s->inputs&&!s->input)||(s->colors&&!s->color)||(s->preserves&&!s->preserve)){*complete=0;continue;}
  unsigned needed=s->inputs+s->colors+(s->resolve?s->colors:0)+(s->depth?1:0);
  if(needed>budget){*complete=0;continue;}budget-=needed;
  for(unsigned j=0;j<s->inputs;j++)h=pi_rp2_ref(h,s->input+j,complete);
  for(unsigned j=0;j<s->colors;j++)h=pi_rp2_ref(h,s->color+j,complete);
  h=number(h,s->resolve!=NULL);if(s->resolve)for(unsigned j=0;j<s->colors;j++)h=pi_rp2_ref(h,s->resolve+j,complete);
  h=number(h,s->depth!=NULL);if(s->depth)h=pi_rp2_ref(h,s->depth,complete);
  for(unsigned j=0;j<s->preserves;j++)h=number(h,s->preserve[j]);
 }
 for(unsigned i=0;i<r->dependencies;i++){
  const pi_dependency2 *d=r->dependency_data+i;
  if(d->type!=1000109003u||d->next)*complete=0;
  h=number(number(number(number(number(number(number(number(h,d->src),d->dst),d->src_stages),d->dst_stages),d->src_access),d->dst_access),d->flags),(uint32_t)d->view_offset);
 }
 for(unsigned i=0;i<r->correlated;i++)h=number(h,r->masks[i]);
 return h;
}
static uint64_t pi_object_key(unsigned kind,void *device,const void *raw,unsigned *complete){
 const pi_prefix *prefix=raw;
 uint64_t h=number(14695981039346656037ULL,kind);
 uint32_t type=kind==TL_PI_SAMPLER?31:kind==TL_PI_DESCRIPTOR_LAYOUT?32:kind==TL_PI_PIPELINE_LAYOUT?30:38;
 if(raw&&kind==TL_PI_RENDER_PASS&&prefix->type==1000109004u)return pi_rp2_key(h,raw,complete);
 if(!raw||prefix->type!=type){*complete=0;return h;}
 h=number(h,prefix->flags);
 if(prefix->next||prefix->flags){*complete=0;return number(h,prefix->type);}
 if(kind==TL_PI_SAMPLER){
  const pi_sampler *s=raw;
  h=number(number(number(number(number(number(h,s->mag),s->min),s->mipmap),s->u),s->v),s->w);
  h=pi_float(h,s->bias);h=number(h,s->anisotropy);if(s->anisotropy)h=pi_float(h,s->max_anisotropy);
  h=number(h,s->compare);if(s->compare)h=number(h,s->op);
  h=pi_float(pi_float(h,s->min_lod),s->max_lod);
  if(s->u==3||s->v==3||s->w==3)h=number(h,s->border);
  return number(h,s->unnormalized);
 }
 if(kind==TL_PI_DESCRIPTOR_LAYOUT){
  const pi_descriptor_layout *d=raw;h=number(h,d->count);
  if(d->count>128||(d->count&&!d->bindings)){*complete=0;return h;}
  unsigned sampler_budget=256;
  unsigned order[128];for(unsigned i=0;i<d->count;i++){order[i]=i;for(unsigned j=i;j&&d->bindings[order[j-1]].binding>d->bindings[order[j]].binding;j--){unsigned t=order[j];order[j]=order[j-1];order[j-1]=t;}}
  for(unsigned i=0;i<d->count;i++){
   const pi_binding *b=d->bindings+order[i];h=number(number(number(number(h,b->binding),b->type),b->count),b->stages);
   if(i&&d->bindings[order[i-1]].binding==b->binding)*complete=0;
   if(b->type>10||b->count>4096){*complete=0;continue;}
   /* Immutable samplers are ignored for non-sampler descriptors. */
   if(b->type<=1){h=number(h,b->samplers!=NULL);if(b->samplers){if(b->count>sampler_budget){*complete=0;continue;}sampler_budget-=b->count;for(unsigned k=0;k<b->count;k++)h=pi_reference(h,TL_PI_SAMPLER,device,b->samplers[k],complete);}}
  }return h;
 }
 if(kind==TL_PI_PIPELINE_LAYOUT){
  const pi_pipeline_layout *l=raw;h=number(number(h,l->sets),l->pushes);
  if(l->sets>32||l->pushes>128||(l->sets&&!l->layouts)||(l->pushes&&!l->ranges)){*complete=0;return h;}
  for(unsigned i=0;i<l->sets;i++)h=pi_reference(h,TL_PI_DESCRIPTOR_LAYOUT,device,l->layouts[i],complete);
  unsigned order[128];for(unsigned i=0;i<l->pushes;i++){order[i]=i;for(unsigned k=i;k;k--){const pi_push *a=l->ranges+order[k-1],*b=l->ranges+order[k];if(a->stages<b->stages||(a->stages==b->stages&&(a->offset<b->offset||(a->offset==b->offset&&a->size<=b->size))))break;unsigned t=order[k];order[k]=order[k-1];order[k-1]=t;}}
  for(unsigned i=0;i<l->pushes;i++){const pi_push *p=l->ranges+order[i];h=number(number(number(h,p->stages),p->offset),p->size);}return h;
 }
 const pi_render_pass *r=raw;h=number(number(number(h,r->attachments),r->subpasses),r->dependencies);
 if(r->attachments>128||r->subpasses>64||r->dependencies>256||(r->attachments&&!r->attachment_data)||(r->subpasses&&!r->subpass_data)||(r->dependencies&&!r->dependency_data)){*complete=0;return h;}
 for(unsigned i=0;i<r->attachments*9;i++)h=number(h,r->attachment_data[i]);
 for(unsigned i=0;i<r->subpasses;i++){
  const pi_subpass *s=r->subpass_data+i;
  h=number(number(number(number(number(h,s->flags),s->bind_point),s->inputs),s->colors),s->preserves);
  if(s->flags||s->bind_point||s->inputs>128||s->colors>128||s->preserves>128||(s->inputs&&!s->input)||(s->colors&&!s->color)||(s->preserves&&!s->preserve)){*complete=0;continue;}
  for(unsigned j=0;j<s->inputs;j++)h=pi_ref(h,s->input+j);
  for(unsigned j=0;j<s->colors;j++)h=pi_ref(h,s->color+j);
  h=number(h,s->resolve!=NULL);if(s->resolve)for(unsigned j=0;j<s->colors;j++)h=pi_ref(h,s->resolve+j);
  h=number(h,s->depth!=NULL);if(s->depth)h=pi_ref(h,s->depth);
  for(unsigned j=0;j<s->preserves;j++)h=number(h,s->preserve[j]);
 }
 for(unsigned i=0;i<r->dependencies*7;i++)h=number(h,r->dependency_data[i]);
 return h;
}
void tl_pi_object(unsigned kind,void *device,uint64_t handle,const void *ci){
 if(!atomic_load(&enabled)||!device||!handle||kind<TL_PI_SAMPLER||kind>TL_PI_RENDER_PASS)return;
 if(pthread_mutex_trylock(&mu)){atomic_fetch_add(&drops,1);return;}
 unsigned complete=1;uint64_t key=pi_object_key(kind,device,ci,&complete);pi_store_object(kind,device,handle,key,complete);pthread_mutex_unlock(&mu);
}
void tl_pi_forget_object(unsigned kind,void *device,uint64_t handle){
 if(!atomic_load(&enabled))return;
 pthread_mutex_lock(&mu);struct pi_object_record *o=pi_find_object(kind,device,handle);if(o)o->state=2;pthread_mutex_unlock(&mu);
}
void tl_pi_pipeline_objects(tl_pi_request request,void *device,const uint64_t *handles){
 if(!atomic_load(&enabled)||!handles||!request.sampled)return;
 if(pthread_mutex_trylock(&mu)){atomic_fetch_add(&drops,1);return;}
 for(unsigned i=0;i<request.sampled;i++)if(handles[i])pi_store_object(TL_PI_PIPELINE,device,handles[i],request.id[i],request.full_core[i]);
 pthread_mutex_unlock(&mu);
}
static uint64_t pi_pipeline_dependencies(uint64_t h,bool compute,void *device,const void *raw,tl_pi_request *r,unsigned index){
 unsigned known=1;uint64_t layout,renderpass=0,base;int32_t base_index;uint32_t flags;
 if(compute){const tl_pi_compute *p=raw;layout=p->layout;base=p->base;base_index=p->base_index;flags=p->flags;}
 else{const tl_pi_graphics *p=raw;layout=p->layout;renderpass=p->renderpass;base=p->base;base_index=p->base_index;flags=p->flags;}
 h=pi_reference(h,TL_PI_PIPELINE_LAYOUT,device,layout,&known);
 if(known)r->coverage[index]|=TL_PI_LAYOUT_STATE;else r->coverage[index]|=TL_PI_MISSING_OBJECT;
 if(!compute){
  known=1;
  if(renderpass)h=pi_reference(h,TL_PI_RENDER_PASS,device,renderpass,&known);
  else{
   const pi_prefix *node=((const tl_pi_graphics*)raw)->next;const pi_rendering *rendering=NULL;
   for(unsigned i=0;node&&i<32;i++,node=node->next)if(node->type==1000044002u){if(rendering){known=0;break;}rendering=(const pi_rendering*)node;}
   if(!rendering||rendering->colors>16||(rendering->colors&&!rendering->formats)){known=0;h=number(h,0);}
   else{h=number(number(number(number(h,rendering->view_mask),rendering->colors),rendering->depth),rendering->stencil);for(unsigned i=0;i<rendering->colors;i++)h=number(h,rendering->formats[i]);}
  }
  if(known)r->coverage[index]|=TL_PI_RENDER_STATE;else r->coverage[index]|=TL_PI_MISSING_OBJECT;
 }
 known=1;
 if(flags&4){
  if(base_index>=0){if((unsigned)base_index<index){h=number(h,r->id[base_index]);known=r->full_core[base_index];}else known=0;}
  else h=pi_reference(h,TL_PI_PIPELINE,device,base,&known);
 }
 if(known)r->coverage[index]|=TL_PI_BASE_STATE;else r->coverage[index]|=TL_PI_MISSING_OBJECT;
 return h;
}
