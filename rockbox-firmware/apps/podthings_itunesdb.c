/* SPDX-License-Identifier: GPL-2.0-or-later */
/*
 * Classic iPod iTunesDB format (mhbd/mhsd/mhlt/mhit/mhlp/mhyp/mhip/mhod).
 * Format reference: libgpod src/itdb_itunesdb.c (fadingred/libgpod).
 * Independent read-only implementation; never updates checksums or Apple data.
 */
#include "podthings_itunesdb.h"
#include <string.h>
#include <stdlib.h>

struct record { uint32_t at, header, end; };

static uint32_t le32(const unsigned char *p)
{
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 |
           (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static bool bytes(struct itdb *db, uint32_t at, void *out, size_t n)
{
    unsigned char *p = out;
    if (at > db->size || n > db->size - at)
        return false;
    while (n)
    {
        if (!db->cache_len || at < db->cache_at ||
            at - db->cache_at >= db->cache_len)
        {
            db->cache_at = at;
            db->cache_len = db->size - at;
            if (db->cache_len > sizeof(db->cache))
                db->cache_len = sizeof(db->cache);
            if (!db->read_at(db->context, at, db->cache, db->cache_len))
            {
                db->cache_len = 0;
                return false;
            }
        }
        size_t take = db->cache_len - (at - db->cache_at);
        if (take > n) take = n;
        memcpy(p, db->cache + at - db->cache_at, take);
        p += take;
        at += take;
        n -= take;
    }
    return true;
}

static bool number(struct itdb *db, uint32_t at, uint32_t *value)
{
    unsigned char b[4];
    if (!bytes(db, at, b, sizeof(b))) return false;
    *value = le32(b);
    return true;
}

static bool record(struct itdb *db, uint32_t at, uint32_t end,
                   const char *tag, uint32_t min, struct record *r)
{
    unsigned char b[12];
    if (at > end || end - at < 12 || !bytes(db, at, b, 12) ||
        memcmp(b, tag, 4))
        return false;
    uint32_t header = le32(b + 4), total = le32(b + 8);
    if (header < min || total < header || total > end - at)
        return false;
    *r = (struct record){at, header, at + total};
    return true;
}

/* mhlt/mhlp use offset 8 for child count, not total length. */
static bool list(struct itdb *db, const struct record *section,
                 const char *tag, uint32_t max, uint32_t *at, uint32_t *count)
{
    unsigned char b[12];
    uint32_t pos = section->at + section->header;
    if (section->end - pos < 12 || !bytes(db, pos, b, 12) ||
        memcmp(b, tag, 4))
        return false;
    uint32_t len = le32(b + 4);
    *count = le32(b + 8);
    if (len < 12 || len > section->end - pos || *count > max ||
        *count > (section->end - pos - len) / 12)
        return false;
    *at = pos + len;
    return true;
}

bool itdb_open(struct itdb *db,
               bool (*read_at)(void *, uint32_t, void *, size_t),
               void *context, uint32_t size)
{
    memset(db, 0, sizeof(*db));
    db->read_at = read_at;
    db->context = context;
    db->size = size;
    struct record root, section, tracks = {0}, playlists = {0};
    uint32_t count, type, playlist_type = 0;
    if (!record(db, 0, size, "mhbd", 24, &root) ||
        !number(db, 20, &count) || count > (root.end - root.header) / 16)
        return false;
    uint32_t pos = root.header;
    for (uint32_t i = 0; i < count; ++i)
    {
        if (!record(db, pos, root.end, "mhsd", 16, &section) ||
            !number(db, pos + 12, &type))
            return false;
        if (type == 1)
        {
            if (tracks.end) return false;
            tracks = section;
        }
        /* Dataset 3 is the extended playlist list, not a second copy to merge. */
        if ((type == 2 || type == 3) && type > playlist_type)
        {
            playlists = section;
            playlist_type = type;
        }
        pos = section.end;
    }
    if (!tracks.end || !playlists.end ||
        !list(db, &tracks, "mhlt", ITDB_MAX_TRACKS,
              &db->tracks_at, &db->track_count) ||
        !list(db, &playlists, "mhlp", ITDB_MAX_PLAYLISTS,
              &db->playlists_at, &db->playlist_capacity))
        return false;
    db->tracks_end = tracks.end;
    db->playlists_end = playlists.end;
    return true;
}

static bool metadata(struct itdb *db, const struct record *parent, uint32_t count,
                     uint32_t *title, uint32_t *artist, uint32_t *path,
                     uint32_t *next)
{
    uint32_t pos = parent->at + parent->header, type;
    struct record item;
    if (count > (parent->end - pos) / 16) return false;
    for (uint32_t i = 0; i < count; ++i)
    {
        if (!record(db, pos, parent->end, "mhod", 16, &item) ||
            !number(db, pos + 12, &type))
            return false;
        if (type == 1 && title && !*title) *title = pos;
        if (type == 2 && path && !*path) *path = pos;
        if (type == 4 && artist && !*artist) *artist = pos;
        pos = item.end;
    }
    *next = pos;
    return true;
}

static int track_compare(const void *a, const void *b)
{
    uint32_t x = ((const struct itdb_track *)a)->id;
    uint32_t y = ((const struct itdb_track *)b)->id;
    return (x > y) - (x < y);
}

bool itdb_index(struct itdb *db, struct itdb_track *tracks,
                struct itdb_playlist *playlists)
{
    struct record r;
    uint32_t pos = db->tracks_at, count, next;
    db->tracks = tracks;
    db->playlists = playlists;
    db->playlist_count = 0;
    for (uint32_t i = 0; i < db->track_count; ++i)
    {
        struct itdb_track *t = &tracks[i];
        memset(t, 0, sizeof(*t));
        if (!record(db, pos, db->tracks_end, "mhit", 20, &r) ||
            !number(db, pos + 12, &count) ||
            !number(db, pos + 16, &t->id) || !t->id ||
            !metadata(db, &r, count, &t->title, &t->artist, &t->path, &next))
            return false;
        pos = r.end;
    }
    qsort(tracks, db->track_count, sizeof(*tracks), track_compare);
    for (uint32_t i = 1; i < db->track_count; ++i)
        if (tracks[i-1].id == tracks[i].id) return false;
    pos = db->playlists_at;
    for (uint32_t i = 0; i < db->playlist_capacity; ++i)
    {
        unsigned char type;
        struct itdb_playlist p = {0};
        if (!record(db, pos, db->playlists_end, "mhyp", 24, &r) ||
            !number(db, pos + 12, &count) ||
            !number(db, pos + 16, &p.count) || p.count > ITDB_MAX_TRACKS ||
            !bytes(db, pos + 20, &type, 1) ||
            !metadata(db, &r, count, &p.title, NULL, NULL, &p.members) ||
            p.count > (r.end - p.members) / 36)
            return false;
        p.end = r.end;
        /* The hidden master library is not a user playlist. */
        if (!(type & 1)) playlists[db->playlist_count++] = p;
        pos = r.end;
    }
    return true;
}

static int member_compare(const void *a, const void *b)
{
    const struct itdb_member *x = a, *y = b;
    if (x->position != y->position)
        return (x->position > y->position) - (x->position < y->position);
    return (x->ordinal > y->ordinal) - (x->ordinal < y->ordinal);
}

bool itdb_members(struct itdb *db, const struct itdb_playlist *pl,
                  struct itdb_member *members)
{
    uint32_t pos = pl->members, count, type, order;
    struct record r, item;
    for (uint32_t i = 0; i < pl->count; ++i)
    {
        struct itdb_member *m = &members[i];
        if (!record(db, pos, pl->end, "mhip", 36, &r) ||
            !number(db, pos + 12, &count) ||
            !number(db, pos + 24, &m->id))
            return false;
        m->position = m->ordinal = i;
        uint32_t child = pos + r.header;
        bool legacy = (r.end == child), found = false;
        uint32_t end = legacy ? pl->end : r.end;
        if (count > (end - child) / 16) return false;
        for (uint32_t j = 0; j < count; ++j)
        {
            if (!record(db, child, end, "mhod", 16, &item) ||
                !number(db, child + 12, &type))
                return false;
            if (type == 100 && !found)
            {
                if (item.end - child < 28 ||
                    !number(db, child + 24, &order))
                    return false;
                m->position = order;
                found = true;
            }
            child = item.end;
        }
        pos = legacy ? child : r.end;
    }
    qsort(members, pl->count, sizeof(*members), member_compare);
    return true;
}

const struct itdb_track *itdb_find(struct itdb *db, uint32_t id)
{
    uint32_t lo = 0, hi = db->track_count;
    /* The firmware's small C library has qsort but no bsearch. */
    while (lo < hi)
    {
        uint32_t mid = lo + (hi - lo) / 2;
        if (db->tracks[mid].id < id) lo = mid + 1;
        else if (db->tracks[mid].id > id) hi = mid;
        else return &db->tracks[mid];
    }
    return NULL;
}

static bool unit(struct itdb *db, uint32_t pos, uint32_t end, uint32_t *u)
{
    unsigned char b[2];
    if (end - pos < 2 || !bytes(db, pos, b, 2)) return false;
    *u = b[0] | (uint32_t)b[1] << 8;
    return true;
}

bool itdb_text(struct itdb *db, uint32_t at, char *out, size_t size,
               bool truncate)
{
    struct record r;
    uint32_t encoding, len;
    size_t used = 0;
    if (!size) return false;
    out[0] = '\0';
    if (!at || !record(db, at, db->size, "mhod", 16, &r) ||
        r.end - at - r.header < 16 ||
        !number(db, at + r.header, &encoding) ||
        !number(db, at + r.header + 4, &len) ||
        len > r.end - at - r.header - 16 || encoding > 2 ||
        (encoding != 2 && (len & 1)))
        return false;
    uint32_t pos = at + r.header + 16, end = pos + len;
    while (pos < end)
    {
        uint32_t cp;
        if (encoding == 2)
        {
            unsigned char b;
            if (!bytes(db, pos++, &b, 1)) return false;
            cp = b;
            unsigned follow = 0;
            uint32_t minimum = 0;
            if (b >= 0xc2 && b <= 0xdf) { follow = 1; cp &= 31; minimum = 0x80; }
            else if (b >= 0xe0 && b <= 0xef) { follow = 2; cp &= 15; minimum = 0x800; }
            else if (b >= 0xf0 && b <= 0xf4) { follow = 3; cp &= 7; minimum = 0x10000; }
            else if (b >= 0x80) return false;
            while (follow--)
            {
                if (pos == end || !bytes(db, pos++, &b, 1) || (b & 0xc0) != 0x80)
                    return false;
                cp = (cp << 6) | (b & 63);
            }
            if (cp < minimum) return false;
        }
        else
        {
            if (!unit(db, pos, end, &cp)) return false;
            pos += 2;
            if (cp >= 0xd800 && cp <= 0xdbff)
            {
                uint32_t low;
                if (pos == end || !unit(db, pos, end, &low) ||
                    low < 0xdc00 || low > 0xdfff)
                    return false;
                pos += 2;
                cp = 0x10000 + ((cp - 0xd800) << 10) + low - 0xdc00;
            }
        }
        if (cp > 0x10ffff || (cp >= 0xd800 && cp <= 0xdfff) ||
            cp == 0 || cp == '\r' || cp == '\n')
            return false;
        unsigned n = cp < 0x80 ? 1 : cp < 0x800 ? 2 : cp < 0x10000 ? 3 : 4;
        if (n >= size - used)
        {
            out[used] = '\0';
            return truncate;
        }
        if (n == 1) out[used++] = cp;
        else
        {
            out[used++] = (n == 2 ? 0xc0 : n == 3 ? 0xe0 : 0xf0) |
                          (cp >> (6 * (n - 1)));
            for (unsigned j = n - 1; j; --j)
                out[used++] = 0x80 | ((cp >> (6 * (j - 1))) & 63);
        }
    }
    out[used] = '\0';
    return true;
}

bool itdb_path(struct itdb *db, const struct itdb_track *track,
               char *out, size_t size)
{
    if (!track || !itdb_text(db, track->path, out, size, false)) return false;
    for (char *p = out; *p; ++p)
        if (*p == ':') *p = '/';
    /* Accept only device-local iPod_Control media, never traversal/URLs. */
    if (strncmp(out, "/iPod_Control/", 14)) return false;
    const char *p = out + 1;
    do
    {
        const char *end = strchr(p, '/');
        size_t n = end ? (size_t)(end - p) : strlen(p);
        if (!n || (n == 1 && *p == '.') ||
            (n == 2 && p[0] == '.' && p[1] == '.') || memchr(p, '\\', n))
            return false;
        p = end ? end + 1 : NULL;
    } while (p);
    return true;
}
