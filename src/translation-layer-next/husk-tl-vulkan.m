/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "husk-tl-vulkan.h"

#import <QuartzCore/QuartzCore.h>
#import <QuartzCore/CAMetalLayer.h>
#import <Metal/Metal.h>
#include <TargetConditionals.h>
#if TARGET_OS_IOS
#import <UIKit/UIKit.h>
#include <os/proc.h>
#endif
#include <dispatch/dispatch.h>
#include <dlfcn.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <errno.h>
#include <time.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "husk-tl-bionic.h"
#include "husk-tl-ld.h"
#include "husk-tl-ue4-graphics.h"
#include "husk-tl-pipeline-store.h"
#include "husk-tl-thread-policy.h"
#include "husk-tl-driver-profile.h"
#include "husk-tl-efficiency.h"
#include "husk-tl-pipeline-diagnostics.h"
#include "husk-tl-pipeline-feedback.h"
#include "husk-tl-gpu-timing.h"
#include "husk-tl-render-inventory.h"
#include "husk-tl-spatial.h"

void *tl_nwindow_native(void *window);
int tl_nwindow_width(void *window);
int tl_nwindow_height(void *window);

/* Only the parts of the Vulkan structures this layer reads or writes; they are the same on the guest and the host. */
typedef struct { uint32_t sType; const void *pNext; uint32_t flags; const void *pApplicationInfo; uint32_t layerCount; const char *const *layers; uint32_t extCount; const char *const *exts; } vk_instance_ci;
typedef struct { uint32_t sType; const void *pNext; const char *appName; uint32_t appVersion; const char *engineName; uint32_t engineVersion; uint32_t apiVersion; } vk_app_info;
typedef tl_pf_extension vk_ext_props;
typedef struct { uint32_t sType; const void *pNext; uint32_t flags; void *window; } vk_android_surface_ci;
typedef struct { uint32_t sType; const void *pNext; uint32_t flags; const void *pLayer; } vk_metal_surface_ci;

#define VK_SUCCESS 0
#define VK_INCOMPLETE 5
#define VK_ERROR_EXTENSION_NOT_PRESENT (-7)
#define VK_STYPE_METAL_SURFACE_CI 1000217000

typedef void *(*pfn_gipa)(void *, const char *);
typedef int (*pfn_enum_ext)(const char *, uint32_t *, vk_ext_props *);
typedef int (*pfn_create_instance)(const vk_instance_ci *, const void *, void **);
typedef int (*pfn_create_metal_surface)(void *, const vk_metal_surface_ci *, const void *, uint64_t *);

static struct {
    pthread_once_t once;
    char path[1024];
    bool have_path;
    void *lib;
    pfn_gipa gipa;
    int trace;
    bool probe_frames;
    char frame_dir[700];
    int frame_every;
    atomic_ulong frames;
} V = { .once = PTHREAD_ONCE_INIT };

static void *g_swapchain_layer;                               /* the layer the surface was made on, for the log */

#define LOG(...) do { if (V.trace) tl_log_line(__VA_ARGS__); } while (0)

void tl_vk_configure(const char *path, const char *frame_dir, int frame_every)
{
    if (path) { snprintf(V.path, sizeof(V.path), "%s", path); V.have_path = true; }
    if (frame_dir) { snprintf(V.frame_dir, sizeof(V.frame_dir), "%s", frame_dir); V.frame_every = frame_every > 0 ? frame_every : 60; }
}

static bool spatial_requested;
static atomic_bool spatial_prepared;
static float spatial_touch_x=1.0f,spatial_touch_y=1.0f;
void husk_ue4_set_spatial_upscaling(bool enabled){spatial_requested=enabled;}
bool tl_vk_spatial_active(void){return atomic_load_explicit(&spatial_prepared,memory_order_acquire);}
void tl_vk_spatial_touch(float *x,float *y){
    if(tl_vk_spatial_active()){if(x)*x*=spatial_touch_x;if(y)*y*=spatial_touch_y;}
}
static int submission_mode;
void husk_ue4_set_submission_mode(int mode) { submission_mode = mode == 1 ? 1 : 0; }
static void vk_load(void)
{
    V.trace = getenv("TL_VK_TRACE") ? 1 : 0;
    /* One failed Metal command buffer (a GPU fault, or iOS cutting off a frame that kept the GPU too long) would otherwise lose the device for good, and a game
     * has no way back from VK_ERROR_DEVICE_LOST: DXVK reports it as a removed device and the game ends itself. Read once, when MoltenVK first needs its settings. */
    setenv("MVK_CONFIG_RESUME_LOST_DEVICE", "1", 0);
    /* GPU readback probes stall the queue. Opt in only when diagnosing a
     * blank image; normal gameplay never calls vkQueueWaitIdle for logging. */
    const char *probe = getenv("TL_VK_PROBE_FRAMES");
    V.probe_frames = probe && !strcmp(probe, "1");
    if (submission_mode == 1) setenv("MVK_CONFIG_SYNCHRONOUS_QUEUE_SUBMITS", "0", 1);
    V.lib = V.have_path ? dlopen(V.path, RTLD_NOW | RTLD_LOCAL) : RTLD_DEFAULT;
    if(!V.lib&&V.have_path){
        const char *suffix=strstr(V.path,"HuskMoltenVK.framework/HuskMoltenVK");
        if(suffix&&!strcmp(suffix,"HuskMoltenVK.framework/HuskMoltenVK")){
            char original[sizeof(V.path)];
            snprintf(original,sizeof(original),"%.*sMoltenVK.framework/MoltenVK",(int)(suffix-V.path),V.path);
            V.lib=dlopen(original,RTLD_NOW|RTLD_LOCAL);
            if(V.lib)snprintf(V.path,sizeof(V.path),"%s",original);
            tl_log_line("[M9-SPATIAL] experimental driver load failed; original driver fallback %s",V.lib?"loaded":"unavailable");
        }
    }
    typedef void (*version_fn)(char *, uint32_t, char *, uint32_t);
    version_fn versions = V.lib ? (version_fn)dlsym(V.lib, "vkGetVersionStringsMVK") : NULL;
    char mvk_version[64] = {0}, vulkan_version[64] = {0};
    if (versions) versions(mvk_version, sizeof(mvk_version), vulkan_version, sizeof(vulkan_version));
    tl_dp_set_api(V.lib ? (int (*)(void *, void *, size_t *))dlsym(V.lib, "vkGetPerformanceStatisticsMVK") : NULL, mvk_version);
    tl_pc_set_api((tl_pc_api){
        .create = V.lib ? (void *)dlsym(V.lib, "vkCreatePipelineCache") : NULL,
        .data = V.lib ? (void *)dlsym(V.lib, "vkGetPipelineCacheData") : NULL,
        .merge = V.lib ? (void *)dlsym(V.lib, "vkMergePipelineCaches") : NULL,
        .destroy = V.lib ? (void *)dlsym(V.lib, "vkDestroyPipelineCache") : NULL
    });
    V.gipa = V.lib ? (pfn_gipa)dlsym(V.lib, "vkGetInstanceProcAddr") : NULL;
    /* Stable first five fields of the versioned public MoltenVK configuration
     * ABI (verified against bundled 1.4.2). Short reads return VK_INCOMPLETE. */
    typedef int (*config_fn)(void *, void *, size_t *);
    config_fn config = V.lib ? (config_fn)dlsym(V.lib, "vkGetMoltenVKConfigurationMVK") : NULL;
    uint32_t prefix[5] = {0}; size_t bytes = sizeof(prefix);
    int cr = config ? config(NULL, prefix, &bytes) : -1;
    if ((cr == 0 || cr == 5) && bytes >= sizeof(prefix))
        tl_log_line("ue4 submission: mode %s; MoltenVK synchronous=%u, prefill=%u, active-command-buffer-limit=%u; asynchronous may move work rather than reduce it",
                    submission_mode ? "Async (experimental)" : "Driver Default", prefix[2], prefix[3], prefix[4]);
    else tl_log_line("ue4 submission: configuration unavailable rc=%d; no runtime layout assumptions used beyond size-checked prefix", cr);
    tl_log_line("vulkan: %s", V.gipa ? (V.have_path ? V.path : "MoltenVK linked into the process") : "MoltenVK not found");
}
static bool vk_ready(void) { pthread_once(&V.once, vk_load); return V.gipa != NULL; }
bool tl_vk_available(void) { return V.have_path && vk_ready(); }
void tl_vk_spatial_snapshot(tl_spatial_stats *out){
    if(!out)return;
    *out=(tl_spatial_stats){.version=1,.size=sizeof(*out)};
    if(V.lib){
        tl_spatial_stats_fn read=(tl_spatial_stats_fn)dlsym(V.lib,"vkHuskSpatialSnapshot");
        if(read&&!read(out))*out=(tl_spatial_stats){.version=1,.size=sizeof(*out)};
    }
}
bool tl_vk_spatial_prepare(const char *project,int *width,int *height){
    if(!spatial_requested)return false;
    tl_spatial_config config;
    if(!project||strcmp(project,"Dungeons")||!tl_ue4_sharp_graphics_enabled()||
       !width||!height||!tl_spatial_dimensions(*width,*height,80,&config)||!vk_ready()){
        tl_log_line("[M9-SPATIAL] preflight unavailable; original dimensions retained");return false;
    }
    tl_spatial_configure_fn configure=(tl_spatial_configure_fn)dlsym(V.lib,"vkHuskSpatialConfigure");
    if(!configure||!configure(&config)){
        tl_log_line("[M9-SPATIAL] driver/scaler preflight declined; original dimensions retained");return false;
    }
    spatial_touch_x=(float)config.input_width/config.output_width;
    spatial_touch_y=(float)config.input_height/config.output_height;
    *width=(int)config.input_width;*height=(int)config.input_height;
    atomic_store_explicit(&spatial_prepared,true,memory_order_release);
    tl_log_line("[M9-SPATIAL] configured experimental input %ux%u -> output %ux%u; 80%% dimension budget; actual encoding/quality/energy pending; restart with option OFF restores baseline",
                config.input_width,config.input_height,config.output_width,config.output_height);
    return true;
}

/* MoltenVK's own list of instance extensions */
static vk_ext_props *mvk_instance_exts(uint32_t *n)
{
    *n = 0;
    pfn_enum_ext f = (pfn_enum_ext)V.gipa(NULL, "vkEnumerateInstanceExtensionProperties");
    if (!f || f(NULL, n, NULL) != VK_SUCCESS) return NULL;
    vk_ext_props *p = calloc(*n + 1, sizeof(vk_ext_props));
    if (f(NULL, n, p) < 0) { free(p); *n = 0; return NULL; }
    return p;
}

