/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef PODTHINGS_BOOT_H
#define PODTHINGS_BOOT_H

#include <stdbool.h>

/* No persistent boot preference is changed by these operations. */
bool podthings_request_official_boot(void);
bool podthings_cancel_official_boot(void);
/* 1: consumed and flushed; 0: absent; -1: invalid or could not be cleared. */
int podthings_consume_official_boot(void);

enum podthings_boot_target {
    PODTHINGS_BOOT_OS = 0,
    PODTHINGS_BOOT_APPLE = 1,
    PODTHINGS_BOOT_ROCKBOX = 2,
    PODTHINGS_BOOT_DISK = 3 /* One-time only; never a saved default. */
};
int podthings_boot_default(void);
bool podthings_set_boot_default(int target);
/* Hold always selects PodThings OS for either alternative default. */
int podthings_boot_select(int target, bool hold);
int podthings_boot_resolve(int target, bool hold, int official_once, int rockbox_once);
bool podthings_request_rockbox_boot(void);
bool podthings_cancel_rockbox_boot(void);
int podthings_consume_rockbox_boot(void);
bool podthings_request_disk_boot(void);
bool podthings_cancel_disk_boot(void);
int podthings_consume_disk_boot(void);
int podthings_boot_resolve_disk(int target, bool hold, int official_once,
                               int rockbox_once, int disk_once);

#endif
