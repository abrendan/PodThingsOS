/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Read-only, bounded classic iPod iTunesDB reader. No filesystem writes. */
#ifndef PODTHINGS_ITUNESDB_H
#define PODTHINGS_ITUNESDB_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define ITDB_MAX_TRACKS 100000
#define ITDB_MAX_PLAYLISTS 4096

struct itdb_track {
    uint32_t id, title, artist, path;
};
struct itdb_playlist {
    uint32_t title, members, end, count;
};
struct itdb_member {
    uint32_t id, position, ordinal;
};
struct itdb {
    bool (*read_at)(void *, uint32_t, void *, size_t);
    void *context;
    uint32_t size, tracks_at, tracks_end, playlists_at, playlists_end;
    uint32_t track_count, playlist_capacity, playlist_count;
    struct itdb_track *tracks;
    struct itdb_playlist *playlists;
    uint32_t cache_at, cache_len;
    unsigned char cache[512];
};

bool itdb_open(struct itdb *db,
               bool (*read_at)(void *, uint32_t, void *, size_t),
               void *context, uint32_t size);
bool itdb_index(struct itdb *db, struct itdb_track *tracks,
                struct itdb_playlist *playlists);
bool itdb_members(struct itdb *db, const struct itdb_playlist *pl,
                  struct itdb_member *members);
const struct itdb_track *itdb_find(struct itdb *db, uint32_t id);
/* Display strings may truncate at a codepoint boundary; paths never truncate. */
bool itdb_text(struct itdb *db, uint32_t at, char *out, size_t size,
               bool truncate);
bool itdb_path(struct itdb *db, const struct itdb_track *track,
               char *out, size_t size);
#endif
