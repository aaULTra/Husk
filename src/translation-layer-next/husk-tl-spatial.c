/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "husk-tl-spatial.h"
bool tl_spatial_dimensions(int width,int height,int percent,tl_spatial_config *out) {
    if(!out||width<64||height<64||width>8192||height>8192||percent<50||percent>=100)return false;
    int w=(width*percent/100)&~7,h=(height*percent/100)&~7;
    if(w<64||h<64||w>=width||h>=height)return false;
    double ratio=(double)w*height/((double)h*width);
    if(ratio<0.99||ratio>1.01)return false;
    *out=(tl_spatial_config){1,sizeof(*out),(uint32_t)w,(uint32_t)h,(uint32_t)width,(uint32_t)height,1,0};
    return true;
}
