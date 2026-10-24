/* SPDX-License-Identifier: GPL-2.0-or-later */
#define _POSIX_C_SOURCE 200809L
#include "husk-tl-ue4-graphics.h"
#include <errno.h>
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <unistd.h>

static bool sharp;
static bool efficient;
static int frame_limit = 60;
double tl_ue4_resolution_fraction(int width, int height, bool tablet, int percent)
{
    if (width <= 0 || height <= 0) return 1.0;
    if (percent >= 65 && percent <= 100 && percent % 5 == 0)
        return percent / 100.0;
    /* Larger tablets retain more spatial detail. Phones use a smaller pixel
     * budget even when their native display is very dense. Current dimensions
     * distinguish a smaller outer display from a larger inner display without
     * guessing model identifiers or depending on undocumented fold APIs. */
    int longer = width > height ? width : height;
    int shorter = width > height ? height : width;
    double long_budget = tablet ? 2304.0 : 2048.0;
    double short_budget = tablet ? 1600.0 : 1280.0;
    double fraction = long_budget / longer;
    if (short_budget / shorter < fraction) fraction = short_budget / shorter;
    return fraction < 1.0 ? fraction : 1.0;
}
static const char begin[] = "; BEGIN HUSK SHARP GRAPHICS v1\n";
static const char end[] = "; END HUSK SHARP GRAPHICS v1\n";
/* Runtime quality CVars only: do not change feature level, shader permutations,
 * HDR, texture format, or disable streaming / remove its memory budget. Values
 * are requests; a game's cooked assets and renderer still limit the result. */
static const char *const values[] = {
    "sg.ViewDistanceQuality=3", "sg.AntiAliasingQuality=3",
    "sg.ShadowQuality=3", "sg.PostProcessQuality=3",
    "sg.TextureQuality=3", "sg.EffectsQuality=3", "sg.FoliageQuality=3",
    "r.MobileContentScaleFactor=0", "r.ScreenPercentage=100",
    "r.DynamicRes.OperationMode=0", "r.MaxAnisotropy=16",
    "r.Streaming.MipBias=0", "r.ViewDistanceScale=1", "r.DetailMode=2",
    "r.PostProcessAAQuality=4", "r.ShadowQuality=5",
    "r.Shadow.MaxResolution=2048", "r.Shadow.CSM.MaxCascades=4",
    "r.MotionBlurQuality=0", "r.DepthOfFieldQuality=0",
    "r.SceneColorFringeQuality=0"
};

/* Keep native geometry/texture sharpness, spend less on shadows and effects.
 * Keep the same marker so switching presets replaces the previous block. */
static const char *const efficient_values[] = {
    "sg.ViewDistanceQuality=2", "sg.AntiAliasingQuality=3",
    "sg.ShadowQuality=2", "sg.PostProcessQuality=1",
    "sg.TextureQuality=3", "sg.EffectsQuality=2", "sg.FoliageQuality=2",
    "r.MobileContentScaleFactor=0", "r.ScreenPercentage=100",
    "r.DynamicRes.OperationMode=0", "r.MaxAnisotropy=8",
    "r.Streaming.MipBias=0", "r.ViewDistanceScale=1", "r.DetailMode=2",
    "r.PostProcessAAQuality=4", "r.ShadowQuality=3",
    "r.Shadow.MaxResolution=1024", "r.Shadow.CSM.MaxCascades=2",
    "r.MotionBlurQuality=0", "r.DepthOfFieldQuality=0",
    "r.SceneColorFringeQuality=0"
};
_Static_assert(sizeof(values) == sizeof(efficient_values), "preset size mismatch");
#define BASE_VALUE_COUNT (sizeof(values) / sizeof(values[0]))
#define VALUE_COUNT (BASE_VALUE_COUNT + (efficient ? 1u : 0u))
static const char *value_at(size_t i)
{
    if (efficient && i == BASE_VALUE_COUNT)
        return frame_limit == 30 ? "t.MaxFPS=30" : "t.MaxFPS=60";
    return efficient ? efficient_values[i] : values[i];
}

