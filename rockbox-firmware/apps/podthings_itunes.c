/* SPDX-License-Identifier: GPL-2.0-or-later */
/* iTunes playlists are views of Apple data, not editable catalog files. */
#include "config.h"
#include <stdio.h>
#include <string.h>
#include "file.h"
#include "kernel.h"
#include "core_alloc.h"
#include "action.h"
#include "list.h"
#include "icons.h"
#include "settings.h"
#include "playlist.h"
#include "audio.h"
#include "misc.h"
#include "splash.h"
#include "filetypes.h"
#include "string-extra.h"
#include "podthings_itunes.h"
#include "podthings_itunesdb.h"

#define ITUNES_DB "/iPod_Control/iTunes/iTunesDB"
#define CACHE_A "itunes-playback-a.m3u8"
#define CACHE_B "itunes-playback-b.m3u8"
#define CACHE_TMP ROCKBOX_DIR "/itunes-playback.tmp"

struct itunes_browser {
    struct itdb db;
    int fd;
    struct itdb_member *members;
    bool usb;
};

static bool read_database(void *context, uint32_t at, void *out, size_t n)
{
    struct itunes_browser *b = context;
    yield();
    return lseek(b->fd, at, SEEK_SET) == (off_t)at &&
           read(b->fd, out, n) == (ssize_t)n;
}

static const char *itunes_playlist_name(int item, void *data, char *buf, size_t size)
{
    struct itunes_browser *b = data;
    if (!itdb_text(&b->db, b->db.playlists[item].title, buf, size, true) || !*buf)
        snprintf(buf, size, "Playlist %d", item + 1);
    return buf;
}

static const char *track_name(int item, void *data, char *buf, size_t size)
{
    struct itunes_browser *b = data;
    const struct itdb_track *t = itdb_find(&b->db, b->members[item].id);
    char artist[96];
    if (!t)
        snprintf(buf, size, "%d. [Missing track]", item + 1);
    else
    {
        if (!itdb_text(&b->db, t->title, buf, size, true) || !*buf)
            snprintf(buf, size, "Track %d", item + 1);
        if (itdb_text(&b->db, t->artist, artist, sizeof(artist), true) && *artist)
        {
            size_t used = strlen(buf);
            snprintf(buf + used, size - used, " - %s", artist);
        }
    }
    return buf;
}

static int select_action(int action, struct gui_synclist *lists)
{
    if (action == SYS_USB_CONNECTED)
    {
        struct itunes_browser *b = lists->data;
        b->usb = true;
        /* Close the database before USB exposes the disk for another sync. */
        return ACTION_STD_CANCEL;
    }
    /* No context menu / rename / delete / reorder / save-to-iTunes actions. */
    return action == ACTION_STD_OK ? ACTION_STD_CANCEL : action;
}

/* -3 = USB, -2 = WPS, -1 = back; otherwise selected item. */
static int choose(struct itunes_browser *b, char *title, int count,
                  int selected, bool tracks)
{
    struct simplelist_info info;
    simplelist_info_init(&info, title, count, b);
    info.get_name = tracks ? track_name : itunes_playlist_name;
    info.action_callback = select_action;
    info.selection = selected;
    info.title_icon = Icon_Playlist;
    if (simplelist_show_list(&info) || b->usb) return -3;
    return info.selection;
}

static bool playable(struct itunes_browser *b, uint32_t id, char *path, size_t size)
{
    const struct itdb_track *t = itdb_find(&b->db, id);
    if (!itdb_path(&b->db, t, path, size)) return false;
    const char *ext = strrchr(path, '.');
    /* Protected iTunes purchases cannot be decrypted by the firmware. */
    if (ext && !strcasecmp(ext, ".m4p")) return false;
    return (filetype_get_attr(path) & FILE_ATTR_MASK) == FILE_ATTR_AUDIO &&
           file_exists(path);
}