/* The guest's list with Android's surface extension swapped for the Metal one and anything MoltenVK lacks dropped. */
static void resolve_feature_hooks(void *instance);

static int w_vkCreateInstance(const vk_instance_ci *ci, const void *alloc, void **out)
{
    uint32_t nhave = 0;
    vk_ext_props *have = mvk_instance_exts(&nhave);
    const char **ext = calloc(ci->extCount + 2, sizeof(char *));
    uint32_t n = 0;
    bool metal = false;
    for (uint32_t i = 0; i < ci->extCount; i++) {
        const char *e = ci->exts[i];
        if (!strcmp(e, "VK_KHR_android_surface")) e = "VK_EXT_metal_surface";
        bool ok = false;
        for (uint32_t j = 0; j < nhave; j++) if (!strcmp(have[j].name, e)) { ok = true; break; }
        if (!ok) { tl_log_line("vulkan: instance extension %s is not offered by MoltenVK, left out", e); continue; }
        if (!strcmp(e, "VK_EXT_metal_surface")) { if (metal) continue; metal = true; }
        ext[n++] = e;
    }
    vk_instance_ci copy = *ci;
    /* MoltenVK hands out a core entry point only when the instance asked for the version that has it, where Android's loader does not mind:
     * an engine that creates a 1.0 instance and then looks up vkGetPhysicalDeviceMemoryProperties2 gets NULL from it. So ask for 1.2. */
    vk_app_info app = { 0 };
    if (ci->pApplicationInfo) app = *(const vk_app_info *)ci->pApplicationInfo;
    else app.sType = 0;
    if (app.apiVersion < ((1u << 22) | (2u << 12))) app.apiVersion = (1u << 22) | (2u << 12);
    copy.pApplicationInfo = &app;
    copy.extCount = n; copy.exts = ext;
    copy.layerCount = 0; copy.layers = NULL;
    pfn_create_instance create = (pfn_create_instance)V.gipa(NULL, "vkCreateInstance");
    int r = create ? create(&copy, alloc, out) : -3;
    tl_log_line("vulkan: vkCreateInstance(%u extensions) -> %d", n, r);
    if (r == VK_SUCCESS && out && *out) resolve_feature_hooks(*out);
    free(ext); free(have);
    return r;
}

static int w_vkEnumerateInstanceExtensionProperties(const char *layer, uint32_t *count, vk_ext_props *props)
{
    if (layer) { *count = 0; return VK_SUCCESS; }
    uint32_t nhave = 0;
    vk_ext_props *have = mvk_instance_exts(&nhave);
    uint32_t total = nhave;
    vk_ext_props *all = calloc(nhave + 1, sizeof(vk_ext_props));
    if (nhave) memcpy(all, have, nhave * sizeof(vk_ext_props));
    bool has_android = false;
    for (uint32_t i = 0; i < nhave; i++) if (!strcmp(all[i].name, "VK_KHR_android_surface")) has_android = true;
    if (!has_android) { snprintf(all[total].name, sizeof(all[total].name), "VK_KHR_android_surface"); all[total].specVersion = 6; total++; }
    int r = VK_SUCCESS;
    if (!props) *count = total;
    else {
        uint32_t k = *count < total ? *count : total;
        memcpy(props, all, k * sizeof(vk_ext_props));
        if (k < total) r = VK_INCOMPLETE;
        *count = k;
    }
    free(all); free(have);
    return r;
}

/* On the phone the window's layer is the app's own; for a test on a Mac there is no view, so make one the size of the window. */
static void *layer_for(void *window)
{
    void *layer = tl_nwindow_native(window);
    if (layer) return layer;
    static CAMetalLayer *offscreen;
    if (!offscreen) {
        offscreen = [CAMetalLayer layer];
        offscreen.frame = CGRectMake(0, 0, tl_nwindow_width(window), tl_nwindow_height(window));
        offscreen.contentsScale = 1.0;
        offscreen.drawableSize = CGSizeMake(tl_nwindow_width(window), tl_nwindow_height(window));
        offscreen.framebufferOnly = NO;
        CFRetain((__bridge CFTypeRef)offscreen);
    }
    return (__bridge void *)offscreen;
}

static int w_vkCreateAndroidSurfaceKHR(void *instance, const vk_android_surface_ci *ci, const void *alloc, uint64_t *surface)
{
    pfn_create_metal_surface create = (pfn_create_metal_surface)V.gipa(instance, "vkCreateMetalSurfaceEXT");
    if (!create) return VK_ERROR_EXTENSION_NOT_PRESENT;
    void *layer = layer_for(ci->window);
    vk_metal_surface_ci m = { VK_STYPE_METAL_SURFACE_CI, NULL, 0, layer };
    int r = create(instance, &m, alloc, surface);
    tl_log_line("vulkan: surface on layer %p (%dx%d) -> %d", layer, tl_nwindow_width(ci->window), tl_nwindow_height(ci->window), r);
    g_swapchain_layer = layer;
    return r;
}

#if TARGET_OS_OSX
/* A test on a Mac has no view to look at: the frame about to be presented is read back from its swapchain image's Metal texture and written out like the GL path's
 * frames (latest.bmp, 24-bit). The queue is waited idle first, so the texture holds the finished frame. */
static void capture_frame(void *queue, const void *info)
{
    if (!V.frame_dir[0] || !V.lib) return;
    typedef int (*pfn_wait)(void *);
    typedef int (*pfn_get_images)(void *, uint64_t, uint32_t *, uint64_t *);
    typedef int (*pfn_get_tex)(uint64_t, void *);
    pfn_wait wait_idle = (pfn_wait)dlsym(V.lib, "vkQueueWaitIdle");
    pfn_get_images get_images = (pfn_get_images)dlsym(V.lib, "vkGetSwapchainImagesKHR");
    pfn_get_tex get_tex = (pfn_get_tex)dlsym(V.lib, "vkGetMTLTextureMVK");
    if (!wait_idle || !get_images || !get_tex) { tl_log_line("vulkan: capture: missing entry points (%p %p %p)", (void *)wait_idle, (void *)get_images, (void *)get_tex); return; }
    const uint8_t *pi = info;
    uint32_t nsw; memcpy(&nsw, pi + 32, 4);
    const uint64_t *sws; memcpy(&sws, pi + 40, 8);
    const uint32_t *idx; memcpy(&idx, pi + 48, 8);
    if (nsw < 1 || !sws || !idx) return;
    wait_idle(queue);
    uint32_t cnt = 0; get_images(NULL, sws[0], &cnt, NULL);
    if (idx[0] >= cnt || cnt > 8) { tl_log_line("vulkan: capture: image %u of %u", idx[0], cnt); return; }
    uint64_t imgs[8]; get_images(NULL, sws[0], &cnt, imgs);
    void *raw = NULL;
    get_tex(imgs[idx[0]], &raw);                          /* returns void: the texture is what it wrote */
    if (!raw) return;
    id<MTLTexture> tex = (__bridge id<MTLTexture>)raw;
    int w = (int)tex.width, h = (int)tex.height;
    static int said; if (said++ < 2) tl_log_line("vulkan: capture %dx%d format %d storage %d", w, h, (int)tex.pixelFormat, (int)tex.storageMode);
    if (tex.storageMode == MTLStorageModePrivate || w <= 0 || h <= 0) return;
    size_t bpr = (size_t)w * 4; uint8_t *px = malloc(bpr * h);
    [tex getBytes:px bytesPerRow:bpr fromRegion:MTLRegionMake2D(0, 0, w, h) mipmapLevel:0];
    char tmp[760], fin[760]; snprintf(tmp, sizeof(tmp), "%s/latest.tmp", V.frame_dir); snprintf(fin, sizeof(fin), "%s/latest.bmp", V.frame_dir);
    FILE *f = fopen(tmp, "wb");
    if (f) {
        uint32_t rowbytes = ((uint32_t)w * 3 + 3) & ~3u, size = 54 + rowbytes * (uint32_t)h;
        uint8_t hdr[54] = { 'B', 'M' };
        memcpy(hdr + 2, &size, 4); uint32_t off = 54; memcpy(hdr + 10, &off, 4);
        uint32_t dib = 40; memcpy(hdr + 14, &dib, 4); memcpy(hdr + 18, &w, 4); memcpy(hdr + 22, &h, 4);
        hdr[26] = 1; hdr[28] = 24; uint32_t img = rowbytes * (uint32_t)h; memcpy(hdr + 34, &img, 4);
        fwrite(hdr, 1, 54, f);
        uint8_t *row = calloc(1, rowbytes);
        for (int y = h - 1; y >= 0; y--) {                         /* BMP is bottom-up; the drawable is BGRA */
            const uint8_t *src = px + (size_t)y * bpr;
            for (int x = 0; x < w; x++) { row[x * 3] = src[x * 4]; row[x * 3 + 1] = src[x * 4 + 1]; row[x * 3 + 2] = src[x * 4 + 2]; }
            fwrite(row, 1, rowbytes, f);
        }
        free(row); fclose(f); rename(tmp, fin);
    }
    free(px);
}
#endif

/* What the layer the swapchain presents to looks like, said from the main thread (UIKit's properties are read there): drawable size, bounds, scale, format, and whether
 * the view that owns it is in a window, visible, and how big. For finding out why a game that is rendering shows nothing. */
static void log_layer_state(void *layerp, const char *when)
{
    if (!layerp) return;
    CAMetalLayer *l = (__bridge CAMetalLayer *)layerp;
    CFRetain((__bridge CFTypeRef)l);
    dispatch_async(dispatch_get_main_queue(), ^{
        CGSize ds = l.drawableSize; CGRect b = l.bounds;
        tl_log_line("vulkan: layer (%s): drawable %.0fx%.0f bounds %.0fx%.0f scale %.1f format %lu framebufferOnly %d opaque %d hidden %d opacity %.2f superlayer %p",
                    when, ds.width, ds.height, b.size.width, b.size.height, l.contentsScale, (unsigned long)l.pixelFormat, l.framebufferOnly, l.opaque, l.hidden, l.opacity, (__bridge void *)l.superlayer);
#if TARGET_OS_IOS
        id d = l.delegate;
        if ([d isKindOfClass:[UIView class]]) {
            UIView *v = d;
            CGAffineTransform transform = v.transform;
            tl_log_line("vulkan: sizing M6/BUG-03 (%s): drawable %.0fx%.0f pixels; view-bounds %.2fx%.2f points; affine %.5f %.5f %.5f %.5f %.2f %.2f; fixed swapchain size is not changed by this observation",
                        when, ds.width, ds.height, v.bounds.size.width, v.bounds.size.height,
                        transform.a, transform.b, transform.c, transform.d, transform.tx, transform.ty);
            tl_log_line("vulkan: view (%s): window %p hidden %d alpha %.2f frame %.0f,%.0f %.0fx%.0f superview %p appState %ld", when, (__bridge void *)v.window, v.hidden, v.alpha,
                        v.frame.origin.x, v.frame.origin.y, v.frame.size.width, v.frame.size.height, (__bridge void *)v.superview, (long)[UIApplication sharedApplication].applicationState);
        } else tl_log_line("vulkan: layer (%s) delegate is not a view: %s", when, d ? object_getClassName(d) : "(none)");
#endif
        CFRelease((__bridge CFTypeRef)l);
    });
}

