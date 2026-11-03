/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include "storage.h"
#include "ipodvideo-apple.h"

static unsigned char disk[512 * 100];
static unsigned char image[2048] __attribute__((aligned(32)));
static unsigned reads;
static bool fail_read;
static unsigned sector_size = 512;
enum { START=512, DIRECTORY=START+0x3f6, PAYLOAD=START+4608, LENGTH=1301 };

int storage_read_sectors(sector_t start, int count, void *out)
{
    ++reads;
    if (fail_read || start > 100 || count < 0 || (uint64_t)start + count > 100)
        return -1;
    memcpy(out, disk + start * 512, count * 512);
    return 0;
}
void storage_get_info(int drive, struct storage_info *info)
{ assert(drive==0); info->sector_size=sector_size; }
static void le32(unsigned at, uint32_t value)
{
    for (unsigned i=0; i<4; ++i) disk[at+i]=value>>(i*8);
}
static void checksum(void)
{
    uint32_t sum=0;
    for (unsigned i=0; i<LENGTH; ++i) sum+=disk[PAYLOAD+i];
    le32(DIRECTORY+28,sum);
}
static void fixture(void)
{
    memset(disk,0,sizeof(disk));
    memset(image,0xcc,sizeof(image));
    fail_read=false; reads=0; sector_size=512;
    disk[510]=0x55; disk[511]=0xaa;
    le32(0x1be + 8,1); le32(0x1be + 12,90);
    memcpy(disk+START+0x100,"]ih[",4);
    le32(START+0x104,0x1f6); disk[START+0x10a]=3;
    memcpy(disk+DIRECTORY,"!ATAsoso",8);
    le32(DIRECTORY+12,4096);
    le32(DIRECTORY+16,LENGTH);
    le32(DIRECTORY+24,1200); /* Appended dualboot loader entry point. */
    for (unsigned i=0; i<LENGTH; ++i) disk[PAYLOAD+i]=(i*37)&255;
    memcpy(disk+PAYLOAD+0x20,"portalplayer",12);
    checksum();
}
int main(void)
{
    fixture();
    assert(ipodvideo_load_apple(image,sizeof(image)));
    assert(!memcmp(image,disk+PAYLOAD,LENGTH));
    for (unsigned i=LENGTH; i<sizeof(image); ++i) assert(image[i]==0xcc);
    assert(reads < 30); /* Cross-sector directory plus bounded bulk image reads. */
    fixture(); le32(DIRECTORY+24,0);
    assert(ipodvideo_load_apple(image,sizeof(image))); /* Unpatched Apple image. */
    fixture(); disk[START+0x10a]=2;
    assert(ipodvideo_load_apple(image,sizeof(image))); /* One-image v2. */
    fixture(); disk[START+0x10a]=2;
    memcpy(disk+DIRECTORY+40,"!ATAcrsr",8);
    le32(DIRECTORY+12,4608); /* v2 multi-image data starts at partition base. */
    assert(ipodvideo_load_apple(image,sizeof(image)));
    fixture(); memcpy(disk+DIRECTORY+4,"kbso",4);
    assert(ipodvideo_load_apple(image,sizeof(image))); /* Valid backup image. */
    fixture(); assert(!ipodvideo_load_apple(image,LENGTH-1));
    assert(image[LENGTH-1]==0xcc);
    fixture(); disk[511]=0; assert(!ipodvideo_load_apple(image,sizeof(image)));
    fixture(); disk[0x1be + 4]=0xb; assert(!ipodvideo_load_apple(image,sizeof(image)));
    fixture(); le32(0x1be + 8,0); assert(!ipodvideo_load_apple(image,sizeof(image)));
    fixture(); le32(0x1be + 12,1); assert(!ipodvideo_load_apple(image,sizeof(image)));
    fixture(); le32(START+0x104,0xfffffff0);
    assert(!ipodvideo_load_apple(image,sizeof(image)));
    fixture(); disk[START+0x10a]=4;
    assert(!ipodvideo_load_apple(image,sizeof(image)));
    fixture(); le32(DIRECTORY+12,90*512-512);
    assert(!ipodvideo_load_apple(image,sizeof(image))); /* Partition overrun. */
    fixture(); le32(DIRECTORY+24,LENGTH);
    assert(!ipodvideo_load_apple(image,sizeof(image)));
    fixture(); disk[PAYLOAD+80]^=1;
    assert(!ipodvideo_load_apple(image,sizeof(image))); /* Bad checksum. */
    fixture(); disk[PAYLOAD+32]=0; checksum();
    assert(!ipodvideo_load_apple(image,sizeof(image))); /* Not Apple's image. */
    fixture(); fail_read=true; assert(!ipodvideo_load_apple(image,sizeof(image)));
    fixture(); sector_size=4096;
    assert(!ipodvideo_load_apple(image,sizeof(image))); /* Unsupported OF geometry. */
    assert(!reads);
    return 0;
}