void husk_ue4_set_efficiency(bool enabled, int fps)
{
    efficient = enabled;
    frame_limit = fps == 30 ? 30 : 60;
}
bool tl_ue4_efficiency_enabled(void) { return sharp && efficient; }
int tl_ue4_effective_frame_limit(int thermal_state)
{
    if (!tl_ue4_efficiency_enabled()) return 0;
    if (thermal_state >= 3) return 20;
    if (thermal_state >= 2) return 30;
    return frame_limit;
}
/* Pure monotonic scheduling: no busy wait or catch-up burst after slow frames
 * or a resume. Call once per present, on that present thread. */
int64_t tl_ue4_frame_delay_ns(int64_t now, int fps, int64_t *deadline)
{
    if (fps <= 0) { *deadline = 0; return 0; }
    int64_t interval = 1000000000LL / fps;
    if (!*deadline || now >= *deadline || *deadline - now > interval) {
        *deadline = now + interval;
        return 0;
    }
    int64_t delay = *deadline - now;
    *deadline += interval;
    return delay;
}

void husk_ue4_set_sharp_graphics(bool enabled) { sharp = enabled; }
bool tl_ue4_sharp_graphics_enabled(void) { return sharp; }

/* FParse::Value takes the first matching mcsf= token. Remove old copies, while
 * preserving quoted project paths and unrelated options, before adding ours. */
static char *without_mcsf(const char *base)
{
    char *out = malloc(strlen(base) + 1);
    if (!out) return NULL;
    size_t used = 0;
    for (const char *p = base; *p;) {
        const char *start = p;
        while (isspace((unsigned char)*p)) p++;
        memcpy(out + used, start, (size_t)(p - start)); used += (size_t)(p - start);
        if (!*p) break;
        start = p;
        bool quoted = false;
        while (*p && (quoted || !isspace((unsigned char)*p))) {
            if (*p == '"' && (p == start || p[-1] != '\\')) quoted = !quoted;
            p++;
        }
        const char *key = start;
        if (*key == '"') key++;
        if (*key == '-') key++;
        if ((size_t)(p - key) < 5 || strncasecmp(key, "mcsf=", 5)) {
            memcpy(out + used, start, (size_t)(p - start)); used += (size_t)(p - start);
        }
    }
    while (used && isspace((unsigned char)out[used - 1])) used--;
    out[used] = 0;
    return out;
}

char *tl_ue4_graphics_command_line(const char *base)
{
    if (!base) base = "";
    if (!sharp) return strdup(base);
    char *clean = without_mcsf(base);
    if (!clean) return NULL;
    const char prefix[] = " -mcsf=0 -ini:Engine:";
    const char section[] = "[SystemSettings]:";
    size_t bytes = strlen(clean) + sizeof(prefix);
    for (size_t i = 0; i < VALUE_COUNT; i++)
        bytes += strlen(section) + strlen(value_at(i)) + 1;
    char *out = malloc(bytes);
    if (!out) { free(clean); return NULL; }
    strcpy(out, clean); free(clean); strcat(out, prefix);
    for (size_t i = 0; i < VALUE_COUNT; i++) {
        if (i) strcat(out, ",");
        strcat(out, section); strcat(out, value_at(i));
    }
    return out;
}

static bool is_command_file(const char *name)
{
    if (!name) return false;
    const char *last = strrchr(name, '/');
    return !strcasecmp(last ? last + 1 : name, "UE4CommandLine.txt");
}

char *tl_ue4_graphics_command_asset(const char *name, const void *data, size_t length)
{
    if (!sharp || !is_command_file(name) || length >= 16384 || (length && !data)) return NULL;
    /* Embedded NULs are not command-line text. Never truncate a project path. */
    if (length && memchr(data, 0, length)) return NULL;
    char *base = malloc(length + 1);
    if (!base) return NULL;
    if (length) memcpy(base, data, length);
    base[length] = 0;
    char *out = tl_ue4_graphics_command_line(base);
    free(base);
    /* UE4's InitCommandLine uses a 16 KiB buffer. Refuse a partial override. */
    if (out && strlen(out) >= 16383) { free(out); return NULL; }
    return out;
}

