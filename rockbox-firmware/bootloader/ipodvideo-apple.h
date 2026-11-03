/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef IPODVIDEO_APPLE_H
#define IPODVIDEO_APPLE_H
#include <stdbool.h>
#include <stddef.h>
/* Read-only recovery of OSOS/OSBK from the Apple firmware partition. */
bool ipodvideo_load_apple(unsigned char *image, size_t capacity);
#endif
