/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_COMPONENT_SCOPE_H
#define HUSK_TL_COMPONENT_SCOPE_H
#include "husk-tl-component-profile.h"
#include <stdatomic.h>
extern atomic_bool tl_cp_gate;
static inline void tl_cp_scope_cleanup(tl_cp_ticket *t){if(t->active)tl_cp_end(*t);}
/* Disabled: one relaxed gate read, no clocks/allocations/locks. Enabled: one in
 *64 entries per thread/component. GCC/Clang cleanup also covers early returns. */
#define TL_CP_SCOPE(kind) tl_cp_ticket tl_cp_scope_token __attribute__((cleanup(tl_cp_scope_cleanup)))={0}; \
 if(atomic_load_explicit(&tl_cp_gate,memory_order_relaxed))tl_cp_scope_token=tl_cp_begin(kind)
#endif
