/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Native click-wheel music entry points. No Apple database writes. */
#include "config.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "menu.h"
#include "root_menu.h"
#include "plugin.h"
#include "tagcache.h"
#include "settings.h"
#include "playlist.h"
#include "audio.h"
#include "file.h"
#include "filetypes.h"
#include "list.h"
#include "action.h"
#include "misc.h"
#include "splash.h"
#include "core_alloc.h"
#include "yesno.h"
#include "string-extra.h"
#include "podthings_music.h"

int podthings_music_menu(void *unused)
{
    (void)unused;
    static int selection;
    MENUITEM_RETURNVALUE(library, "Browse Music", GO_TO_DBBROWSER, NULL, Icon_Audio);
    MENUITEM_RETURNVALUE(az, "A-Z Jump", GO_TO_MUSIC_AZ, NULL, Icon_Audio);
    MENUITEM_RETURNVALUE(search, "Search Music", GO_TO_MUSIC_SEARCH, NULL, Icon_Audio);
    MENUITEM_RETURNVALUE(flow, "Cover Flow", GO_TO_COVER_FLOW, NULL, Icon_Audio);
    MENUITEM_RETURNVALUE(playlists, "Playlists", GO_TO_PLAYLISTS_SCREEN, NULL, Icon_Playlist);
    MENUITEM_RETURNVALUE(favorites, "Favorites", GO_TO_SHORTCUTMENU, NULL, Icon_Bookmark);
    MENUITEM_RETURNVALUE(shuffle, "Shuffle Songs", GO_TO_MUSIC_SHUFFLE, NULL, Icon_Audio);
    MAKE_MENU(music, "Music", NULL, Icon_Audio,
              &library, &az, &search, &flow, &playlists, &shuffle, &favorites);
    return do_menu(&music, &selection, NULL, false);
}

int podthings_extras_menu(void *unused)
{
    (void)unused;
    static int selection;
    MENUITEM_RETURNVALUE(files, "Files", GO_TO_FILEBROWSER, NULL, Icon_file_view_menu);
    MENUITEM_RETURNVALUE(plugins, "Games & Plugins", GO_TO_BROWSEPLUGINS, NULL, Icon_Plugin);
#ifdef HAVE_RECORDING
    MENUITEM_RETURNVALUE(recording, "Recording", GO_TO_RECSCREEN, NULL, Icon_Recording);
#endif
    MENUITEM_RETURNVALUE(bookmarks, "Recent Bookmarks", GO_TO_RECENTBMARKS, NULL, Icon_Bookmark);
    MAKE_MENU(extras, "Extras", NULL, Icon_Submenu_Entered, &files, &plugins,
#ifdef HAVE_RECORDING
              &recording,
#endif
              &bookmarks);
    return do_menu(&extras, &selection, NULL, false);
}

static bool return_to_coverflow;

int podthings_coverflow_wps_return(int screen)
{
    if (!return_to_coverflow) return screen;
    if (screen==GO_TO_PREVIOUS || screen==GO_TO_PREVIOUS_BROWSER)
        return GO_TO_COVER_FLOW;
    return_to_coverflow=false;
    return screen;
}

int podthings_coverflow(void *unused)
{
    (void)unused;
    if (!tagcache_is_usable())
    {
        return_to_coverflow=false;
        splash(HZ * 3, "Build the music database in Browse Music first");
        return GO_TO_PREVIOUS;
    }
    bool resume=return_to_coverflow;
    return_to_coverflow=false;
    int status = plugin_load(PLUGIN_DEMOS_DIR "/pictureflow.rock",
                             resume ? "podthings:album" : NULL);
    return_to_coverflow=status==PLUGIN_GOTO_WPS;
    return return_to_coverflow ? GO_TO_WPS : GO_TO_MUSIC;
}

#define RECENT_ALBUMS 24
struct recent_album {
    char album[160], artist[96];
    long stamp;
};
struct album_track { int32_t index; long disc, track; };
static struct recent_album recent[RECENT_ALBUMS];
static int recent_count;

