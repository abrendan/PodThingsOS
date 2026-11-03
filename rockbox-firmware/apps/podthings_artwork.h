/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef PODTHINGS_ARTWORK_H
#define PODTHINGS_ARTWORK_H
#include <stdbool.h>
#include <stddef.h>
/* Apple files are read-only. Derived indexes/bitmaps live in ROCKBOX_DIR. */
bool podthings_itunes_art(const char *track, char *out, size_t size);
#endif
