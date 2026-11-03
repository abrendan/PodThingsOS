/* SPDX-License-Identifier: GPL-2.0-or-later
 *
 * One-use handoff shared by the firmware and its matching bootloaders.
 * Clear and flush the request BEFORE launching Apple's firmware. Never
 * launch it on an invalid request or a failed clear.
 */
#include "config.h"
#include <errno.h>
#include <string.h>
#include "file.h"
#include "storage.h"
#include "rbpaths.h"
#include "podthings_boot.h"
#if (defined(IPOD_VIDEO) || defined(IPOD_COLOR)) && !defined(SIMULATOR)
#include "ata.h"
#endif

#define OFFICIAL_BOOT_REQUEST ROCKBOX_DIR "/boot-official-once"
static const char request_magic[] = "PodThings OS: official firmware once\n";
#define ROCKBOX_BOOT_REQUEST ROCKBOX_DIR "/boot-rockbox-once"
#define BOOT_PREFERENCE ROCKBOX_DIR "/boot-default"
#define BOOT_PREFERENCE_TEMP ROCKBOX_DIR "/boot-default.tmp"
static const char rockbox_magic[] = "PodThings OS: Rockbox firmware once\n";
#define DISK_BOOT_REQUEST ROCKBOX_DIR "/boot-disk-once"
static const char disk_magic[] = "Disk\n";

static int flush_request_storage(void)
{
#ifdef HAVE_STORAGE_FLUSH
    return storage_flush();
#else
    /* FAT close/remove synchronously commit filesystem metadata. Targets
     * without this optional FTL hook flush the ATA cache at standby:
     * normal shutdown does this for the writer; cancellation does it below. */
    return 0;
#endif
}

static bool cancel_request(const char *path)
{
    int removed = remove(path);
    int flushed = flush_request_storage();
#if (defined(IPOD_VIDEO) || defined(IPOD_COLOR)) && !defined(SIMULATOR)
    /* The Video loader still has to read Apple's image. Flush the deletion
     * while keeping the disk awake; do not enter standby then reset it. */
    int persisted = ata_flush_for_handoff();
    return removed == 0 && flushed == 0 && persisted == 0;
#elif defined(IPOD_NANO3G) && !defined(SIMULATOR)
    /* Nano commits its FTL through storage_flush(); it has no ATA standby
     * implementation and must remain mounted for the next firmware read. */
    return removed == 0 && flushed == 0;
#else
    /* Persist deletion even on cancellation or a malformed request, not
     * just on a successful handoff. Both ATA drivers flush at standby. */
    storage_sleepnow();
    return removed == 0 && flushed == 0 && !storage_disk_is_active();
#endif
}

static bool write_request(const char *path, const char *magic, size_t length)
{
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0666);
    if (fd < 0)
        return false;

    bool ok = write(fd, magic, length) == (ssize_t)length;
    if (fsync(fd) < 0)
        ok = false;
    if (close(fd) < 0)
        ok = false;
    if (flush_request_storage() != 0)
        ok = false;

    if (!ok)
        cancel_request(path);
    return ok;
}

static int consume_request(const char *path, const char *magic, size_t length)
{
    int fd = open(path, O_RDONLY);
    if (fd < 0)
        return errno == ENOENT ? 0 : -1;

    /* Read one extra byte so a longer, malformed file is not accepted. */
    char data[64];
    ssize_t count = read(fd, data, sizeof(data));
    bool valid = count == (ssize_t)length && memcmp(data, magic, length) == 0;
    if (close(fd) < 0)
        valid = false;
    if (!cancel_request(path))
        return -1;

    return valid ? 1 : -1;
}

bool podthings_cancel_official_boot(void)
{
    return cancel_request(OFFICIAL_BOOT_REQUEST);
}

bool podthings_request_official_boot(void)
{
    return write_request(OFFICIAL_BOOT_REQUEST, request_magic, sizeof(request_magic)-1);
}

