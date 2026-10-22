/* SPDX-License-Identifier: GPL-2.0-or-later */
#define _POSIX_C_SOURCE 200809L
#include "husk-tl-ue4-graphics.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static bool sharp;
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

void husk_ue4_set_sharp_graphics(bool enabled) { sharp = enabled; }

char *tl_ue4_graphics_command_line(const char *base)
{
    if (!base) base = "";
    if (!sharp) return strdup(base);
    const char prefix[] = " -ini:Engine:";
    const char section[] = "[SystemSettings]:";
    size_t bytes = strlen(base) + sizeof(prefix);
    for (size_t i = 0; i < sizeof(values) / sizeof(values[0]); i++)
        bytes += strlen(section) + strlen(values[i]) + 1;
    char *out = malloc(bytes);
    if (!out) return NULL;
    strcpy(out, base); strcat(out, prefix);
    for (size_t i = 0; i < sizeof(values) / sizeof(values[0]); i++) {
        if (i) strcat(out, ",");
        strcat(out, section); strcat(out, values[i]);
    }
    return out;
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
        for (size_t i = 0; i < sizeof(values) / sizeof(values[0]); i++)
            ok = fprintf(f, "%s\n", values[i]) >= 0 && ok;
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