static int newest_first(const void *a, const void *b)
{
    long x = ((const struct recent_album *)a)->stamp;
    long y = ((const struct recent_album *)b)->stamp;
    return (x < y) - (x > y);
}

static bool album_tags(struct tagcache_search *s, char *album, char *artist)
{
    if (!tagcache_retrieve(s, s->idx_id, tag_album, album, sizeof(recent[0].album)) ||
        !*album || !strcmp(album, "[Untagged]"))
        return false;
    if (!tagcache_retrieve(s, s->idx_id, tag_albumartist, artist,
                           sizeof(recent[0].artist)) || !strcmp(artist, "[Untagged]"))
        artist[0] = '\0';
    return true;
}

static bool collect_recent(void)
{
    struct tagcache_search s;
    char path[MAX_PATH], album[160], artist[96];
    recent_count = 0;
    if (!tagcache_search(&s, tag_filename)) return false;
    while (tagcache_get_next(&s, path, sizeof(path)))
    {
        long stamp = tagcache_get_numeric(&s, tag_lastplayed);
        if (stamp <= 0 || !album_tags(&s, album, artist)) continue;
        int index;
        for (index = 0; index < recent_count; ++index)
            if (!strcmp(recent[index].album, album) &&
                !strcmp(recent[index].artist, artist)) break;
        if (index == recent_count)
        {
            if (recent_count == RECENT_ALBUMS)
            {
                if (stamp <= recent[recent_count - 1].stamp) continue;
                index = recent_count - 1;
            }
            else ++recent_count;
            strmemccpy(recent[index].album, album, sizeof(recent[index].album));
            strmemccpy(recent[index].artist, artist, sizeof(recent[index].artist));
            recent[index].stamp = stamp;
        }
        else if (stamp > recent[index].stamp) recent[index].stamp = stamp;
        qsort(recent, recent_count, sizeof(*recent), newest_first);
        yield();
    }
    tagcache_search_finish(&s);
    return true;
}

static const char *recent_name(int index, void *data, char *buf, size_t size)
{
    (void)data;
    snprintf(buf, size, "%s%s%s", recent[index].album,
             *recent[index].artist ? " - " : "", recent[index].artist);
    return buf;
}

static int select_recent(int action, struct gui_synclist *list)
{
    (void)list;
    return action == ACTION_STD_OK ? ACTION_STD_CANCEL : action;
}

static int album_order(const void *a, const void *b)
{
    const struct album_track *x = a, *y = b;
    if (x->disc != y->disc) return (x->disc > y->disc) - (x->disc < y->disc);
    if (x->track != y->track) return (x->track > y->track) - (x->track < y->track);
    return (x->index > y->index) - (x->index < y->index);
}

static bool same_album(struct tagcache_search *s, const struct recent_album *r)
{
    char album[160], artist[96];
    return album_tags(s, album, artist) &&
           !strcmp(album, r->album) && !strcmp(artist, r->artist);
}

