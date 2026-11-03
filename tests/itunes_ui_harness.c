/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Host-only UI/storage shims. Includes the real browser implementation below. */
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include "podthings_itunesdb.h"

#define MAX_PATH 260
#define ROCKBOX_DIR "/.podthingsloader"
#define HZ 100
#define CONTEXT_STD 0
#define TIMEOUT_NOBLOCK 0
#define ACTION_STD_OK 1
#define ACTION_STD_CANCEL 2
#define ACTION_STD_CONTEXT 3
#define SYS_USB_CONNECTED 99
#define Icon_Playlist 1
#define FILE_ATTR_MASK 0xff00
#define FILE_ATTR_AUDIO 0x0300
struct gui_synclist { void *data; };
struct simplelist_info {
    const char *title;
    int count, selection, title_icon;
    void *callback_data;
    const char *(*get_name)(int, void *, char *, size_t);
    int (*action_callback)(int, struct gui_synclist *);
};
struct playlist_info { int max_playlist_size; };
static struct { bool party_mode, playlist_shuffle; } global_settings;
static struct playlist_info current_pl = {1000};
static char root[1024], current_name[MAX_PATH] = ROCKBOX_DIR "/itunes-playback-a.m3u8";
static char scenario[64];
static int selections[16], selection_count, selection_at;
static int started = -1, amount, shuffles, allocations, active_allocs, audio_active;
static int disk_writes;
static int usb_handlers;
static void *handles[16];
static bool writable[1024];

static void mapped(const char *path, char *out, size_t n)
{
    assert(path[0] == '/' && !strstr(path, ".."));
    int len = snprintf(out, n, "%s%s", root, path);
    assert(len > 0 && (size_t)len < n);
}

static int host_open(const char *path, int flags, ...)
{
    char full[1400];
    mapped(path, full, sizeof(full));
    bool writing = (flags & O_ACCMODE) != O_RDONLY;
    if (writing)
    {
        assert(!strncmp(path, ROCKBOX_DIR "/", sizeof(ROCKBOX_DIR)));
        ++disk_writes;
    }
    int fd = open(full, flags, 0666);
    if (fd >= 0) { assert(fd < 1024); writable[fd] = writing; }
    return fd;
}

static ssize_t host_write(int fd, const void *data, size_t n)
{
    assert(fd >= 0 && fd < 1024 && writable[fd]);
    if (!strcmp(scenario, "write_error")) return -1;
    return write(fd, data, n);
}

static int host_remove(const char *path)
{
    assert(!strncmp(path, ROCKBOX_DIR "/", sizeof(ROCKBOX_DIR)));
    char full[1400];
    mapped(path, full, sizeof(full));
    return remove(full);
}

static int host_rename(const char *from, const char *to)
{
    assert(!strncmp(from, ROCKBOX_DIR "/", sizeof(ROCKBOX_DIR)));
    assert(!strncmp(to, ROCKBOX_DIR "/", sizeof(ROCKBOX_DIR)));
    assert(strcmp(to, current_name)); /* never overwrite active playback */
    if (!strcmp(scenario, "rename_error")) return -1;
    char a[1400], b[1400];
    mapped(from, a, sizeof(a));
    mapped(to, b, sizeof(b));
    return rename(a, b);
}

static off_t ffilesize(int fd)
{
    struct stat st;
    return fstat(fd, &st) ? -1 : st.st_size;
}

static bool file_exists(const char *path)
{
    char full[1400];
    mapped(path, full, sizeof(full));
    return access(full, F_OK) == 0;
}

static int core_alloc(size_t size)
{
    ++allocations;
    if ((!strcmp(scenario, "oom_index") && allocations == 1) ||
        (!strcmp(scenario, "oom_members") && allocations == 2))
        return -1;
    assert(allocations < 16);
    handles[allocations] = calloc(1, size);
    assert(handles[allocations]);
    ++active_allocs;
    return allocations;
}

