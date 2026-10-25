/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_RENDER_INVENTORY_H
#define HUSK_TL_RENDER_INVENTORY_H
#include <stdbool.h>
#include <stdint.h>
/* Requested base fields only; no GPU reads or proof of scene/HUD contents. */
typedef struct { uint32_t kind,width,height,depth,format,usage,samples; uint64_t count; } tl_ri_group;
typedef struct { bool requested,active; uint64_t observed_images,observed_render_areas,dropped; } tl_ri_stats;
void husk_ue4_set_render_inventory(bool value);
void tl_ri_activate(const char *project);
bool tl_ri_active(void);
void tl_ri_image(const void *create_info);
void tl_ri_render_area(const void *begin_info);
uint32_t tl_ri_snapshot(tl_ri_group *out,uint32_t capacity,tl_ri_stats *stats);
#endif