static bool play_album(const struct recent_album *r)
{
    if (global_settings.party_mode && audio_status())
    {
        splash(HZ * 2, "Party mode: current playlist is protected");
        return false;
    }
    /* Two passes keep allocations proportional to the selected album,
     * not to the entire library. Order explicitly by disc and track number. */
    struct tagcache_search s;
    char path[MAX_PATH], current[MAX_PATH];
    int count = 0;
    if (!tagcache_search(&s, tag_filename))
    {
        splash(HZ * 3, "Music database unavailable");
        return false;
    }
    while (tagcache_get_next(&s, path, sizeof(path)))
        if (same_album(&s, r)) ++count;
    tagcache_search_finish(&s);
    if (!count || count > playlist_get_current()->max_playlist_size)
    {
        splash(HZ * 3, "Album empty or exceeds playlist size limit");
        return false;
    }
    int handle = core_alloc(count * sizeof(struct album_track));
    if (handle <= 0)
    {
        splash(HZ * 2, "Not enough memory for album");
        return false;
    }
    struct album_track *tracks = core_get_data_pinned(handle);
    int filled = 0, played = 0;
    bool ok = tagcache_search(&s, tag_filename);
    if (ok)
    {
        while (tagcache_get_next(&s, path, sizeof(path)))
            if (same_album(&s, r))
            {
                if (filled == count) { ok = false; break; }
                tracks[filled++] = (struct album_track){
                    s.idx_id, tagcache_get_numeric(&s, tag_discnumber),
                    tagcache_get_numeric(&s, tag_tracknumber)};
            }
        tagcache_search_finish(&s);
    }
    if (filled != count) ok = false;
    qsort(tracks, filled, sizeof(*tracks), album_order);
    playlist_get_name(NULL, current, sizeof(current));
    const char *name = !strcmp(current, ROCKBOX_DIR "/recent-album-a.m3u8") ?
                      "recent-album-b.m3u8" : "recent-album-a.m3u8";
    const char *tmp = ROCKBOX_DIR "/recent-album.tmp";
    int fd = ok ? open(tmp, O_WRONLY | O_CREAT | O_TRUNC, 0666) : -1;
    if (fd < 0) ok = false;
    if (ok && tagcache_search(&s, tag_filename))
    {
        for (int i = 0; i < filled; ++i)
        {
            if (!tagcache_retrieve(&s, tracks[i].index, tag_filename, path, sizeof(path)))
            { ok = false; break; }
            const char *ext = strrchr(path, '.');
            if (!file_exists(path) || (ext && !strcasecmp(ext, ".m4p")) ||
                (filetype_get_attr(path) & FILE_ATTR_MASK) != FILE_ATTR_AUDIO)
                continue;
            size_t len = strlen(path);
            if (path[0] != '/' || strchr(path, '\n') || strchr(path, '\r') ||
                write(fd, path, len) != (ssize_t)len || write(fd, "\n", 1) != 1)
            { ok = false; break; }
            ++played;
        }
        tagcache_search_finish(&s);
    }
    else ok = false;
    if (fd >= 0 && close(fd) < 0) ok = false;
    core_unpin(handle);
    core_free(handle);
    if (!ok || !played)
    {
        remove(tmp);
        splash(HZ * 3, "Cannot prepare album playback");
        return false;
    }
    if (!warn_on_pl_erase()) { remove(tmp); return false; }
    snprintf(path, sizeof(path), "%s/%s", ROCKBOX_DIR, name);
    if (rename(tmp, path) < 0 ||
        playlist_create(ROCKBOX_DIR, name) < 0 || playlist_amount() != played)
    {
        remove(tmp);
        splash(HZ * 3, "Cannot load album playlist");
        return false;
    }
    int start = global_settings.playlist_shuffle ? playlist_shuffle(0, 0) : 0;
    playlist_start(start, 0, 0);
    if (played < count) splashf(HZ * 2, "Skipped %d unavailable tracks", count - played);
    return true;
}

int podthings_recent_albums(void *unused)
{
    (void)unused;
    if (!tagcache_is_usable())
    {
        splash(HZ * 3, "Build the music database in Music > Browse Music first");
        return GO_TO_PREVIOUS;
    }
    if (!global_settings.runtimedb)
    {
        static const char *lines[] = {
            "Enable listening history?",
            "Used for Recently Played Albums.",
            "Stored on this iPod only."
        };
        static const struct text_message message = {lines, 3};
        if (gui_syncyesno_run(&message, NULL, NULL) != YESNO_YES)
            return GO_TO_PREVIOUS;
        global_settings.runtimedb = true;
        settings_save();
    }
    splash(0, "Loading recent albums...");
    if (!collect_recent())
    {
        splash(HZ * 3, "Music database unavailable");
        return GO_TO_PREVIOUS;
    }
    if (!recent_count)
    {
        splash(HZ * 3, "No listening history yet. Play some music first.");
        return GO_TO_PREVIOUS;
    }
    struct simplelist_info info;
    simplelist_info_init(&info, "Recently Played Albums", recent_count, NULL);
    info.get_name = recent_name;
    info.action_callback = select_recent;
    info.title_icon = Icon_Audio;
    for (;;)
    {
        if (simplelist_show_list(&info) || info.selection < 0) return GO_TO_PREVIOUS;
        if (play_album(&recent[info.selection])) return GO_TO_WPS;
    }
}
