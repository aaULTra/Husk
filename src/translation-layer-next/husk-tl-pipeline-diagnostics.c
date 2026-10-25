/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "husk-tl-pipeline-diagnostics.h"
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>
_Static_assert(sizeof(tl_pi_stage) == 48 && sizeof(tl_pi_graphics) == 144 && sizeof(tl_pi_compute) == 96 && offsetof(tl_pi_graphics, subpass) == 120, "Vulkan 64-bit pipeline ABI");
#define MODULES 4096
#define SIGNATURES 2048
#define EVENTS 64
static atomic_bool enabled;
static pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;
static struct { void *device; uint64_t module, hash; } modules[MODULES];
static tl_pi_group signatures[SIGNATURES];
static struct event { tl_pi_request request; bool compute, cache; int result; uint64_t ns, finished, occurrence; int feedback; unsigned stage_count, stage_valid, stage_hits, stage_valid_mask, stage_hit_mask; } events[EVENTS];
static unsigned head, length;
static atomic_uint_fast64_t drops;
void tl_log_line(const char *fmt, ...);
static uint64_t bytes(uint64_t h, const void *p, size_t n) {
    const unsigned char *b = p; for (size_t i = 0; i < n; i++) { h ^= b[i]; h *= 1099511628211ULL; } return h;
}
static uint64_t number(uint64_t h, uint64_t n) { return bytes(h, &n, sizeof(n)); }
void husk_ue4_set_pipeline_diagnostics(bool value) { atomic_store(&enabled, value); }
void tl_pi_shader(void *device, uint64_t module, const tl_pi_module_ci *ci) {
    if (!atomic_load(&enabled) || !ci || !ci->code || !ci->size || ci->size > 16u*1024u*1024u) return;
    uint64_t hash = bytes(14695981039346656037ULL, ci->code, ci->size);
    if (pthread_mutex_trylock(&mu)) { atomic_fetch_add(&drops, 1); return; }
    unsigned slot = MODULES;
    for (unsigned i = 0; i < MODULES; i++) {
        if (modules[i].device == device && modules[i].module == module) { slot = i; break; }
        if (!modules[i].device && slot == MODULES) slot = i;
    }
    if (slot != MODULES) { modules[slot].device = device; modules[slot].module = module; modules[slot].hash = hash; }
    else atomic_fetch_add(&drops, 1);
    pthread_mutex_unlock(&mu);
}
/* Lifetime invalidation must not be skipped: a reused handle must never inherit
 * a previous shader's identity. These rare teardown operations take the mutex. */
void tl_pi_forget_shader(void *device, uint64_t module) {
    if (!atomic_load(&enabled)) return;
    pthread_mutex_lock(&mu);
    for (unsigned i = 0; i < MODULES; i++) if (modules[i].device == device && modules[i].module == module) modules[i].device = NULL;
    pthread_mutex_unlock(&mu);
}
void tl_pi_forget_device(void *device) {
    if (!atomic_load(&enabled)) return;
    pthread_mutex_lock(&mu);
    for (unsigned i = 0; i < MODULES; i++) if (modules[i].device == device) modules[i].device = NULL;
    pthread_mutex_unlock(&mu);
}
static uint64_t stage_hash(uint64_t h, void *device, const tl_pi_stage *stage, unsigned *known, uint64_t *shader_identity) {
    h = number(number(h, stage->stage), stage->flags);
    uint64_t shader = 0;
    for (unsigned i = 0; i < MODULES; i++) if (modules[i].device == device && modules[i].module == stage->module) { shader = modules[i].hash; break; }
    if (shader_identity) *shader_identity = shader;
    if (!shader) *known = 0;
    h = number(h, shader);
    if (stage->name) { size_t n = 0; while (n < 256 && stage->name[n]) n++; h = bytes(h, stage->name, n); if (n == 256) *known = 0; }
    else *known = 0;
    if (stage->next) *known = 0;
    const tl_pi_specialization *s = stage->specialization;
    if (s) {
        if (s->count > 256 || (s->count && (!s->entries || !s->data))) { *known = 0; return h; }
        for (unsigned i = 0; i < s->count; i++) {
            const tl_pi_map *e = &s->entries[i];
            if (e->offset > s->size || e->size > s->size - e->offset || e->size > 65536) { *known = 0; continue; }
            h = number(number(h, e->id), e->size); h = bytes(h, (const char *)s->data + e->offset, e->size);
        }
    }
    return h;
}
#include "husk-tl-pipeline-state.h"