/* The image about to be presented, read back (after the queue has finished it): its format, and nine pixels. Said at a few early presents so a log says whether the game is
 * drawing anything. Only texture the GPU lets the CPU read can be looked at. */
static void probe_frame(void *queue, const void *info, unsigned long n)
{
    if (!V.lib) return;
    typedef int (*pfn_wait)(void *);
    typedef int (*pfn_get_images)(void *, uint64_t, uint32_t *, uint64_t *);
    typedef int (*pfn_get_tex)(uint64_t, void *);
    pfn_wait wait_idle = (pfn_wait)dlsym(V.lib, "vkQueueWaitIdle");
    pfn_get_images get_images = (pfn_get_images)dlsym(V.lib, "vkGetSwapchainImagesKHR");
    pfn_get_tex get_tex = (pfn_get_tex)dlsym(V.lib, "vkGetMTLTextureMVK");
    if (!wait_idle || !get_images || !get_tex) { tl_log_line("vulkan: probe #%lu: missing entry points (%p %p %p)", n, (void *)wait_idle, (void *)get_images, (void *)get_tex); return; }
    const uint8_t *pi = info;
    uint32_t nsw; memcpy(&nsw, pi + 32, 4);
    const uint64_t *sws; memcpy(&sws, pi + 40, 8);
    const uint32_t *idx; memcpy(&idx, pi + 48, 8);
    if (nsw < 1 || !sws || !idx) return;
    wait_idle(queue);
    uint32_t cnt = 0; get_images(NULL, sws[0], &cnt, NULL);
    if (idx[0] >= cnt || cnt > 8) { tl_log_line("vulkan: probe #%lu: image %u of %u", n, idx[0], cnt); return; }
    uint64_t imgs[8]; get_images(NULL, sws[0], &cnt, imgs);
    void *raw = NULL;
    get_tex(imgs[idx[0]], &raw);
    if (!raw) { tl_log_line("vulkan: probe #%lu: no texture for image %u", n, idx[0]); return; }
    id<MTLTexture> tex = (__bridge id<MTLTexture>)raw;
    int w = (int)tex.width, h = (int)tex.height;
    bool readable = !tex.framebufferOnly && tex.storageMode != MTLStorageModePrivate && w > 0 && h > 0;
    char px[9 * 24]; px[0] = 0;
    if (readable) {
        static const int pts[9][2] = { {1,1},{2,1},{1,2},{0,0},{1,0},{0,1},{2,2},{1,1},{2,0} };      /* in eighths of the size */
        size_t off = 0;
        for (int i = 0; i < 9 && off + 24 < sizeof(px); i++) {
            int x = w * pts[i][0] / 4, y = h * pts[i][1] / 4; if (x >= w) x = w - 1; if (y >= h) y = h - 1;
            uint8_t b[16] = { 0 };
            [tex getBytes:b bytesPerRow:16 fromRegion:MTLRegionMake2D(x, y, 1, 1) mipmapLevel:0];
            off += (size_t)snprintf(px + off, sizeof(px) - off, " %02x%02x%02x%02x", b[0], b[1], b[2], b[3]);
        }
    }
    tl_log_line("vulkan: probe #%lu: image %u/%u %dx%d format %lu storage %lu usage %lu framebufferOnly %d pixels:%s", n, idx[0], cnt, w, h, (unsigned long)tex.pixelFormat, (unsigned long)tex.storageMode,
                (unsigned long)tex.usage, tex.framebufferOnly, readable ? px : " (not readable)");
}

/* M2 observer: original module arguments/results are forwarded unchanged. */
static int w_vkCreateShaderModule(void *device, const tl_pi_module_ci *ci, const void *alloc, uint64_t *out)
{
    typedef int (*fn)(void *, const void *, const void *, uint64_t *);
    fn real = V.lib ? (fn)dlsym(V.lib, "vkCreateShaderModule") : NULL;
    int result = real ? real(device, ci, alloc, out) : -3;
    if (result == VK_SUCCESS && out) tl_pi_shader(device, *out, ci);
    return result;
}
static void w_vkDestroyShaderModule(void *device, uint64_t module, const void *alloc)
{
    typedef void (*fn)(void *, uint64_t, const void *);
    fn real = V.lib ? (fn)dlsym(V.lib, "vkDestroyShaderModule") : NULL;
    tl_pi_forget_shader(device, module);
    if (real) real(device, module, alloc);
}

/* Direct MoltenVK handles only, no Vulkan loader/layers. The deprecated
 * export is optional: absent exports leave GPU timing unavailable. */
static void observe_game_queue(void *device,void *queue)
{
    if(!tl_ue4_sharp_graphics_enabled()||!queue)return;
    typedef void (*get_queue_fn)(void *,void **);
    get_queue_fn get=V.lib?(get_queue_fn)dlsym(V.lib,"vkGetMTLCommandQueueMVK"):NULL;
    void *metal=NULL;if(get)get(queue,&metal);
    if(metal)tl_gput_native_register(device,metal);
}
static void w_vkGetDeviceQueue(void *device,uint32_t family,uint32_t index,void **out)
{
    typedef void (*fn)(void *,uint32_t,uint32_t,void **);
    fn real=V.lib?(fn)dlsym(V.lib,"vkGetDeviceQueue"):NULL;
    if(real){real(device,family,index,out);if(out&&*out)observe_game_queue(device,*out);}
}
static void w_vkGetDeviceQueue2(void *device,const void *info,void **out)
{
    typedef void (*fn)(void *,const void *,void **);
    fn real=V.lib?(fn)dlsym(V.lib,"vkGetDeviceQueue2"):NULL;
    if(real){real(device,info,out);if(out&&*out)observe_game_queue(device,*out);}
}

/* M9 observation only; do not change extents, texture use or command order. */
static int w_vkCreateImage(void *device,const void *ci,const void *alloc,uint64_t *out)
{
    typedef int (*fn)(void *,const void *,const void *,uint64_t *);
    fn real=V.lib?(fn)dlsym(V.lib,"vkCreateImage"):NULL;
    int result=real?real(device,ci,alloc,out):-3;
    if(result==VK_SUCCESS&&out&&*out)tl_ri_image(ci);
    return result;
}
static void w_vkCmdBeginRenderPass(void *command,const void *info,uint32_t contents)
{
    typedef void (*fn)(void *,const void *,uint32_t);
    static _Atomic(fn) cached;
    fn real=atomic_load_explicit(&cached,memory_order_acquire);
    if(!real&&V.lib){real=(fn)dlsym(V.lib,"vkCmdBeginRenderPass");atomic_store_explicit(&cached,real,memory_order_release);}
    if(real){real(command,info,contents);tl_ri_render_area(info);}
}

typedef int (*pfn_create_swapchain)(void *, const void *, const void *, uint64_t *);
static int64_t monotonic_ns(void);
enum { TIMING_ACQUIRE, TIMING_SUBMIT, TIMING_PRESENT, TIMING_SLEEP, TIMING_GRAPHICS_PIPELINES, TIMING_COMPUTE_PIPELINES, TIMING_COUNT };
/* Host API durations only. These calls may overlap between threads and are not
 * GPU execution time. Relaxed counters avoid locks or GPU synchronization. */
static struct { atomic_uint_fast64_t ns, calls; } host_timings[TIMING_COUNT];
static atomic_uint pipeline_inflight;
static atomic_uint_fast64_t pipeline_window_max, pipeline_window_slow;
static pthread_mutex_t pipeline_event_mu = PTHREAD_MUTEX_INITIALIZER;
static struct pipeline_event {
    uint64_t elapsed, lock_wait;
    int64_t finished;
    unsigned stage, count;
    bool cache;
    int result;
} worst_pipeline;
static uint64_t record_host_timing(unsigned stage, int64_t start)
{
    uint64_t elapsed = (uint64_t)(monotonic_ns() - start);
    atomic_fetch_add_explicit(&host_timings[stage].ns, elapsed, memory_order_relaxed);
    atomic_fetch_add_explicit(&host_timings[stage].calls, 1, memory_order_relaxed);
    tl_em_host(stage, elapsed);
    return elapsed;
}
/* Keep one worst slow call per reporting period. Producers never wait for the
 * diagnostic mutex, and no pipeline thread writes a per-call log or waits GPU idle. */
