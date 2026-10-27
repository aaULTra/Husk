/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HUSK_TL_NATIVE_ARCHIVE_H
#define HUSK_TL_NATIVE_ARCHIVE_H
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Optional native driver ABI; paths are copied synchronously. No Vulkan objects
 * or descriptor addresses are persisted; Metal owns the archive's format. */
#define TL_NATIVE_ARCHIVE_ABI 2u
enum { TL_NA_VERIFY_REQUIREMENT=1u };
typedef struct {uint32_t version,size,enabled,flags;const char *directory;} tl_na_config;
typedef struct {
 uint32_t version,size,requested,supported,preparing,pending;
 uint64_t descriptors_captured,descriptors_dropped,archive_attachments,archive_fallbacks,prepare_calls,prepared,prepare_failures;
 uint64_t restored_bytes,saved_bytes,read_failures,write_failures,prepare_ns,evicted_files,evicted_bytes;
 uint32_t verification_requested,reserved;
 uint64_t verification_attempts,archive_requirement_satisfied,verification_failures;
 int64_t last_verification_error_code;
 char last_verification_error_domain[64];
} tl_na_stats;
typedef struct {
 uint32_t version,size,pending,capacity;
 uint64_t eligible,replaced,rejected,requirement_satisfied_skips,highest_pending_ns,lowest_pending_ns;
} tl_na_priority;
bool tl_vk_archive_priority(tl_na_priority*);
typedef struct {
 int (*configure)(const tl_na_config*);int (*snapshot)(tl_na_stats*);
 int (*prepare)(void);void (*forget)(void);
} tl_npa_api;
void tl_npa_set_api(tl_npa_api api);
bool tl_npa_requested(void);
void tl_npa_configure(const char *project,const char *directory,bool sharp);
void tl_npa_device(void *device);
void tl_npa_forget(void *device);
void husk_ue4_set_native_archive(int mode);
void husk_ue4_set_native_archive_verification(bool enabled);
void tl_vk_archive_configure(const char *project,const char *directory);
bool tl_vk_archive_begin_prepare(void);
int tl_vk_archive_prepare(void);
bool tl_vk_archive_preparing(void);
void tl_vk_archive_snapshot(tl_na_stats *out);
#ifdef __cplusplus
}
#endif
#endif