static bool play_selection(struct itunes_browser *b, uint32_t count, int selected)
{
    char path[MAX_PATH], current[MAX_PATH], cache[MAX_PATH];
    if (global_settings.party_mode && audio_status())
    {
        splash(HZ * 2, "Party mode: current playlist is protected");
        return false;
    }
    if (!playable(b, b->members[selected].id, path, sizeof(path)))
    {
        splash(HZ * 3, "Track missing, protected, or unsupported");
        return false;
    }
    /* Build a private playback copy first. Never write under iPod_Control.
     * Choose the inactive slot so a failed/cancelled load cannot overwrite the
     * playlist backing current playback. Apple IDs/order are left untouched. */
    playlist_get_name(NULL, current, sizeof(current));
    const char *name = !strcmp(current, ROCKBOX_DIR "/" CACHE_A) ? CACHE_B : CACHE_A;
    snprintf(cache, sizeof(cache), "%s/%s", ROCKBOX_DIR, name);
    int out = open(CACHE_TMP, O_WRONLY | O_CREAT | O_TRUNC, 0666);
    if (out < 0)
    {
        splash(HZ * 2, "Cannot create playback copy");
        return false;
    }
    splash(0, "Loading iTunes playlist...");
    int playable_count = 0, start = -1, skipped = 0;
    bool ok = true, cancelled = false;
    for (uint32_t i = 0; i < count; ++i)
    {
        /* Defer USB handling until all files and allocations are closed. */
        int action = get_action(CONTEXT_STD, TIMEOUT_NOBLOCK);
        if (action == ACTION_STD_CANCEL)
        {
            cancelled = true;
            break;
        }
        if (action == SYS_USB_CONNECTED)
        {
            b->usb = true;
            cancelled = true;
            break;
        }
        default_event_handler(action);
        if (!playable(b, b->members[i].id, path, sizeof(path)))
        {
            ++skipped;
            continue;
        }
        if ((int)i == selected) start = playable_count;
        size_t len = strlen(path);
        if (++playable_count > playlist_get_current()->max_playlist_size ||
            write(out, path, len) != (ssize_t)len || write(out, "\n", 1) != 1)
        {
            ok = false;
            break;
        }
        yield();
    }
    if (close(out) < 0) ok = false;
    if (cancelled || !ok || !playable_count || start < 0)
    {
        remove(CACHE_TMP);
        if (!cancelled)
            splash(HZ * 3, "Cannot load: storage error or playlist size limit");
        return false;
    }
    if (!warn_on_pl_erase())
    {
        remove(CACHE_TMP);
        return false;
    }
    if (rename(CACHE_TMP, cache) < 0)
    {
        remove(CACHE_TMP);
        splash(HZ * 2, "Cannot save playback copy");
        return false;
    }
    if (playlist_create(ROCKBOX_DIR, name) < 0 || playlist_amount() != playable_count)
    {
        splash(HZ * 3, "Cannot load playback copy");
        return false;
    }
    if (global_settings.playlist_shuffle)
        start = playlist_shuffle(0, start);
    playlist_start(start, 0, 0);
    if (skipped)
        splashf(HZ * 3, "Skipped %d missing/protected/unsupported tracks", skipped);
    return true;
}

bool podthings_itunes_playlists(void)
{
    /* Static: the native UI thread has a small stack; only one browser runs. */
    static struct itunes_browser b;
    memset(&b, 0, sizeof(b));
    b.fd = open(ITUNES_DB, O_RDONLY);
    if (b.fd < 0)
    {
        splash(HZ * 4, file_exists("/iPod_Control/iTunes/iTunesCDB") ?
               "Compressed iTunes database is not supported" :
               "No iTunesDB found. Sync playlists to this iPod first.");
        return false;
    }
    off_t size = ffilesize(b.fd);
    if (size < 24 || size > 0x7fffffff ||
        !itdb_open(&b.db, read_database, &b, (uint32_t)size))
    {
        splash(HZ * 3, "Invalid or unsupported iTunes database");
        close(b.fd);
        return false;
    }
    size_t bytes = b.db.track_count * sizeof(struct itdb_track) +
                   b.db.playlist_capacity * sizeof(struct itdb_playlist);
    int index_handle = core_alloc(bytes ? bytes : 1);
    if (index_handle <= 0)
    {
        splash(HZ * 2, "Not enough memory for iTunes library");
        close(b.fd);
        return false;
    }
    struct itdb_track *tracks = core_get_data_pinned(index_handle);
    struct itdb_playlist *playlists = (void *)(tracks + b.db.track_count);
    bool playing = false;
    splash(0, "Reading iTunes playlists...");
    if (!itdb_index(&b.db, tracks, playlists))
        splash(HZ * 3, "Invalid or unsupported iTunes database");
    else if (!b.db.playlist_count)
        splash(HZ * 3, "No synced iTunes playlists");
    else
    {
        int selected = 0;
        for (;;)
        {
            selected = choose(&b, "iTunes Playlists (read-only)",
                              b.db.playlist_count, selected, false);
            if (selected < 0)
            {
                playing = selected == -2 && audio_status();
                break;
            }
            const struct itdb_playlist *pl = &playlists[selected];
            if (!pl->count)
            {
                splash(HZ * 2, "Empty iTunes playlist");
                continue;
            }
            int members_handle = core_alloc(pl->count * sizeof(*b.members));
            if (members_handle <= 0)
            {
                splash(HZ * 2, "Not enough memory for this playlist");
                continue;
            }
            b.members = core_get_data_pinned(members_handle);
            if (!itdb_members(&b.db, pl, b.members))
                splash(HZ * 3, "Invalid iTunes playlist entries");
            else
            {
                char title[128];
                itunes_playlist_name(selected, &b, title, sizeof(title));
                int track = 0;
                for (;;)
                {
                    track = choose(&b, title, pl->count, track, true);
                    if (track < 0)
                    {
                        playing = track == -2 && audio_status();
                        break;
                    }
                    if (play_selection(&b, pl->count, track))
                    {
                        playing = true;
                        break;
                    }
                    if (b.usb) break;
                }
                if (track == -3) selected = -3;
            }
            core_unpin(members_handle);
            core_free(members_handle);
            b.members = NULL;
            if (playing || selected == -3 || b.usb) break;
        }
    }
    core_unpin(index_handle);
    core_free(index_handle);
    close(b.fd);
    bool usb = b.usb;
    memset(&b, 0, sizeof(b));
    if (usb) default_event_handler(SYS_USB_CONNECTED);
    return playing;
}