static void record_pipeline_event(unsigned stage, uint32_t count, bool cache, int result,
                                  int64_t finished, uint64_t elapsed, uint64_t lock_wait)
{
    uint_fast64_t old = atomic_load_explicit(&pipeline_window_max, memory_order_relaxed);
    while (elapsed > old && !atomic_compare_exchange_weak_explicit(&pipeline_window_max, &old, elapsed,
                                                                  memory_order_relaxed, memory_order_relaxed)) {}
    if (elapsed < 16666667) return;
    atomic_fetch_add_explicit(&pipeline_window_slow, 1, memory_order_relaxed);
    if (pthread_mutex_trylock(&pipeline_event_mu)) return;
    if (elapsed > worst_pipeline.elapsed)
        worst_pipeline = (struct pipeline_event){elapsed, lock_wait, finished, stage, count, cache, result};
    pthread_mutex_unlock(&pipeline_event_mu);
}
static void report_pipeline_event(void)
{
    if (pthread_mutex_trylock(&pipeline_event_mu)) return;
    struct pipeline_event event = worst_pipeline; worst_pipeline = (struct pipeline_event){0};
    pthread_mutex_unlock(&pipeline_event_mu);
    if (event.elapsed)
        tl_log_line("ue4 pipeline stall: worst observed %s call %.3f ms, store-lock wait %.3f ms, batch %u, cache %s, result %d, finished monotonic %.6f s; host duration, not exclusive frame/GPU time or verified cache miss",
                    event.stage == TIMING_GRAPHICS_PIPELINES ? "graphics" : "compute", event.elapsed / 1e6,
                    event.lock_wait / 1e6, event.count, event.cache ? "yes" : "no", event.result, event.finished / 1e9);
}
static int w_vkCreateSwapchainKHR(void *device, const void *ci, const void *alloc, uint64_t *out)
{
    static pfn_create_swapchain real;
    if (!real && V.lib) real = (pfn_create_swapchain)dlsym(V.lib, "vkCreateSwapchainKHR");
    const uint8_t *c = ci; uint32_t minimg, fmt, cs, w, h, usage, alpha, mode;
    memcpy(&minimg, c + 32, 4); memcpy(&fmt, c + 36, 4); memcpy(&cs, c + 40, 4); memcpy(&w, c + 44, 4); memcpy(&h, c + 48, 4);
    memcpy(&usage, c + 56, 4); memcpy(&alpha, c + 84, 4); memcpy(&mode, c + 88, 4);
    int r = real ? real(device, ci, alloc, out) : -3;
    tl_log_line("vulkan: vkCreateSwapchainKHR %ux%u images %u format %u colorspace %u usage %#x compositeAlpha %u presentMode %u -> %d", w, h, minimg, fmt, cs, usage, alpha, mode, r);
    if (r == VK_SUCCESS) tl_em_size(w, h);
    if (r == VK_SUCCESS && tl_ue4_sharp_graphics_enabled())
        tl_log_line("ue4 graphics: actual guest swapchain buffer %ux%u (M9 experiment may upscale to a separate drawable; not a measurement of internal 3D resolution)", w, h);
    /* MoltenVK changes the layer from this thread, which has no run loop: make sure the changes are committed rather than waiting for a transaction nothing will flush. */
    [CATransaction flush];
    log_layer_state(g_swapchain_layer, "after swapchain");
    return r;
}

typedef int (*pfn_acquire)(void *, uint64_t, uint64_t, uint64_t, uint64_t, uint32_t *);
static int w_vkAcquireNextImageKHR(void *device, uint64_t swapchain, uint64_t timeout, uint64_t sem, uint64_t fence, uint32_t *index)
{
    static pfn_acquire real;
    static atomic_int bad, seen;
    if (!real && V.lib) real = (pfn_acquire)dlsym(V.lib, "vkAcquireNextImageKHR");
    bool measure = tl_ue4_sharp_graphics_enabled();
    int64_t start = measure ? monotonic_ns() : 0;
    int r = real ? real(device, swapchain, timeout, sem, fence, index) : -3;
    if (measure) record_host_timing(TIMING_ACQUIRE, start);
    if (r != VK_SUCCESS && atomic_fetch_add(&bad, 1) < 20) tl_log_line("vulkan: vkAcquireNextImageKHR -> %d", r);
    else if (atomic_fetch_add(&seen, 1) < 2) tl_log_line("vulkan: vkAcquireNextImageKHR -> %d (image %u)", r, index ? *index : 0);
    return r;
}

typedef int (*pfn_queue_submit)(void *, uint32_t, const void *, uint64_t);
static int w_vkQueueSubmit(void *queue, uint32_t count, const void *submits, uint64_t fence)
{
    static _Atomic(pfn_queue_submit) cached;
    pfn_queue_submit real = atomic_load_explicit(&cached, memory_order_acquire);
    if (!real && V.lib) {
        real = (pfn_queue_submit)dlsym(V.lib, "vkQueueSubmit");
        atomic_store_explicit(&cached, real, memory_order_release);
    }
    bool measure = tl_ue4_sharp_graphics_enabled();
    int64_t start = measure ? monotonic_ns() : 0;
    int result = real ? real(queue, count, submits, fence) : -3;
    if (measure) record_host_timing(TIMING_SUBMIT, start);
    return result;
}

/* Observe guest cache use without changing cache contents, pipeline options,
 * compilation order or synchronization. Data returned is not proof of a disk save. */
static atomic_uint cache_log_events;
static atomic_uint_fast64_t cache_creates, cache_seeded, cache_host_seeded, cache_host_seed_bytes, cache_readbacks, cached_pipeline_calls, uncached_pipeline_calls;
typedef int (*pfn_cache_create)(void *, const void *, const void *, uint64_t *);
static int w_vkCreatePipelineCache(void *device, const void *ci, const void *alloc, uint64_t *out)
{
    static _Atomic(pfn_cache_create) cached;
    pfn_cache_create real = atomic_load_explicit(&cached, memory_order_acquire);
    if (!real && V.lib) {
        real = (pfn_cache_create)dlsym(V.lib, "vkCreatePipelineCache");
        atomic_store_explicit(&cached, real, memory_order_release);
    }
    bool locked = tl_pc_enter();
    const tl_pc_create_info *original = ci;
    tl_pc_create_info seeded;
    size_t stored_size = 0;
    void *stored = original && !original->next && !original->flags && !original->size ? tl_pc_load(device, &stored_size) : NULL;
    bool host_seed_used = stored != NULL;
    if (stored) { seeded = *original; seeded.size = stored_size; seeded.data = stored; }
    int result = real ? real(device, stored ? &seeded : ci, alloc, out) : -3;
    if (stored && result == -3) {
        tl_log_line("ue4 cache store: driver rejected seed (%d); retrying original empty cache", result);
        tl_pc_discard(device);
        host_seed_used = false;
        result = real ? real(device, ci, alloc, out) : -3;
    }
    if (result == VK_SUCCESS && out) tl_pc_track(device, *out);
    free(stored);
    tl_pc_leave(locked);
    if (tl_ue4_sharp_graphics_enabled()) {
        size_t bytes = 0;
        if (ci) memcpy(&bytes, (const uint8_t *)ci + 24, sizeof(bytes));
        if (result == VK_SUCCESS) {
            atomic_fetch_add_explicit(&cache_creates, 1, memory_order_relaxed);
            if (bytes) atomic_fetch_add_explicit(&cache_seeded, 1, memory_order_relaxed);
            if (host_seed_used) {
                atomic_fetch_add_explicit(&cache_host_seeded, 1, memory_order_relaxed);
                atomic_fetch_add_explicit(&cache_host_seed_bytes, stored_size, memory_order_relaxed);
            }
        }
        if (atomic_fetch_add_explicit(&cache_log_events, 1, memory_order_relaxed) < 24)
            tl_log_line("ue4 cache: game initial data %llu bytes, host restored %llu bytes, host seed accepted %d, result %d; acceptance is not proof of cache hits",
                        (unsigned long long)bytes, (unsigned long long)(host_seed_used ? stored_size : 0), host_seed_used && result == VK_SUCCESS, result);
    }
    return result;
}
typedef int (*pfn_cache_data)(void *, uint64_t, size_t *, void *);
static int w_vkGetPipelineCacheData(void *device, uint64_t cache, size_t *size, void *data)
{
    static _Atomic(pfn_cache_data) cached;
    pfn_cache_data real = atomic_load_explicit(&cached, memory_order_acquire);
    if (!real && V.lib) {
        real = (pfn_cache_data)dlsym(V.lib, "vkGetPipelineCacheData");
        atomic_store_explicit(&cached, real, memory_order_release);
    }
    bool locked = tl_pc_enter();
    int result = real ? real(device, cache, size, data) : -3;
    tl_pc_leave(locked);
    if (tl_ue4_sharp_graphics_enabled()) {
        if (data && result >= 0) atomic_fetch_add_explicit(&cache_readbacks, 1, memory_order_relaxed);
        if (atomic_fetch_add_explicit(&cache_log_events, 1, memory_order_relaxed) < 24)
            tl_log_line("ue4 cache: %s %llu bytes, result %d; readback does not confirm disk persistence", data ? "data readback" : "size query", (unsigned long long)(size ? *size : 0), result);
    }
    return result;
}
typedef int (*pfn_create_pipelines)(void *, uint64_t, uint32_t, const void *, const void *, uint64_t *);
static int measure_pipeline_create(pfn_create_pipelines real, unsigned stage, void *device, uint64_t cache, uint32_t count, const void *ci, const void *alloc, uint64_t *out)
{
    tl_pi_request identity = tl_pi_identify(stage == TIMING_COMPUTE_PIPELINES, device, count, ci);
    tl_pf_batch feedback_batch;
    const void *observed_ci = tl_pf_prepare(stage == TIMING_COMPUTE_PIPELINES, device, count, ci, &feedback_batch);
    bool measure = tl_ue4_sharp_graphics_enabled();
    int64_t start = measure ? monotonic_ns() : 0;
    if (measure) atomic_fetch_add_explicit(&pipeline_inflight, 1, memory_order_relaxed);
    bool locked = tl_pc_enter();
    int64_t entered = measure ? monotonic_ns() : 0;
    int result = real ? real(device, cache, count, observed_ci, alloc, out) : -3;
    if (real && count) tl_pc_changed(device, cache);
    tl_pc_leave(locked);
    if (measure) {
        uint64_t elapsed = record_host_timing(stage, start);
        tl_pi_completed(identity, stage == TIMING_COMPUTE_PIPELINES, elapsed, start + elapsed, cache != 0, result, observed_ci);
        record_pipeline_event(stage, count, cache != 0, result, start + (int64_t)elapsed, elapsed, (uint64_t)(entered - start));
        tl_thread_policy_pipeline_completed(start + (int64_t)elapsed, (int64_t)elapsed);
        atomic_fetch_sub_explicit(&pipeline_inflight, 1, memory_order_relaxed);
        atomic_fetch_add_explicit(cache ? &cached_pipeline_calls : &uncached_pipeline_calls, 1, memory_order_relaxed);
    }
    tl_pf_release(&feedback_batch);
    return result;
}
static int w_vkCreateGraphicsPipelines(void *device, uint64_t cache, uint32_t count, const void *ci, const void *alloc, uint64_t *out)
{
    static _Atomic(pfn_create_pipelines) cached;
    pfn_create_pipelines real = atomic_load_explicit(&cached, memory_order_acquire);
    if (!real && V.lib) {
        real = (pfn_create_pipelines)dlsym(V.lib, "vkCreateGraphicsPipelines");
        atomic_store_explicit(&cached, real, memory_order_release);
    }
    return measure_pipeline_create(real, TIMING_GRAPHICS_PIPELINES, device, cache, count, ci, alloc, out);
}
static int w_vkCreateComputePipelines(void *device, uint64_t cache, uint32_t count, const void *ci, const void *alloc, uint64_t *out)
{
    static _Atomic(pfn_create_pipelines) cached;
    pfn_create_pipelines real = atomic_load_explicit(&cached, memory_order_acquire);
    if (!real && V.lib) {
        real = (pfn_create_pipelines)dlsym(V.lib, "vkCreateComputePipelines");
        atomic_store_explicit(&cached, real, memory_order_release);
    }
    return measure_pipeline_create(real, TIMING_COMPUTE_PIPELINES, device, cache, count, ci, alloc, out);
}