int podthings_consume_official_boot(void)
{
    return consume_request(OFFICIAL_BOOT_REQUEST, request_magic, sizeof(request_magic)-1);
}

bool podthings_cancel_rockbox_boot(void)
{
    return cancel_request(ROCKBOX_BOOT_REQUEST);
}

bool podthings_request_rockbox_boot(void)
{
    return write_request(ROCKBOX_BOOT_REQUEST, rockbox_magic, sizeof(rockbox_magic)-1);
}

int podthings_consume_rockbox_boot(void)
{
    return consume_request(ROCKBOX_BOOT_REQUEST, rockbox_magic, sizeof(rockbox_magic)-1);
}

bool podthings_request_disk_boot(void)
{
    return write_request(DISK_BOOT_REQUEST, disk_magic, sizeof(disk_magic)-1);
}

bool podthings_cancel_disk_boot(void)
{
    return cancel_request(DISK_BOOT_REQUEST);
}

int podthings_consume_disk_boot(void)
{
    return consume_request(DISK_BOOT_REQUEST, disk_magic, sizeof(disk_magic)-1);
}

int podthings_boot_resolve_disk(int target, bool hold, int official_once,
                               int rockbox_once, int disk_once)
{
    if (hold && target != PODTHINGS_BOOT_OS)
        return PODTHINGS_BOOT_OS;
    if (official_once < 0 || rockbox_once < 0 || disk_once < 0 ||
        (official_once > 0) + (rockbox_once > 0) + (disk_once > 0) > 1)
        return PODTHINGS_BOOT_OS;
    if (disk_once > 0)
        return PODTHINGS_BOOT_DISK;
    if (official_once > 0)
        return PODTHINGS_BOOT_APPLE;
    if (rockbox_once > 0)
        return PODTHINGS_BOOT_ROCKBOX;
    return podthings_boot_select(target, hold);
}

int podthings_boot_default(void)
{
    char data[3];
    int fd = open(BOOT_PREFERENCE, O_RDONLY);
    if (fd < 0)
        return PODTHINGS_BOOT_OS;
    ssize_t count = read(fd, data, sizeof(data));
    bool closed = close(fd) == 0;
    if (!closed || count != 2 || data[1] != '\n' ||
        data[0] < '0' || data[0] > '2')
        return PODTHINGS_BOOT_OS;
    return data[0] - '0';
}

bool podthings_set_boot_default(int target)
{
    if (target < PODTHINGS_BOOT_OS || target > PODTHINGS_BOOT_ROCKBOX)
        return false;
    /* Never truncate the saved preference on an interrupted/failed write. */
    char data[2] = { '0' + target, '\n' };
    int fd = open(BOOT_PREFERENCE_TEMP, O_WRONLY | O_CREAT | O_TRUNC, 0666);
    if (fd < 0)
        return false;
    bool ok = write(fd, data, sizeof(data)) == sizeof(data);
    if (fsync(fd) < 0)
        ok = false;
    if (close(fd) < 0)
        ok = false;
    if (ok && rename(BOOT_PREFERENCE_TEMP, BOOT_PREFERENCE) < 0)
        ok = false;
    if (!ok)
        remove(BOOT_PREFERENCE_TEMP);
    if (flush_request_storage() != 0)
        ok = false;
    return ok;
}

int podthings_boot_select(int target, bool hold)
{
    if (target < PODTHINGS_BOOT_OS || target > PODTHINGS_BOOT_ROCKBOX)
        target = PODTHINGS_BOOT_OS;
    return hold ? (target == PODTHINGS_BOOT_OS ? PODTHINGS_BOOT_APPLE :
                   PODTHINGS_BOOT_OS) : target;
}

int podthings_boot_resolve(int target, bool hold, int official_once, int rockbox_once)
{
    return podthings_boot_resolve_disk(target, hold, official_once, rockbox_once, 0);
}
