/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_SPATIAL_H
#define HUSK_TL_SPATIAL_H
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct {
    uint32_t version, size, input_width, input_height, output_width, output_height;
    uint32_t enabled, reserved;
} tl_spatial_config;
typedef struct {
    uint32_t version, size, configured, live_images;
    uint32_t input_width, input_height, output_width, output_height;
    uint64_t images_created, encoded, failures;
} tl_spatial_stats;
typedef int (*tl_spatial_configure_fn)(const tl_spatial_config *);
typedef int (*tl_spatial_stats_fn)(tl_spatial_stats *);
bool tl_spatial_dimensions(int width,int height,int percent,tl_spatial_config *out);
void husk_ue4_set_spatial_upscaling(bool enabled);
bool tl_vk_spatial_prepare(const char *project,int *width,int *height);
bool tl_vk_spatial_active(void);
void tl_vk_spatial_snapshot(tl_spatial_stats *out);
void tl_vk_spatial_touch(float *x,float *y);
#ifdef __cplusplus
}
#endif
#endif