static int w_vkMergePipelineCaches(void *device, uint64_t dst, uint32_t count, const uint64_t *src)
{
    typedef int (*fn)(void *, uint64_t, uint32_t, const uint64_t *);
    fn real = V.lib ? (fn)dlsym(V.lib, "vkMergePipelineCaches") : NULL;
    bool locked = tl_pc_enter();
    int result = real ? real(device, dst, count, src) : -3;
    if (real && count) tl_pc_changed(device, dst);
    tl_pc_leave(locked); return result;
}
static void w_vkDestroyPipelineCache(void *device, uint64_t cache, const void *alloc)
{
    typedef void (*fn)(void *, uint64_t, const void *);
    fn real = V.lib ? (fn)dlsym(V.lib, "vkDestroyPipelineCache") : NULL;
    bool locked = tl_pc_enter();
    tl_pc_untrack(device, cache);
    if (real) real(device, cache, alloc);
    tl_pc_leave(locked);
}
static void w_vkDestroyDevice(void *device, const void *alloc)
{
    tl_dp_forget(device);
    tl_pi_forget_device(device);
    tl_pf_forget_device(device);
    tl_gput_native_forget(device);
    typedef void (*fn)(void *, const void *);
    fn real = V.lib ? (fn)dlsym(V.lib, "vkDestroyDevice") : NULL;
    tl_pc_forget_device(device, real, alloc);
}

static int64_t monotonic_ns(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (int64_t)t.tv_sec * 1000000000LL + t.tv_nsec;
}
static int compare_frame_ms(const void *a, const void *b)
{
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}
/* Observe every Sharp mode. Keep the working Efficient limiter unchanged.
 * Timings do not add GPU waits, readbacks or per-frame log messages. */
static void pace_efficient_frame(void)
{
    if (!tl_ue4_sharp_graphics_enabled()) return;
    static _Thread_local int64_t deadline, sampled_at, recovered_at, previous, report_at;
    static _Thread_local int thermal, cap;
    static _Thread_local int last_observed = -1, last_low_power = -1;
    static _Thread_local double intervals[600];
    static _Thread_local unsigned count, late;
    static _Thread_local uint64_t last_ns[TIMING_COUNT], last_calls[TIMING_COUNT];
    int64_t now = monotonic_ns();
    if (!sampled_at || now - sampled_at >= 1000000000LL) {
        int observed = 0, low_power = 0;
#if TARGET_OS_IOS
        NSProcessInfo *process = [NSProcessInfo processInfo];
        observed = (int)process.thermalState;
        low_power = process.lowPowerModeEnabled ? 1 : 0;
#endif
        if (observed != last_observed || low_power != last_low_power) {
            if (last_observed >= 0 && (observed > 0 || low_power != last_low_power)) tl_thread_policy_suspend();
            tl_log_line("ue4 power: low-power mode %d, reported thermal %d (0 nominal, 1 fair, 2 serious, 3 critical); settings and pacing unchanged by observation", low_power, observed);
            last_observed = observed; last_low_power = low_power;
        }
        /* Escalate on the next sample; recover only after 15 seconds at a
         * lower state, avoiding repeated speed changes near a threshold. */
        if (observed >= thermal) { thermal = observed; recovered_at = 0; }
        else if (!recovered_at) recovered_at = now;
        else if (now - recovered_at >= 15000000000LL) { thermal = observed; recovered_at = 0; }
        sampled_at = now;
    }
    int wanted = tl_ue4_effective_frame_limit(thermal);
    int host_cap = tl_ue4_host_frame_limit(thermal);
    if (wanted != cap) {
        cap = wanted; deadline = 0;
        count = late = 0; previous = 0; report_at = now;
        tl_log_line("ue4 timing: requested cap %d FPS (0 game controlled), host cap %d (0 no extra limiter), thermal %d; selected launch resolution retained", cap, host_cap, thermal);
    }
    int64_t delay = tl_ue4_frame_delay_ns(now, host_cap, &deadline);
    if (delay > 0) {
        int64_t sleep_started = now;
        struct timespec wait = { .tv_sec = delay / 1000000000LL, .tv_nsec = delay % 1000000000LL };
        while (nanosleep(&wait, &wait) != 0 && errno == EINTR) {}
        record_host_timing(TIMING_SLEEP, sleep_started);
        now = monotonic_ns();
    }
    tl_em_frame(now);
    /* Present-to-present wall-clock cadence including pacing, not GPU time.
     * Discard background/loading gaps instead of reporting them as gameplay. */
    if (previous && now - previous < 1000000000LL) {
        tl_thread_policy_frame(now, now - previous);
        double ms = (double)(now - previous) / 1e6;
        intervals[count++] = ms;
        if (ms > 1000.0 / (cap ? cap : 60) * 1.2) late++;
    } else {
        count = late = 0; report_at = now;
        atomic_exchange_explicit(&pipeline_window_max, 0, memory_order_relaxed);
        atomic_exchange_explicit(&pipeline_window_slow, 0, memory_order_relaxed);
        if (!pthread_mutex_trylock(&pipeline_event_mu)) { worst_pipeline = (struct pipeline_event){0}; pthread_mutex_unlock(&pipeline_event_mu); }
        for (unsigned i = 0; i < TIMING_COUNT; i++) {
            last_ns[i] = atomic_load_explicit(&host_timings[i].ns, memory_order_relaxed);
            last_calls[i] = atomic_load_explicit(&host_timings[i].calls, memory_order_relaxed);
        }
    }
    previous = now;
    if (count && (count == 600 || now - report_at >= 10000000000LL)) {
        double sum = 0;
        for (unsigned i = 0; i < count; i++) sum += intervals[i];
        qsort(intervals, count, sizeof(intervals[0]), compare_frame_ms);
        unsigned p95 = (count * 95 + 99) / 100 - 1;
        double avg[TIMING_COUNT];
        uint64_t window_ns[TIMING_COUNT];
        uint64_t samples[TIMING_COUNT];
        for (unsigned i = 0; i < TIMING_COUNT; i++) {
            uint64_t ns = atomic_load_explicit(&host_timings[i].ns, memory_order_relaxed);
            uint64_t calls = atomic_load_explicit(&host_timings[i].calls, memory_order_relaxed);
            samples[i] = calls - last_calls[i];
            window_ns[i] = ns - last_ns[i];
            avg[i] = samples[i] ? (double)window_ns[i] / samples[i] / 1e6 : 0;
            last_ns[i] = ns; last_calls[i] = calls;
        }
        uint64_t pipeline_ns = window_ns[TIMING_GRAPHICS_PIPELINES] + window_ns[TIMING_COMPUTE_PIPELINES];
        uint64_t pipeline_max = atomic_exchange_explicit(&pipeline_window_max, 0, memory_order_relaxed);
        uint64_t pipeline_slow = atomic_exchange_explicit(&pipeline_window_slow, 0, memory_order_relaxed);
        unsigned inflight = atomic_load_explicit(&pipeline_inflight, memory_order_relaxed);
        tl_thread_policy_sample(now, (int64_t)(sum * 1e6), count * 1000.0 / sum,
                                intervals[p95], intervals[count - 1], last_observed, last_low_power > 0,
                                pipeline_ns, pipeline_max, inflight);
        tl_log_line("ue4 timing: cadence %.1f FPS, p95 %.2f ms, max %.2f ms, %u/%u intervals >120%% of %d FPS reference; thermal %d, engine cap %d, host cap %d; host call averages acquire %.3f ms (%llu), submit %.3f ms (%llu), present %.3f ms (%llu), sleep %.3f ms (%llu); calls may overlap; not GPU execution or displayed-frame timing",
                    count * 1000.0 / sum, intervals[p95], intervals[count - 1], late, count, cap ? cap : 60, thermal, cap, host_cap,
                    avg[0], (unsigned long long)samples[0], avg[1], (unsigned long long)samples[1],
                    avg[2], (unsigned long long)samples[2], avg[3], (unsigned long long)samples[3]);
        tl_log_line("ue4 cache totals: created %llu, supplied initial data %llu, readbacks %llu, pipeline calls with cache %llu / null %llu; window graphics create %.3f ms (%llu), compute create %.3f ms (%llu); host times, not GPU execution or verified cache hits",
                    (unsigned long long)atomic_load_explicit(&cache_creates, memory_order_relaxed),
                    (unsigned long long)atomic_load_explicit(&cache_seeded, memory_order_relaxed),
                    (unsigned long long)atomic_load_explicit(&cache_readbacks, memory_order_relaxed),
                    (unsigned long long)atomic_load_explicit(&cached_pipeline_calls, memory_order_relaxed),
                    (unsigned long long)atomic_load_explicit(&uncached_pipeline_calls, memory_order_relaxed),
                    avg[TIMING_GRAPHICS_PIPELINES], (unsigned long long)samples[TIMING_GRAPHICS_PIPELINES],
                    avg[TIMING_COMPUTE_PIPELINES], (unsigned long long)samples[TIMING_COMPUTE_PIPELINES]);
        tl_log_line("ue4 cache detail: host seeds accepted %llu (%llu bytes); pipeline window total %.3f ms, max %.3f ms, calls >=16.67 ms %llu, in-flight %u; aggregate calls may overlap",
                    (unsigned long long)atomic_load_explicit(&cache_host_seeded, memory_order_relaxed),
                    (unsigned long long)atomic_load_explicit(&cache_host_seed_bytes, memory_order_relaxed),
                    pipeline_ns / 1e6, pipeline_max / 1e6, (unsigned long long)pipeline_slow, inflight);
        report_pipeline_event();
        tl_dp_report();
        count = late = 0; report_at = now;
    }
}