static void *core_get_data_pinned(int h) { return handles[h]; }
static void core_unpin(int h) { assert(handles[h]); }
static void core_free(int h) { free(handles[h]); handles[h] = NULL; --active_allocs; }
static void yield(void) {}
static int get_action(int context, int timeout)
{
    (void)context; (void)timeout;
    return !strcmp(scenario, "usb_loading") ? SYS_USB_CONNECTED : 0;
}
static long default_event_handler(long action)
{
    if (action == SYS_USB_CONNECTED)
    {
        assert(active_allocs == 0);
        ++usb_handlers;
    }
    return action;
}
static int audio_status(void) { return audio_active; }
static void splash(int ticks, const char *text) { (void)ticks; puts(text); }
static void splashf(int ticks, const char *fmt, ...)
{
    (void)ticks;
    va_list args;
    va_start(args, fmt);
    vprintf(fmt, args);
    va_end(args);
    puts("");
}
static bool warn_on_pl_erase(void) { return strcmp(scenario, "cancel_replace"); }
static struct playlist_info *playlist_get_current(void) { return &current_pl; }
static char *playlist_get_name(void *pl, char *out, int size)
{
    (void)pl;
    snprintf(out, size, "%s", current_name);
    return out;
}
static int playlist_create(const char *dir, const char *name)
{
    char path[MAX_PATH], full[1400], line[1024];
    snprintf(path, sizeof(path), "%s/%s", dir, name);
    mapped(path, full, sizeof(full));
    FILE *f = fopen(full, "r");
    assert(f);
    amount = 0;
    while (fgets(line, sizeof(line), f))
    {
        assert(!strncmp(line, "/iPod_Control/Music/", 20));
        ++amount;
    }
    fclose(f);
    snprintf(current_name, sizeof(current_name), "%s", path);
    return 0;
}
static int playlist_amount(void) { return amount; }
static int playlist_shuffle(int seed, int index)
{
    (void)seed;
    ++shuffles;
    return amount - 1 - index;
}
static void playlist_start(int index, unsigned long elapsed, unsigned long offset)
{
    assert(index >= 0 && index < amount && !elapsed && !offset);
    started = index;
    audio_active = 1;
}
static int filetype_get_attr(const char *path)
{
    const char *ext = strrchr(path, '.');
    return ext && (!strcasecmp(ext, ".mp3") || !strcasecmp(ext, ".m4a") ||
                   !strcasecmp(ext, ".flac")) ? FILE_ATTR_AUDIO : 0;
}
static void simplelist_info_init(struct simplelist_info *info, char *title,
                                 int count, void *data)
{
    memset(info, 0, sizeof(*info));
    info->title = title;
    info->count = count;
    info->callback_data = data;
}
static bool simplelist_show_list(struct simplelist_info *info)
{
    assert(selection_at < selection_count);
    assert(info->action_callback(ACTION_STD_CONTEXT, NULL) == ACTION_STD_CONTEXT);
    for (int i = 0; i < info->count; ++i)
    {
        char name[260];
        assert(info->get_name(i, info->callback_data, name, sizeof(name)) == name);
        assert(*name);
    }
    int selected = selections[selection_at++];
    if (selected == -3)
    {
        struct gui_synclist lists = {.data = info->callback_data};
        assert(info->action_callback(SYS_USB_CONNECTED, &lists) == ACTION_STD_CANCEL);
        info->selection = -1;
        return false;
    }
    assert(selected < info->count);
    info->selection = selected;
    if (selected >= 0)
        assert(info->action_callback(ACTION_STD_OK, NULL) == ACTION_STD_CANCEL);
    return false;
}

#define open host_open
#define write host_write
#define remove host_remove
#define rename host_rename
#include "itunes-ui-under-test.c"
#undef open
#undef write
#undef remove
#undef rename

int main(int argc, char **argv)
{
    assert(argc == 3);
    snprintf(root, sizeof(root), "%s", argv[1]);
    snprintf(scenario, sizeof(scenario), "%s", argv[2]);
    selections[0] = 0; selections[1] = 1;
    selections[2] = -1; selections[3] = -1; selection_count = 4;
    bool expect_play = !strcmp(scenario, "play") || !strcmp(scenario, "shuffle") ||
                       !strcmp(scenario, "skip");
    if (expect_play) selection_count = 2;
    if (!strcmp(scenario, "usb_loading")) selection_count = 2;
    if (!strcmp(scenario, "skip")) selections[1] = 2;
    if (!strcmp(scenario, "shuffle")) global_settings.playlist_shuffle = true;
    if (!strcmp(scenario, "back")) { selections[0] = -1; selection_count = 1; }
    if (!strcmp(scenario, "usb")) { selections[0] = -3; selection_count = 1; }
    if (!strcmp(scenario, "wps"))
    {
        selections[0] = -2; selection_count = 1; audio_active = 1;
    }
    if (!strcmp(scenario, "empty"))
    {
        selections[0] = 1; selections[1] = -1; selection_count = 2;
    }
    if (!strcmp(scenario, "oom_members") || !strcmp(scenario, "bad_members"))
    {
        selections[0] = 0; selections[1] = -1; selection_count = 2;
    }
    if (!strcmp(scenario, "missing")) selections[1] = 0;
    if (!strcmp(scenario, "size_limit")) current_pl.max_playlist_size = 1;
    if (!strcmp(scenario, "party")) { global_settings.party_mode = true; audio_active = 1; }

    bool ret = podthings_itunes_playlists();
    assert(ret == (expect_play || !strcmp(scenario, "wps")));
    assert(active_allocs == 0);
    if (expect_play)
    {
        assert(amount == 2);
        assert(started == (!strcmp(scenario, "shuffle") ? 0 : 1));
        assert(shuffles == !strcmp(scenario, "shuffle"));
        assert(strstr(current_name, "itunes-playback-b.m3u8"));
    }
    else assert(started == -1);
    if (!strcmp(scenario, "back") || !strcmp(scenario, "empty") ||
        !strcmp(scenario, "usb") || !strcmp(scenario, "oom_index") ||
        !strcmp(scenario, "oom_members") || !strcmp(scenario, "missing") ||
        !strcmp(scenario, "no_db") || !strcmp(scenario, "bad_db") ||
        !strcmp(scenario, "bad_members") || !strcmp(scenario, "party"))
        assert(disk_writes == 0);
    assert(!file_exists(CACHE_TMP));
    assert(usb_handlers == (!strcmp(scenario, "usb") || !strcmp(scenario, "usb_loading")));
    return 0;
}
