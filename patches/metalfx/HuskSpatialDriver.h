/* SPDX-License-Identifier: Apache-2.0 */
#pragma once
#include "HuskSpatialABI.h"
void* huskSpatialNewImage(id<MTLDevice>,MTLPixelFormat,MTLTextureUsage,const tl_spatial_config&);
id<MTLTexture> huskSpatialInput(void*);
bool huskSpatialEncode(void*,id<MTLTexture>,id<MTLCommandBuffer>);
void huskSpatialDeleteImage(void*);

#include "HuskDisplayABI.h"
uint64_t huskDisplayNewGeneration();
bool huskDisplayMonitoring();
void huskDisplayObserve(uint64_t,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t);