typedef int (*pfn_queue_present)(void *, const void *);
static int w_vkQueuePresentKHR(void *queue, const void *info)
{
    static pfn_queue_present real;
    if (!real && V.lib) real = (pfn_queue_present)dlsym(V.lib, "vkQueuePresentKHR");
    unsigned long n = atomic_fetch_add(&V.frames, 1) + 1;
#if TARGET_OS_OSX
    if (V.frame_dir[0] && n % (V.frame_every > 0 ? (unsigned)V.frame_every : 60u) == 0) capture_frame(queue, info);
#endif
    if (V.probe_frames && (n == 3 || n == 60 || n == 400 || n == 3000)) { probe_frame(queue, info, n); log_layer_state(g_swapchain_layer, "present"); }
    /* VK_GOOGLE_display_timing: the game may ask for each frame to appear at a time of its own choosing. MoltenVK hands that to Metal as an absolute time on the system's media
     * clock, which is not the clock an Android game counted its nanoseconds on, so a time that was "now" to the game can be hours away to Metal and the frame is never shown.
     * Frames are shown when they are ready instead. */
    for (const uint8_t *c = *(const uint8_t *const *)((const uint8_t *)info + 8); c; c = *(const uint8_t *const *)(c + 8)) {
        uint32_t st; memcpy(&st, c, 4);
        if (st != 1000092000u) continue;                                   /* VK_STRUCTURE_TYPE_PRESENT_TIMES_INFO_GOOGLE */
        uint32_t cnt; memcpy(&cnt, c + 16, 4);
        uint8_t *times; memcpy(&times, c + 24, 8);
        for (uint32_t i = 0; times && i < cnt; i++) {
            uint64_t want; memcpy(&want, times + i * 16 + 8, 8);
            static atomic_int said; if (want && atomic_fetch_add(&said, 1) < 6) tl_log_line("vulkan: present #%lu asked for time %llu ns (media clock now %.0f ns); shown at once", n, (unsigned long long)want, CACurrentMediaTime() * 1e9);
            uint64_t zero = 0; memcpy(times + i * 16 + 8, &zero, 8);
        }
    }
    bool measure = tl_ue4_sharp_graphics_enabled();
    int64_t start = measure ? monotonic_ns() : 0;
    int r = real ? real(queue, info) : -3;
    if (measure) record_host_timing(TIMING_PRESENT, start);
    if (r >= 0) pace_efficient_frame();
    { static atomic_int bad; if (r != VK_SUCCESS && atomic_fetch_add(&bad, 1) < 20) tl_log_line("vulkan: vkQueuePresentKHR #%lu -> %d", n, r); }
    { static int tr = -1; if (tr < 0) tr = getenv("TL_VK_TRACE") ? 1 : 0; if (tr && n <= 5) tl_log_line("vulkan: vkQueuePresentKHR #%lu -> %d", n, r); }
    return r;
}


/* ------------------------------------------------------------ Direct3D 11 features over Metal */
/*
 * DXVK (Direct3D 9-11 over Vulkan) refuses a device that lacks any feature Direct3D 11 makes mandatory, and Metal has a few of them
 * not at all: geometry shaders, cull distances, pipeline statistics queries, logic ops. A game that ships DXVK is told they are
 * there, so it gets past adapter selection, and the device is then made without them. Most games never use them; one that does
 * loses that draw rather than the whole game. Only for DXVK games: anything else is told the truth.
 */
#define VK_STYPE_FEATURES2 51
enum { F_GEOMETRY = 4, F_LOGIC_OP = 8, F_PIPELINE_STATS = 24, F_CULL_DISTANCE = 38 };
static const int k_d3d_features[] = { F_GEOMETRY, F_LOGIC_OP, F_PIPELINE_STATS, F_CULL_DISTANCE };
#define N_FEATURES 55

typedef void (*pfn_get_features)(void *, uint32_t *);
typedef struct { uint32_t sType; void *pNext; uint32_t f[N_FEATURES]; } vk_features2;
typedef void (*pfn_get_features2)(void *, vk_features2 *);
static pfn_get_features2 g_real_gpdf2, g_real_gpdf2khr;
typedef struct { uint32_t sType; const void *pNext; } vk_base;
typedef tl_pf_device_info vk_device_ci;
typedef int (*pfn_create_device)(void *, const vk_device_ci *, const void *, void **);

static bool dxvk_game(void)
{
    static int known = -1;
    if (known < 0) known = (tl_ld_find_lib("libdxvk_dxgi.so") || tl_ld_find_lib("libdxvk_d3d11.so") || tl_ld_find_lib("libdxvk_d3d9.so")) ? 1 : 0;
    return known == 1;
}

static void claim(uint32_t *f)
{
    if (!dxvk_game()) return;
    static atomic_int said;
    for (size_t i = 0; i < sizeof(k_d3d_features) / sizeof(k_d3d_features[0]); i++) {
        if (!f[k_d3d_features[i]] && !atomic_exchange(&said, 1)) tl_log_line("vulkan: DXVK game: reporting the Direct3D 11 features Metal lacks (geometry shaders, cull distance, pipeline statistics, logic op) as present");
        f[k_d3d_features[i]] = 1;
    }
}


/* Device extensions Direct3D 11 needs that MoltenVK does not offer, listed for DXVK games and taken out again before the device is made:
 * the extension name, its feature struct's sType and how many VkBool32 it holds. */
static const struct { const char *name; uint32_t stype; int bools; } k_fake_ext[] = {
    { "VK_EXT_depth_clip_enable", 1000102000, 1 },     /* depthClipEnable: Metal clips depth unless clamping, which is what D3D asks by default */
    { "VK_EXT_transform_feedback", 1000028000, 2 },    /* transformFeedback, geometryStreams: stream output, rarely used */
    { "VK_EXT_custom_border_color", 1000287002, 2 },   /* customBorderColors, customBorderColorWithoutFormat: samplers fall back to the nearest standard border */
};

/* Single features inside structs MoltenVK does have, claimed the same way: the struct's sType and the VkBool32's index in it. */
static const struct { uint32_t stype; int index; } k_fake_field[] = {
    { 1000286000, 0 },   /* VK_EXT_robustness2 robustBufferAccess2: out-of-bounds buffer reads are not zeroed */
    { 1000286000, 2 },   /* VK_EXT_robustness2 nullDescriptor: unbound slots are left unbound */
};
#define N_FAKE_FIELD (sizeof(k_fake_field) / sizeof(k_fake_field[0]))
#define N_FAKE_EXT (sizeof(k_fake_ext) / sizeof(k_fake_ext[0]))

typedef int (*pfn_enum_dev_ext)(void *, const char *, uint32_t *, vk_ext_props *);
static pfn_enum_dev_ext g_real_enum_dev_ext;

static bool real_dev_ext(void *pd, const char *name)
{
    uint32_t n = 0;
    if (!g_real_enum_dev_ext || g_real_enum_dev_ext(pd, NULL, &n, NULL) != VK_SUCCESS) return false;
    vk_ext_props *p = calloc(n + 1, sizeof(*p));
    bool found = false;
    if (g_real_enum_dev_ext(pd, NULL, &n, p) >= 0) for (uint32_t i = 0; i < n; i++) if (!strcmp(p[i].name, name)) { found = true; break; }
    free(p);
    return found;
}

static int w_vkEnumerateDeviceExtensionProperties(void *pd, const char *layer, uint32_t *count, vk_ext_props *props)
{
    if (!g_real_enum_dev_ext) return -3;
    if (layer || !dxvk_game()) return g_real_enum_dev_ext(pd, layer, count, props);
    uint32_t n = 0;
    int r = g_real_enum_dev_ext(pd, NULL, &n, NULL);
    if (r != VK_SUCCESS) return r;
    vk_ext_props *all = calloc(n + N_FAKE_EXT + 1, sizeof(*all));
    g_real_enum_dev_ext(pd, NULL, &n, all);
    uint32_t total = n;
    for (size_t i = 0; i < N_FAKE_EXT; i++) {
        bool have = false;
        for (uint32_t j = 0; j < n; j++) if (!strcmp(all[j].name, k_fake_ext[i].name)) have = true;
        if (!have) { snprintf(all[total].name, sizeof(all[total].name), "%s", k_fake_ext[i].name); all[total].specVersion = 1; total++; }
    }
    if (!props) { *count = total; free(all); return VK_SUCCESS; }
    uint32_t k = *count < total ? *count : total;
    memcpy(props, all, k * sizeof(*all));
    *count = k;
    free(all);
    return k < total ? VK_INCOMPLETE : VK_SUCCESS;
}

/* In a features query's chain, the fake extensions' structs say yes. */
static void claim_chain(void *pd, vk_features2 *f)
{
    if (!dxvk_game()) return;
    for (vk_base *b = (vk_base *)f->pNext; b; b = (vk_base *)b->pNext) {
        for (size_t i = 0; i < N_FAKE_FIELD; i++)
            if (b->sType == k_fake_field[i].stype) ((uint32_t *)((char *)b + sizeof(vk_base)))[k_fake_field[i].index] = 1;
        for (size_t i = 0; i < N_FAKE_EXT; i++)
            if (b->sType == k_fake_ext[i].stype && !real_dev_ext(pd, k_fake_ext[i].name)) {
                uint32_t *bools = (uint32_t *)((char *)b + sizeof(vk_base));
                for (int j = 0; j < k_fake_ext[i].bools; j++) bools[j] = 1;
            }
    }
}

/* What the device really has for each claimed field, asked once per struct type. */
static bool real_field(void *pd, uint32_t stype, int index)
{
    if (!g_real_gpdf2) return false;
    struct { uint32_t sType; void *pNext; uint32_t b[16]; } probe = { stype, NULL, { 0 } };
    vk_features2 f = { VK_STYPE_FEATURES2, &probe };
    g_real_gpdf2(pd, &f);
    return probe.b[index] != 0;
}

static pfn_get_features g_real_gpdf;
static void w_vkGetPhysicalDeviceFeatures(void *pd, uint32_t *f)
{
    if (g_real_gpdf) g_real_gpdf(pd, f);
    claim(f);
}

static void w_vkGetPhysicalDeviceFeatures2(void *pd, vk_features2 *f) { if (g_real_gpdf2) g_real_gpdf2(pd, f); claim(f->f); claim_chain(pd, f); }
static void w_vkGetPhysicalDeviceFeatures2KHR(void *pd, vk_features2 *f) { if (g_real_gpdf2khr) g_real_gpdf2khr(pd, f); else if (g_real_gpdf2) g_real_gpdf2(pd, f); claim(f->f); claim_chain(pd, f); }

