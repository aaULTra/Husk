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
static struct event { tl_pi_request request; bool compute, cache; int result; uint64_t ns, finished, occurrence; int feedback; } events[EVENTS];
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
static uint64_t stage_hash(uint64_t h, void *device, const tl_pi_stage *stage, unsigned *known) {
    h = number(number(h, stage->stage), stage->flags);
    uint64_t shader = 0;
    for (unsigned i = 0; i < MODULES; i++) if (modules[i].device == device && modules[i].module == stage->module) { shader = modules[i].hash; break; }
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
tl_pi_request tl_pi_identify(bool compute, void *device, uint32_t count, const void *ci) {
    tl_pi_request r = {.count = count};
    if (!atomic_load(&enabled) || !ci || !count) return r;
    if (pthread_mutex_trylock(&mu)) { atomic_fetch_add(&drops, 1); return r; }
    r.sampled = count < 4 ? count : 4;
    for (unsigned i = 0; i < r.sampled; i++) {
        uint64_t h = number(14695981039346656037ULL, compute); r.known[i] = 1;
        if (compute) {
            const tl_pi_compute *p = (const tl_pi_compute *)ci + i;
            h = number(h, p->flags); h = stage_hash(h, device, &p->stage, &r.known[i]);
            if (p->next || p->type != 29) r.known[i] = 0;
        } else {
            const tl_pi_graphics *p = (const tl_pi_graphics *)ci + i;
            h = number(number(number(h, p->flags), p->count), p->subpass);
            if (p->count > 16 || (p->count && !p->stages) || p->type != 28) r.known[i] = 0;
            else for (unsigned j = 0; j < p->count; j++) h = stage_hash(h, device, p->stages+j, &r.known[i]);
            /* Explicit scalar fields only: no pointers, opaque handles or padding.
             * Input-assembly topology/restart distinguish common shader variants.
             * Remaining fixed/layout/render-pass state is deliberately unrepresented. */
            if (p->assembly) { const uint32_t *a = (const uint32_t *)((const char *)p->assembly + 16); h = number(number(number(h,a[0]),a[1]),a[2]); }
            if (p->next) r.known[i] = 0;
        }
        r.id[i] = h;
    }
    pthread_mutex_unlock(&mu); return r;
}
/* Passive feedback only: read a feedback chain the guest already supplied.
 * No extension is enabled, chain injected, compile flag changed or cache-hit
 * claim inferred from cache presence. -1 means unavailable/invalid feedback. */
static int feedback(const void *chain) {
    typedef struct node { uint32_t type; const struct node *next; } node;
    typedef struct { uint32_t flags; uint64_t duration; } data;
    typedef struct { uint32_t type; const void *next; const data *pipeline; uint32_t count; const data *stages; } info;
    const node *n = chain;
    for (unsigned i = 0; n && i < 32; i++, n = n->next) if (n->type == 1000192000) {
        const info *p = (const info *)n;
        return p->pipeline && (p->pipeline->flags & 1) ? !!(p->pipeline->flags & 2) : -1;
    }
    return -1;
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
    int hit = result == 0 ? feedback(chain) : -1;
    if (checked < SIGNATURES) {
        tl_pi_group *g = &signatures[slot]; g->signature = r.id[0]; occurrence = ++g->calls;
        g->slow_calls += elapsed >= 16666667; g->total_ns += elapsed;
        if (elapsed > g->worst_ns) g->worst_ns = elapsed;
        g->valid_feedback += hit >= 0; g->application_hits += hit == 1;
    } else atomic_fetch_add(&drops, 1);
    if (elapsed >= 16666667 || occurrence == 1 || occurrence == 2) {
        if (length == EVENTS) atomic_fetch_add(&drops, 1);
        else {
            events[(head+length++)%EVENTS] = (struct event){r,compute,cache,result,elapsed,finished,occurrence,hit};
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
        tl_log_line("ue4 pipeline identity: M2/PIPE-01 partial-v1 ids=%s kind=%s batch %u sampled %u host %.3f ms cache-present %d occurrence %llu feedback-first %s result %d, finished monotonic %.6f s; partial key; batch time; hitch unverified",
            ids,e.compute?"compute":"graphics",e.request.count,e.request.sampled,e.ns/1e6,e.cache,(unsigned long long)e.occurrence,e.feedback<0?"unavailable":e.feedback?"application-cache-hit":"valid-no-application-hit",e.result,e.finished/1e9);
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
