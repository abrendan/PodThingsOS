/* SPDX-License-Identifier: GPL-2.0-or-later
 * Reload Apple firmware when a warm boot did not leave a retail image in RAM.
 * Never modify the partition, boot directory, or entry point.
 */
#include "config.h"
#include <stdint.h>
#include <string.h>
#include "storage.h"
#include "ipodvideo-apple.h"

static unsigned char sector[512] __attribute__((aligned(32)));

static uint32_t read_le32(const unsigned char *p)
{
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 |
           (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static bool partition_read(uint32_t start, uint32_t sectors, uint64_t offset,
                           unsigned char *out, size_t length)
{
    uint64_t limit = (uint64_t)sectors * 512;
    if (offset > limit || length > limit - offset)
        return false;
    while (length)
    {
        unsigned skip = offset % 512;
        if (!skip && length >= 512 && !((uintptr_t)out & 31))
        {
            unsigned count = length / 512;
            if (count > 64)
                count = 64;
            if (storage_read_sectors(IF_MD(0,) (sector_t)start + offset / 512,
                                     count, out) != 0)
                return false;
            unsigned bytes = count * 512;
            offset += bytes;
            out += bytes;
            length -= bytes;
        }
        else
        {
            if (storage_read_sectors(IF_MD(0,) (sector_t)start + offset / 512,
                                     1, sector) != 0)
                return false;
            unsigned bytes = 512 - skip;
            if (bytes > length)
                bytes = length;
            memcpy(out, sector + skip, bytes);
            offset += bytes;
            out += bytes;
            length -= bytes;
        }
    }
    return true;
}

bool ipodvideo_load_apple(unsigned char *image, size_t capacity)
{
    /* OF does not support arbitrary translated sector geometries. */
#ifdef STORAGE_GET_INFO
    struct storage_info info;
    storage_get_info(0, &info);
    if (info.sector_size != 512)
        return false;
#endif
    if (storage_read_sectors(IF_MD(0,) 0, 1, sector) != 0 ||
        sector[510] != 0x55 || sector[511] != 0xaa)
        return false;
    /* Apple's first MBR partition is type zero, not the FAT data partition. */
    if (sector[0x1be + 4] != 0)
        return false;
    uint32_t start = read_le32(sector + 0x1be + 8);
    uint32_t sectors = read_le32(sector + 0x1be + 12);
    if (!start || sectors < 2 || (uint64_t)start + sectors > 0x100000000ULL)
        return false;
    if (!partition_read(start, sectors, 0, sector, 512) ||
        memcmp(sector + 0x100, "]ih[", 4) ||
        (sector[0x10a] != 2 && sector[0x10a] != 3) ||
        sector[0x10b] != 0)
        return false;

    uint64_t directory = (uint64_t)read_le32(sector + 0x104) + 0x200;
    uint32_t image_base = 512;
    if (sector[0x10a] == 2)
    {
        /* The older multi-image directory addresses data from the start of
         * the partition, unlike single-image v2 and the v3 directories. */
        unsigned char second[40];
        if (!partition_read(start, sectors, directory + 40,
                            second, sizeof(second)))
            return false;
        if (!memcmp(second, "!ATA", 4))
            image_base = 0;
    }
    /* A patched OSOS includes the appended loader in its size and checksum.
     * Read/check the whole image, then enter Apple's original RAM vector.
     * OSBK is an alternative only when OSOS isn't a valid retail image. */
    for (unsigned pass = 0; pass < 2; ++pass)
        for (unsigned index = 0; index < 10; ++index)
        {
            unsigned char entry[40];
            if (!partition_read(start, sectors, directory + index * 40,
                                entry, sizeof(entry)))
                return false;
            if (memcmp(entry, "!ATA", 4))
                break;
            if (memcmp(entry + 4, pass ? "kbso" : "soso", 4))
                continue;
            uint32_t length = read_le32(entry + 16);
            uint32_t entrypoint = read_le32(entry + 24);
            if (length < 44 || length > capacity || entrypoint >= length)
                continue;
            uint64_t offset = (uint64_t)read_le32(entry + 12) + image_base;
            if (!partition_read(start, sectors, offset, image, length))
                return false;
            uint32_t checksum = 0;
            for (uint32_t i = 0; i < length; ++i)
                checksum += image[i];
            if (checksum == read_le32(entry + 28) &&
                memcmp(image + 0x20, "portalplayer", 12) == 0)
                return true;
        }
    return false;
}