/* Turn off, in what the game enables, every claimed feature the device does not really have. */
static void unclaim(void *pd, uint32_t *f, uint32_t *saved)
{
    uint32_t real[N_FEATURES];
    if (g_real_gpdf) g_real_gpdf(pd, real); else memset(real, 0, sizeof(real));
    for (size_t i = 0; i < sizeof(k_d3d_features) / sizeof(k_d3d_features[0]); i++) {
        int k = k_d3d_features[i];
        saved[i] = f[k];
        if (!real[k]) f[k] = 0;
    }
}
static void reclaim(uint32_t *f, const uint32_t *saved)
{
    for (size_t i = 0; i < sizeof(k_d3d_features) / sizeof(k_d3d_features[0]); i++) f[k_d3d_features[i]] = saved[i];
}


/* ------------------------------------------------------------ null descriptors */
/*
 * DXVK leaves unused vertex-buffer slots bound to VK_NULL_HANDLE, which robustness2's nullDescriptor allows and MoltenVK does not
 * implement (it dereferences the buffer). For DXVK games each device gets one small buffer of zeros, bound in place of a null one:
 * reads from it return zero, which is what a null binding reads.
 */
typedef struct { uint32_t sType; const void *pNext; uint32_t flags; uint64_t size; uint32_t usage; uint32_t sharing; uint32_t nq; const uint32_t *q; } vk_buffer_ci;
typedef struct { uint64_t size, alignment; uint32_t typeBits; } vk_mem_req;
typedef struct { uint32_t sType; const void *pNext; uint64_t size; uint32_t type; } vk_mem_ai;
typedef struct { uint32_t flags, heap; } vk_mem_type;
typedef struct { uint32_t typeCount; vk_mem_type types[32]; uint32_t heapCount; struct { uint64_t size; uint32_t flags; } heaps[16]; } vk_mem_props;
#define NULL_BUF_SIZE (64 * 1024)

static uint64_t g_null_buf;

static void make_null_buffer(void *pd, void *dev)
{
    int (*create)(void *, const vk_buffer_ci *, const void *, uint64_t *) = dlsym(V.lib, "vkCreateBuffer");
    void (*req)(void *, uint64_t, vk_mem_req *) = dlsym(V.lib, "vkGetBufferMemoryRequirements");
    void (*props)(void *, vk_mem_props *) = dlsym(V.lib, "vkGetPhysicalDeviceMemoryProperties");
    int (*alloc)(void *, const vk_mem_ai *, const void *, uint64_t *) = dlsym(V.lib, "vkAllocateMemory");
    int (*bind)(void *, uint64_t, uint64_t, uint64_t) = dlsym(V.lib, "vkBindBufferMemory");
    int (*map)(void *, uint64_t, uint64_t, uint64_t, uint32_t, void **) = dlsym(V.lib, "vkMapMemory");
    if (!create || !req || !props || !alloc || !bind || !map) return;
    vk_buffer_ci ci = { 12, NULL, 0, NULL_BUF_SIZE, 0x80 | 0x40 | 0x20 | 0x10 | 0x8 | 0x4 | 0x2 | 0x1, 0, 0, NULL };
    uint64_t buf = 0, mem = 0;
    if (create(dev, &ci, NULL, &buf) != VK_SUCCESS) return;
    vk_mem_req r; req(dev, buf, &r);
    vk_mem_props mp; memset(&mp, 0, sizeof(mp)); props(pd, &mp);
    uint32_t type = UINT32_MAX;
    for (uint32_t i = 0; i < mp.typeCount && i < 32; i++) if ((r.typeBits & (1u << i)) && (mp.types[i].flags & 0x6) == 0x6) { type = i; break; }
    if (type == UINT32_MAX) return;
    vk_mem_ai ai = { 5, NULL, r.size, type };
    void *ptr = NULL;
    if (alloc(dev, &ai, NULL, &mem) != VK_SUCCESS || bind(dev, buf, mem, 0) != VK_SUCCESS || map(dev, mem, 0, r.size, 0, &ptr) != VK_SUCCESS) return;
    memset(ptr, 0, (size_t)r.size);
    g_null_buf = buf;
    tl_log_line("vulkan: DXVK game: a %d KiB buffer of zeros stands in for null vertex buffers", NULL_BUF_SIZE / 1024);
}

typedef void (*pfn_bind_vb)(void *, uint32_t, uint32_t, const uint64_t *, const uint64_t *);
typedef void (*pfn_bind_vb2)(void *, uint32_t, uint32_t, const uint64_t *, const uint64_t *, const uint64_t *, const uint64_t *);
static pfn_bind_vb g_real_bind_vb;
static pfn_bind_vb2 g_real_bind_vb2, g_real_bind_vb2ext;

static void resolve_binds(void)
{
    if (g_real_bind_vb) return;
    g_real_bind_vb2 = (pfn_bind_vb2)dlsym(V.lib, "vkCmdBindVertexBuffers2");
    g_real_bind_vb2ext = (pfn_bind_vb2)dlsym(V.lib, "vkCmdBindVertexBuffers2EXT");
    g_real_bind_vb = (pfn_bind_vb)dlsym(V.lib, "vkCmdBindVertexBuffers");
}

static bool has_null(uint32_t n, const uint64_t *b) { if (!g_null_buf || !b) return false; for (uint32_t i = 0; i < n; i++) if (!b[i]) return true; return false; }

static void w_vkCmdBindVertexBuffers(void *cmd, uint32_t first, uint32_t n, const uint64_t *bufs, const uint64_t *offs)
{
    resolve_binds();
    if (!has_null(n, bufs) || n > 64) { g_real_bind_vb(cmd, first, n, bufs, offs); return; }
    uint64_t b[64], o[64];
    for (uint32_t i = 0; i < n; i++) { b[i] = bufs[i] ? bufs[i] : g_null_buf; o[i] = bufs[i] ? offs[i] : 0; }
    g_real_bind_vb(cmd, first, n, b, o);
}

static void bind_vb2(pfn_bind_vb2 real, void *cmd, uint32_t first, uint32_t n, const uint64_t *bufs, const uint64_t *offs, const uint64_t *sizes, const uint64_t *strides)
{
    if (!has_null(n, bufs) || n > 64) { real(cmd, first, n, bufs, offs, sizes, strides); return; }
    uint64_t b[64], o[64], z[64];
    for (uint32_t i = 0; i < n; i++) {
        b[i] = bufs[i] ? bufs[i] : g_null_buf; o[i] = bufs[i] ? offs[i] : 0;
        if (sizes) z[i] = bufs[i] ? sizes[i] : NULL_BUF_SIZE;
    }
    real(cmd, first, n, b, o, sizes ? z : NULL, strides);
}
static void w_vkCmdBindVertexBuffers2(void *cmd, uint32_t first, uint32_t n, const uint64_t *b, const uint64_t *o, const uint64_t *z, const uint64_t *s) { resolve_binds(); bind_vb2(g_real_bind_vb2, cmd, first, n, b, o, z, s); }
static void w_vkCmdBindVertexBuffers2EXT(void *cmd, uint32_t first, uint32_t n, const uint64_t *b, const uint64_t *o, const uint64_t *z, const uint64_t *s) { resolve_binds(); bind_vb2(g_real_bind_vb2ext ? g_real_bind_vb2ext : g_real_bind_vb2, cmd, first, n, b, o, z, s); }

/* ------------------------------------------------------------ video memory */
/*
 * MoltenVK reports most of the phone's shared memory as one device-local heap (11 GiB on a 12 GiB phone). DXVK passes that on as
 * the adapter's video memory, and a PC game sizes its texture streaming to it, then streams until iOS kills the app. For DXVK games
 * the heap (and VK_EXT_memory_budget's budget) is reported as a share of what the app may really use: TL_VK_HEAP_MB overrides it.
 */
typedef void (*pfn_mem_props)(void *, vk_mem_props *);
typedef struct { uint32_t sType; void *pNext; vk_mem_props p; } vk_mem_props2;
typedef struct { uint32_t sType; void *pNext; uint64_t budget[16], usage[16]; } vk_mem_budget;
#define VK_STYPE_MEM_PROPS2 1000059006
#define VK_STYPE_MEM_BUDGET 1000237000
static pfn_mem_props g_real_mem_props;
static void (*g_real_mem_props2)(void *, vk_mem_props2 *), (*g_real_mem_props2khr)(void *, vk_mem_props2 *);

static uint64_t heap_cap(void)
{
    static uint64_t cap;
    if (cap) return cap;
    const char *e = getenv("TL_VK_HEAP_MB");
    if (e && atoi(e) > 0) cap = (uint64_t)atoi(e) << 20;
    else {
#if TARGET_OS_IOS
        uint64_t avail = os_proc_available_memory();
#else
        uint64_t avail = 6ull << 30;
#endif
        cap = avail * 3 / 10;
        if (cap < (768ull << 20)) cap = 768ull << 20;
        cap &= ~((256ull << 20) - 1);
    }
    tl_log_line("vulkan: DXVK game: device-local heaps reported as at most %llu MiB", (unsigned long long)(cap >> 20));
    return cap;
}

static void cap_heaps(vk_mem_props *p)
{
    if (!dxvk_game()) return;
    for (uint32_t i = 0; i < p->heapCount && i < 16; i++) if ((p->heaps[i].flags & 1) && p->heaps[i].size > heap_cap()) p->heaps[i].size = heap_cap();
}

static void cap_chain(vk_mem_props2 *p)
{
    cap_heaps(&p->p);
    if (!dxvk_game()) return;
    for (vk_base *b = p->pNext; b; b = (vk_base *)b->pNext)
        if (b->sType == VK_STYPE_MEM_BUDGET) {
            vk_mem_budget *m = (vk_mem_budget *)b;
            for (uint32_t i = 0; i < p->p.heapCount && i < 16; i++) if (m->budget[i] > p->p.heaps[i].size) m->budget[i] = p->p.heaps[i].size;
        }
}

static void w_vkGetPhysicalDeviceMemoryProperties(void *pd, vk_mem_props *p) { if (g_real_mem_props) g_real_mem_props(pd, p); cap_heaps(p); }
static void w_vkGetPhysicalDeviceMemoryProperties2(void *pd, vk_mem_props2 *p) { if (g_real_mem_props2) g_real_mem_props2(pd, p); cap_chain(p); }
static void w_vkGetPhysicalDeviceMemoryProperties2KHR(void *pd, vk_mem_props2 *p)
{
    if (g_real_mem_props2khr) g_real_mem_props2khr(pd, p); else if (g_real_mem_props2) g_real_mem_props2(pd, p);
    cap_chain(p);
}

