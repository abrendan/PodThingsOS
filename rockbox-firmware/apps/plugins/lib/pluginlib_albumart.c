/***************************************************************************
*             __________               __   ___.
*   Open      \______   \ ____   ____ |  | _\_ |__   _______  ___
*   Source     |       _//  _ \_/ ___\|  |/ /| __ \ /  _ \  \/  /
*   Jukebox    |    |   (  <_> )  \___|    < | \_\ (  <_> > <  <
*   Firmware   |____|_  /\____/ \___  >__|_ \|___  /\____/__/\_ \
*                     \/            \/     \/    \/            \/
*
* Copyright (C) 2009 by Andrew Mahone
*
* This is a wrapper for the core albumart.c
*
* This program is free software; you can redistribute it and/or
* modify it under the terms of the GNU General Public License
* as published by the Free Software Foundation; either version 2
* of the License, or (at your option) any later version.
*
* This software is distributed on an "AS IS" basis, WITHOUT WARRANTY OF ANY
* KIND, either express or implied.
*
****************************************************************************/

#include <plugin.h>
#include "wrappers.h"

#ifdef PODTHINGS_OS
#define write rb->write
#define remove rb->remove
#define rename rb->rename
#define mkdir rb->mkdir
#define ffilesize rb->ffilesize
#define memcmp rb->memcmp
#define memcpy rb->memcpy
#define strncmp rb->strncmp
#define strcasecmp rb->strcasecmp
#define strncasecmp rb->strncasecmp
#define strstr rb->strstr
#define qsort rb->qsort
#define mutex_init rb->mutex_init
#define mutex_lock rb->mutex_lock
#define mutex_unlock rb->mutex_unlock
/* No plugin ABI change: compile the same bounded reader with file-API wrappers. */
#include "../../podthings_itunesdb.c"
#include "../../podthings_artwork.c"
#endif
#include "../../recorder/albumart.c"