tl_pi_request tl_pi_identify(bool compute, void *device, uint32_t count, const void *ci) {
    tl_pi_request r = {.count = count};
    if (!atomic_load(&enabled) || !ci || !count) return r;
    if (pthread_mutex_trylock(&mu)) { atomic_fetch_add(&drops, 1); return r; }
    r.sampled = count < 4 ? count : 4;
    for (unsigned i = 0; i < r.sampled; i++) {
        uint64_t h = number(14695981039346656037ULL, compute); r.known[i] = 1;
        if (compute) {
            const tl_pi_compute *p = (const tl_pi_compute *)ci + i;
            h = number(h, p->flags); h = stage_hash(h, device, &p->stage, &r.known[i], i == 0 ? &r.shader_hashes[0] : NULL);
            if (i == 0) { r.shader_stages = 1; r.stage_bits[0] = p->stage.stage; }
            if (p->next || p->type != 29) r.known[i] = 0;
        } else {
            const tl_pi_graphics *p = (const tl_pi_graphics *)ci + i;
            h = number(number(number(h, p->flags), p->count), p->subpass);
            if (p->count > 16 || (p->count && !p->stages) || p->type != 28) r.known[i] = 0;
            else {
                if (i == 0) r.shader_stages = p->count < 4 ? p->count : 4;
                for (unsigned j = 0; j < p->count; j++) {
                    if (i == 0 && j < 4) r.stage_bits[j] = p->stages[j].stage;
                    h = stage_hash(h, device, p->stages+j, &r.known[i], i == 0 && j < 4 ? &r.shader_hashes[j] : NULL);
                }
            }
            h = fixed_state(h,p,&r.known[i]);
            if (p->next) r.known[i] = 0;
        }
        r.id[i] = h;
    }
    pthread_mutex_unlock(&mu); return r;
}
/* Read actual valid driver outputs, from guest-supplied or explicitly requested
 * diagnostic feedback. Stage hits and pipeline hits are different evidence. */