char *tl_ue4_graphics_command_file(const char *path)
{
    if (!sharp || !is_command_file(path)) return NULL;
    FILE *f = fopen(path, "rb");
    if (!f) return NULL; /* missing override must not erase the packaged project arguments */
    char line[16384];
    char *got = fgets(line, sizeof(line), f);
    bool failed = ferror(f) || (got && !strchr(line, '\n') && !feof(f));
    fclose(f);
    if (failed) return NULL;
    return tl_ue4_graphics_command_asset(path, got ? line : "", got ? strlen(line) : 0);
}

static bool make_parents(char *path)
{
    for (char *p = path + 1; *p; p++) if (*p == '/') {
        *p = 0;
        int rc = mkdir(path, 0700), saved = errno;
        *p = '/';
        if (rc && saved != EEXIST) return false;
    }
    return true;
}

static bool update_ini(const char *root, const char *project, const char *platform)
{
    char path[2048], tmp[2100];
    int n = snprintf(path, sizeof(path), "%s/UE4Game/%s/%s/Saved/Config/%s/Engine.ini", root, project, project, platform);
    if (n < 0 || (size_t)n >= sizeof(path)) return false;
    FILE *f = fopen(path, "rb");
    char *contents = NULL;
    size_t len = 0;
    if (f) {
        if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return false; }
        long size = ftell(f);
        if (size < 0 || size > 16 * 1024 * 1024 || fseek(f, 0, SEEK_SET) != 0) { fclose(f); return false; }
        contents = malloc((size_t)size + 1);
        if (!contents) { fclose(f); return false; }
        len = fread(contents, 1, (size_t)size, f);
        bool failed = len != (size_t)size || ferror(f);
        fclose(f);
        if (failed || memchr(contents, 0, len)) { free(contents); return false; }
        contents[len] = 0;
    } else {
        if (errno != ENOENT) return false;
        if (!sharp) return true;
        contents = calloc(1, 1);
        if (!contents) return false;
    }
    bool removed = false;
    char *first;
    while ((first = strstr(contents, begin))) {
        char *last = strstr(first + strlen(begin), end);
        /* Refuse to truncate unrelated content if a block has been edited. */
        if (!last) { free(contents); return false; }
        last += strlen(end);
        /* The leading newline belongs to our block, not the original file. */
        char *start = first > contents && first[-1] == '\n' ? first - 1 : first;
        memmove(start, last, strlen(last) + 1);
        len = strlen(contents);
        removed = true;
    }
    if (!sharp && !removed) { free(contents); return true; }
    if (!sharp && !len) { free(contents); return unlink(path) == 0 || errno == ENOENT; }
    if (!make_parents(path)) { free(contents); return false; }
    snprintf(tmp, sizeof(tmp), "%s.husk-XXXXXX", path);
    int fd = mkstemp(tmp);
    if (fd < 0) { free(contents); return false; }
    f = fdopen(fd, "wb");
    if (!f) { close(fd); unlink(tmp); free(contents); return false; }
    bool ok = fwrite(contents, 1, len, f) == len;
    free(contents);
    if (sharp) {
        ok = fprintf(f, "\n%s[SystemSettings]\n", begin) >= 0 && ok;
        for (size_t i = 0; i < VALUE_COUNT; i++)
            ok = fprintf(f, "%s\n", value_at(i)) >= 0 && ok;
        ok = fputs(end, f) >= 0 && ok;
    }
    if (fflush(f) || fsync(fd)) ok = false;
    if (fclose(f)) ok = false;
    if (ok && rename(tmp, path) == 0) return true;
    unlink(tmp);
    return false;
}

bool tl_ue4_graphics_prepare(const char *internal_dir, const char *external_dir, const char *project)
{
    if (!project || !*project || !strcmp(project, ".") || !strcmp(project, "..")) return false;
    for (const char *p = project; *p; p++) {
        unsigned char c = (unsigned char)*p;
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '_' || c == '-' || c == '.')) return false;
    }
    if (!internal_dir || !*internal_dir || !external_dir || !*external_dir) return false;
    const char *roots[] = { internal_dir, external_dir };
    const char *platforms[] = { "Android", "Android_Vulkan" };
    bool ok = true;
    for (size_t r = 0; r < 2; r++) for (size_t p = 0; p < 2; p++)
        if (!update_ini(roots[r], project, platforms[p])) ok = false;
    return ok;
}