static pfn_create_device g_real_create_device;
static int w_vkCreateDevice(void *pd, const vk_device_ci *ci, const void *alloc, void **out)
{
    if (!g_real_create_device) return -3;
    if (!dxvk_game()) {
        int result = tl_pf_create_device(pd, ci, alloc, out, g_real_create_device, g_real_enum_dev_ext);
        if (result == VK_SUCCESS && out && *out) {
            tl_dp_device(*out);
            typedef void (*properties_fn)(void *, void *);
            properties_fn properties = V.lib ? (properties_fn)dlsym(V.lib, "vkGetPhysicalDeviceProperties") : NULL;
            if (properties) {
                union { max_align_t align; uint8_t bytes[4096]; } props = {0};
                properties(pd, props.bytes);
                uint32_t vendor, id;
                memcpy(&vendor, props.bytes + 8, 4); memcpy(&id, props.bytes + 12, 4);
                tl_pc_device(*out, vendor, id, props.bytes + 276);
            }
        }
        return result;
    }
    uint32_t base[N_FEATURES], saved1[8], saved2[8];
    vk_device_ci copy = *ci;
    if (ci->features) { memcpy(base, ci->features, sizeof(base)); unclaim(pd, base, saved1); copy.features = base; }
    /* features may also come as a VkPhysicalDeviceFeatures2 in the chain; it is the game's memory, so edit it for the call and put it back */
    vk_features2 *f2 = NULL;
    for (const vk_base *b = ci->pNext; b; b = b->pNext) if (b->sType == VK_STYPE_FEATURES2) { f2 = (vk_features2 *)b; break; }
    if (f2) unclaim(pd, f2->f, saved2);
    /* the fake extensions out of the list, and their structs out of the chain (relinked for the call, restored after) */
    const char **ext = calloc(ci->extCount + 1, sizeof(char *));
    uint32_t n = 0;
    for (uint32_t i = 0; i < ci->extCount; i++) {
        bool fake = false;
        for (size_t j = 0; j < N_FAKE_EXT; j++) if (!strcmp(ci->exts[i], k_fake_ext[j].name) && !real_dev_ext(pd, k_fake_ext[j].name)) fake = true;
        if (fake) tl_log_line("vulkan: device extension %s was only claimed; left out", ci->exts[i]); else ext[n++] = ci->exts[i];
    }
    copy.extCount = n; copy.exts = ext;
    /* claimed fields the device lacks, off for the call */
    struct { uint32_t *at; uint32_t was; } off[16]; int noff = 0;
    for (vk_base *b = (vk_base *)copy.pNext; b; b = (vk_base *)b->pNext)
        for (size_t j = 0; j < N_FAKE_FIELD; j++)
            if (b->sType == k_fake_field[j].stype && noff < 16) {
                uint32_t *at = (uint32_t *)((char *)b + sizeof(vk_base)) + k_fake_field[j].index;
                if (*at && !real_field(pd, k_fake_field[j].stype, k_fake_field[j].index)) { off[noff].at = at; off[noff].was = *at; noff++; *at = 0; }
            }
    struct { vk_base *prev; const void *was; } cut[16]; int ncut = 0;
    vk_base *prev = (vk_base *)&copy;
    for (vk_base *b = (vk_base *)copy.pNext; b; b = (vk_base *)b->pNext) {
        bool fake = false;
        for (size_t j = 0; j < N_FAKE_EXT; j++) if (b->sType == k_fake_ext[j].stype && !real_dev_ext(pd, k_fake_ext[j].name)) fake = true;
        if (fake && ncut < 16) { cut[ncut].prev = prev; cut[ncut].was = prev->pNext; ncut++; prev->pNext = b->pNext; continue; }
        prev = b;
    }
    int r = g_real_create_device(pd, &copy, alloc, out);
    for (int i = ncut - 1; i >= 0; i--) cut[i].prev->pNext = cut[i].was;
    for (int i = 0; i < noff; i++) *off[i].at = off[i].was;
    free(ext);
    if (f2) reclaim(f2->f, saved2);
    tl_log_line("vulkan: vkCreateDevice(%u extensions) -> %d", ci->extCount, r);
    if (r == VK_SUCCESS && out && *out) {
        tl_dp_device(*out);
        make_null_buffer(pd, *out);
    }
    return r;
}

static void resolve_feature_hooks(void *instance)
{
    if (!g_real_gpdf) g_real_gpdf = (pfn_get_features)V.gipa(instance, "vkGetPhysicalDeviceFeatures");
    if (!g_real_gpdf2) g_real_gpdf2 = (pfn_get_features2)V.gipa(instance, "vkGetPhysicalDeviceFeatures2");
    if (!g_real_gpdf2khr) g_real_gpdf2khr = (pfn_get_features2)V.gipa(instance, "vkGetPhysicalDeviceFeatures2KHR");
    if (!g_real_create_device) g_real_create_device = (pfn_create_device)V.gipa(instance, "vkCreateDevice");
    if (!g_real_enum_dev_ext) g_real_enum_dev_ext = (pfn_enum_dev_ext)V.gipa(instance, "vkEnumerateDeviceExtensionProperties");
    if (!g_real_mem_props) g_real_mem_props = (pfn_mem_props)V.gipa(instance, "vkGetPhysicalDeviceMemoryProperties");
    if (!g_real_mem_props2) g_real_mem_props2 = (void (*)(void *, vk_mem_props2 *))V.gipa(instance, "vkGetPhysicalDeviceMemoryProperties2");
    if (!g_real_mem_props2khr) g_real_mem_props2khr = (void (*)(void *, vk_mem_props2 *))V.gipa(instance, "vkGetPhysicalDeviceMemoryProperties2KHR");
}

static void *w_vkGetInstanceProcAddr(void *instance, const char *name);
static void *w_vkGetDeviceProcAddr(void *device, const char *name);

static const struct { const char *name; void *fn; } k_over[] = {
    { "vkGetInstanceProcAddr", w_vkGetInstanceProcAddr },
    { "vkGetDeviceProcAddr", w_vkGetDeviceProcAddr },
    { "vkCreateInstance", w_vkCreateInstance },
    { "vkEnumerateInstanceExtensionProperties", w_vkEnumerateInstanceExtensionProperties },
    { "vkCreateAndroidSurfaceKHR", w_vkCreateAndroidSurfaceKHR },
    { "vkQueuePresentKHR", w_vkQueuePresentKHR },
    { "vkQueueSubmit", w_vkQueueSubmit },
    { "vkCreateImage", w_vkCreateImage },
    { "vkCmdBeginRenderPass", w_vkCmdBeginRenderPass },
    { "vkGetDeviceQueue", w_vkGetDeviceQueue },
    { "vkGetDeviceQueue2", w_vkGetDeviceQueue2 },
    { "vkCreatePipelineCache", w_vkCreatePipelineCache },
    { "vkGetPipelineCacheData", w_vkGetPipelineCacheData },
    { "vkMergePipelineCaches", w_vkMergePipelineCaches },
    { "vkDestroyPipelineCache", w_vkDestroyPipelineCache },
    { "vkDestroyDevice", w_vkDestroyDevice },
    { "vkCreateShaderModule", w_vkCreateShaderModule },
    { "vkDestroyShaderModule", w_vkDestroyShaderModule },
    { "vkCreateGraphicsPipelines", w_vkCreateGraphicsPipelines },
    { "vkCreateComputePipelines", w_vkCreateComputePipelines },
    { "vkCreateSwapchainKHR", w_vkCreateSwapchainKHR },
    { "vkAcquireNextImageKHR", w_vkAcquireNextImageKHR },
    { "vkGetPhysicalDeviceFeatures", w_vkGetPhysicalDeviceFeatures },
    { "vkGetPhysicalDeviceFeatures2", w_vkGetPhysicalDeviceFeatures2 },
    { "vkGetPhysicalDeviceFeatures2KHR", w_vkGetPhysicalDeviceFeatures2KHR },
    { "vkCreateDevice", w_vkCreateDevice },
    { "vkGetPhysicalDeviceMemoryProperties", w_vkGetPhysicalDeviceMemoryProperties },
    { "vkGetPhysicalDeviceMemoryProperties2", w_vkGetPhysicalDeviceMemoryProperties2 },
    { "vkGetPhysicalDeviceMemoryProperties2KHR", w_vkGetPhysicalDeviceMemoryProperties2KHR },
    { "vkEnumerateDeviceExtensionProperties", w_vkEnumerateDeviceExtensionProperties },
    { "vkCmdBindVertexBuffers", w_vkCmdBindVertexBuffers },
    { "vkCmdBindVertexBuffers2", w_vkCmdBindVertexBuffers2 },
    { "vkCmdBindVertexBuffers2EXT", w_vkCmdBindVertexBuffers2EXT },
};

static void *overridden(const char *name)
{
    /* Default-off inventory does not interpose per-render-pass calls at all. */
    if ((!strcmp(name,"vkCreateImage") || !strcmp(name,"vkCmdBeginRenderPass")) && !tl_ri_active()) return NULL;
    for (size_t i = 0; i < sizeof(k_over) / sizeof(k_over[0]); i++) if (!strcmp(k_over[i].name, name)) return k_over[i].fn;
    return NULL;
}

static void *w_vkGetInstanceProcAddr(void *instance, const char *name)
{
    if (!name || !vk_ready()) return NULL;
    if (instance) resolve_feature_hooks(instance);
    void *fn = overridden(name);
    if (fn) return fn;
    fn = V.gipa(instance, name);
    LOG("vulkan: vkGetInstanceProcAddr(%s) -> %p", name, fn);
    return fn;
}

static void *w_vkGetDeviceProcAddr(void *device, const char *name)
{
    if (!name || !vk_ready()) return NULL;
    void *fn = overridden(name);
    if (fn) return fn;
    typedef void *(*pfn_gdpa)(void *, const char *);
    static pfn_gdpa mvk_gdpa;
    if (!mvk_gdpa) mvk_gdpa = V.lib ? (pfn_gdpa)dlsym(V.lib, "vkGetDeviceProcAddr") : NULL;
    return mvk_gdpa ? mvk_gdpa(device, name) : NULL;
}

void *tl_vk_resolve(const char *name)
{
    if (!vk_ready()) return NULL;
    void *fn = overridden(name);
    if (fn) return fn;
    return V.lib ? dlsym(V.lib, name) : NULL;
}

unsigned long tl_vk_frames_presented(void) { return atomic_load(&V.frames); }