typedef struct { int pipeline_hit; unsigned stage_count, stage_valid, stage_hits, stage_valid_mask, stage_hit_mask; } feedback_result;
static feedback_result feedback(const void *chain, unsigned expected_stages) {
    typedef struct node { uint32_t type; const struct node *next; } node;
    typedef struct { uint32_t flags; uint64_t duration; } data;
    typedef struct { uint32_t type; const void *next; const data *pipeline; uint32_t count; const data *stages; } info;
    feedback_result r = {.pipeline_hit = -1};
    const node *n = chain;
    for (unsigned i = 0; n && i < 32; i++, n = n->next) if (n->type == 1000192000) {
        const info *p = (const info *)n;
        if (p->pipeline && (p->pipeline->flags & 1)) r.pipeline_hit = !!(p->pipeline->flags & 2);
        r.stage_count = p->count;
        if (p->count <= 16 && p->count == expected_stages && p->stages) for (unsigned j = 0; j < p->count; j++) {
            if (p->stages[j].flags & 1) { r.stage_valid++; r.stage_valid_mask |= 1u << j; r.stage_hits += !!(p->stages[j].flags & 2); if (p->stages[j].flags & 2) r.stage_hit_mask |= 1u << j; }
        }
        break;
    }
    return r;
}
void tl_pi_completed(tl_pi_request r, bool compute, uint64_t elapsed, uint64_t finished, bool cache, int result, const void *ci) {
    if (!atomic_load(&enabled) || !r.sampled) return;
    if (pthread_mutex_trylock(&mu)) { atomic_fetch_add(&drops, 1); return; }
    uint64_t occurrence = 0;
    /* Count batch-level requests by first sampled signature; not per-pipeline duration. */
    unsigned slot = (unsigned)(r.id[0] % SIGNATURES), checked = 0;
    while (checked < SIGNATURES && signatures[slot].signature && signatures[slot].signature != r.id[0]) {
        slot = (slot + 1) % SIGNATURES; checked++;
    }
    const void *chain = compute ? ((const tl_pi_compute *)ci)->next : ((const tl_pi_graphics *)ci)->next;
    feedback_result f = result == 0 ? feedback(chain, compute ? 1 : ((const tl_pi_graphics *)ci)->count) : (feedback_result){.pipeline_hit = -1};
    int hit = f.pipeline_hit;
    if (checked < SIGNATURES) {
        tl_pi_group *g = &signatures[slot]; g->signature = r.id[0]; occurrence = ++g->calls;
        g->slow_calls += elapsed >= 16666667; g->total_ns += elapsed;
        if (elapsed > g->worst_ns) g->worst_ns = elapsed;
        g->valid_feedback += hit >= 0; g->application_hits += hit == 1;
        g->stage_feedback_valid += f.stage_valid; g->stage_application_hits += f.stage_hits;
        g->shader_stages = r.shader_stages; memcpy(g->shader_hashes,r.shader_hashes,sizeof(g->shader_hashes)); memcpy(g->stage_bits,r.stage_bits,sizeof(g->stage_bits));
        g->last_stage_valid_mask = f.stage_valid_mask; g->last_stage_hit_mask = f.stage_hit_mask;
    } else atomic_fetch_add(&drops, 1);
    if (elapsed >= 16666667 || occurrence == 1 || occurrence == 2) {
        if (length == EVENTS) atomic_fetch_add(&drops, 1);
        else {
            events[(head+length++)%EVENTS] = (struct event){r,compute,cache,result,elapsed,finished,occurrence,hit,f.stage_count,f.stage_valid,f.stage_hits,f.stage_valid_mask,f.stage_hit_mask};
        }
    }
    pthread_mutex_unlock(&mu);
}
void tl_pi_report(void) {
    if (!atomic_load(&enabled)) return;
    for (unsigned i = 0; i < 8; i++) {
        if (pthread_mutex_trylock(&mu)) return;
        if (!length) { pthread_mutex_unlock(&mu); break; }
        struct event e = events[head]; head = (head+1)%EVENTS; length--;
        pthread_mutex_unlock(&mu);
        char ids[220] = {0}; size_t used = 0;
        for (unsigned j = 0; j < e.request.sampled; j++) used += (size_t)snprintf(ids+used,sizeof(ids)-used,"%s%016llx/%s",j?",":"",(unsigned long long)e.request.id[j],e.request.known[j]?"shader-known":"incomplete");
        tl_log_line("ue4 pipeline identity: M2/PIPE-01 partial-v2 ids=%s kind=%s batch %u sampled %u host %.3f ms cache-present %d occurrence %llu feedback-first %s stages-valid %u/%u stage-hits %u masks %#x/%#x result %d, finished monotonic %.6f s; partial key; batch time; hitch unverified",
            ids,e.compute?"compute":"graphics",e.request.count,e.request.sampled,e.ns/1e6,e.cache,(unsigned long long)e.occurrence,e.feedback<0?"unavailable":e.feedback?"application-cache-hit":"valid-no-application-hit",e.stage_valid,e.stage_count,e.stage_hits,e.stage_valid_mask,e.stage_hit_mask,e.result,e.finished/1e9);
    }
    uint64_t lost = atomic_exchange(&drops,0);
    if (lost) tl_log_line("ue4 pipeline identity: M2/PIPE-01 diagnostic records unavailable/dropped %llu; bounded registry/events",(unsigned long long)lost);
}

uint32_t tl_pi_copy_groups(tl_pi_group *out, uint32_t capacity) {
    if (!atomic_load(&enabled) || !out || !capacity) return 0;
    pthread_mutex_lock(&mu);uint32_t n=0;
    for(unsigned i=0;i<SIGNATURES&&n<capacity;i++)if(signatures[i].signature)out[n++]=signatures[i];
    pthread_mutex_unlock(&mu);return n;
}
