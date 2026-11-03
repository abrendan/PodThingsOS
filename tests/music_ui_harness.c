/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Host shims for the real native music screen and recent-album code. */
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdarg.h>
#define MAX_PATH 260
#define HZ 100
#define ROCKBOX_DIR "/.podthingsloader"
#define PLUGIN_DEMOS_DIR ROCKBOX_DIR "/rocks/demos"
#define FILE_ATTR_MASK 0xff00
#define FILE_ATTR_AUDIO 0x0300
#define ACTION_STD_OK 1
#define ACTION_STD_CANCEL 2
#define YESNO_YES 1
enum {GO_TO_PREVIOUS = -2, GO_TO_WPS = 1, GO_TO_DBBROWSER, GO_TO_MUSIC_AZ,
      GO_TO_MUSIC_SEARCH, GO_TO_COVER_FLOW, GO_TO_PLAYLISTS_SCREEN,
      GO_TO_SHORTCUTMENU, GO_TO_FILEBROWSER, GO_TO_BROWSEPLUGINS,
      GO_TO_RECENTBMARKS, PLUGIN_GOTO_WPS, Icon_Audio, Icon_Playlist,
      Icon_Bookmark, Icon_file_view_menu, Icon_Plugin, Icon_Submenu_Entered,
      GO_TO_MUSIC,GO_TO_PREVIOUS_BROWSER,GO_TO_MUSIC_SHUFFLE};
enum {tag_filename, tag_album, tag_albumartist, tag_lastplayed,
      tag_discnumber, tag_tracknumber};
struct menu_item_ex {
    const char *label;
    int value;
    const struct menu_item_ex **items;
    int count;
};
#define MENUITEM_RETURNVALUE(n,l,v,cb,icon) \
    const struct menu_item_ex n = {l,v,NULL,0}
#define MENUITEM_SETTING_W_TEXT(n,var,l,cb) \
    const struct menu_item_ex n = {l,0,NULL,0}
#define MAKE_MENU(n,l,cb,icon,...) \
    const struct menu_item_ex *n##_items[] = {__VA_ARGS__}; \
    const struct menu_item_ex n = {l,0,n##_items,sizeof(n##_items)/sizeof(*n##_items)}
struct tagcache_search {int idx_id, position;};
struct playlist_info {int max_playlist_size;};
struct gui_synclist {int unused;};
struct text_message {const char **message_lines; int nb_lines;};
struct simplelist_info {
    int selection, count, title_icon;
    const char *(*get_name)(int,void*,char*,size_t);
    int (*action_callback)(int,struct gui_synclist*);
};
struct song {char path[64], album[64], artist[64]; long stamp, disc, track;};
static struct song songs[40];
static int song_count = 5, searches, started = -1, amount, allocated, saved, dialogs;
static bool usable = true;
static char root[1024], scenario[64], loaded[MAX_PATH];
static struct {bool party_mode, playlist_shuffle, runtimedb;} global_settings = {false,false,true};
static struct playlist_info playlist = {1000};
static void *allocation;
static int audio_status(void) {return !strcmp(scenario,"party");}
static void yield(void) {}
static void strmemccpy(char *out, const char *s, size_t n) {snprintf(out,n,"%s",s);}
static void splash(int ticks, const char *text) {(void)ticks; puts(text);}
static void splashf(int ticks, const char *fmt, ...)
{
    (void)ticks; va_list args; va_start(args,fmt); vprintf(fmt,args); va_end(args); puts("");
}
static int gui_syncyesno_run(const struct text_message *m, void *a, void *b)
{
    (void)a;(void)b;assert(m->nb_lines == 3);++dialogs;
    return strcmp(scenario,"decline_history") ? YESNO_YES : 0;
}
static void settings_save(void) {++saved;}
static bool tagcache_is_usable(void) {return usable;}
static bool tagcache_search(struct tagcache_search *s, int tag)
{
    assert(tag == tag_filename); s->position = 0; s->idx_id = -1; ++searches; return usable;
}
static bool tagcache_get_next(struct tagcache_search *s, char *buf, long n)
{
    if (s->position == song_count) return false;
    s->idx_id = s->position++;
    snprintf(buf,n,"%s",songs[s->idx_id].path); return true;
}
static bool tagcache_retrieve(struct tagcache_search *s, int index, int tag,
                              char *buf, long n)
{
    (void)s;
    assert(index >= 0 && index < song_count);
    const char *value = tag == tag_filename ? songs[index].path :
                        tag == tag_album ? songs[index].album : songs[index].artist;
    snprintf(buf,n,"%s",value); return true;
}
static long tagcache_get_numeric(struct tagcache_search *s, int tag)
{
    struct song *song = &songs[s->idx_id];
    return tag == tag_lastplayed ? song->stamp :
           tag == tag_discnumber ? song->disc : song->track;
}
static void tagcache_search_finish(struct tagcache_search *s) {(void)s;--searches;}
static int core_alloc(size_t n)
{
    if (!strcmp(scenario,"oom")) return -1;
    assert(!allocation); allocation = calloc(1,n);assert(allocation);++allocated;return 1;
}
static void *core_get_data_pinned(int h) {assert(h==1);return allocation;}
static void core_unpin(int h) {assert(h==1);}
static void core_free(int h) {assert(h==1);free(allocation);allocation=NULL;--allocated;}
static void mapped(const char *path, char *out, size_t n)
{
    assert(path[0]=='/' && !strstr(path,".."));
    int len=snprintf(out,n,"%s%s",root,path);assert(len>0 && (size_t)len<n);
}
static bool file_exists(const char *path)
{
    char full[1400];mapped(path,full,sizeof(full));return access(full,F_OK)==0;
}
static int host_open(const char *path,int flags,...)
{
    assert(!strncmp(path,ROCKBOX_DIR "/",sizeof(ROCKBOX_DIR)));
    if (!strcmp(scenario,"storage_error")) return -1;
    char full[1400];mapped(path,full,sizeof(full));return open(full,flags,0666);
}
static int host_remove(const char *path)
{
    assert(!strncmp(path,ROCKBOX_DIR "/",sizeof(ROCKBOX_DIR)));
    char full[1400];mapped(path,full,sizeof(full));return remove(full);
}
static int host_rename(const char *from,const char *to)
{
    assert(strcmp(to,ROCKBOX_DIR "/recent-album-a.m3u8"));
    char a[1400],b[1400];mapped(from,a,sizeof(a));mapped(to,b,sizeof(b));return rename(a,b);
}
static int filetype_get_attr(const char *path) {(void)path;return FILE_ATTR_AUDIO;}
static bool warn_on_pl_erase(void) {return strcmp(scenario,"cancel");}
static struct playlist_info *playlist_get_current(void) {return &playlist;}
static char *playlist_get_name(void *p,char *buf,int n)
{(void)p;snprintf(buf,n,"%s",ROCKBOX_DIR "/recent-album-a.m3u8");return buf;}
static int playlist_create(const char *dir,const char *name)
{
    snprintf(loaded,sizeof(loaded),"%s/%s",dir,name);
    char full[1400],line[MAX_PATH];mapped(loaded,full,sizeof(full));
    FILE *f=fopen(full,"r");assert(f);amount=0;
    while(fgets(line,sizeof(line),f))
    {
        if (!strcmp(scenario,"play")) {
            const char *want=amount==0 ? "/Music/A1.mp3\n" : "/Music/A2.mp3\n";
            assert(!strcmp(line,want));
        }
        ++amount;
    }
    fclose(f);return 0;
}
static int playlist_amount(void) {return amount;}
static int playlist_shuffle(int seed,int index) {(void)seed;return amount-1-index;}
static void playlist_start(int index,unsigned long elapsed,unsigned long offset)
{assert(!elapsed && !offset);started=index;}
static int plugin_load(const char *path,const void *arg)
{
    assert(!strcmp(path,PLUGIN_DEMOS_DIR "/pictureflow.rock"));
    assert(!arg || !strcmp(arg,"podthings:album"));
    return PLUGIN_GOTO_WPS;
}
static int do_menu(const struct menu_item_ex *menu,int *selection,void *a,bool b)
{
    (void)selection;(void)a;(void)b;
    assert(menu->count>0);
    if (!strcmp(menu->label,"Music"))
    {
        assert(menu->count==7);
        assert(!strcmp(menu->items[1]->label,"A-Z Jump"));
        assert(!strcmp(menu->items[3]->label,"Cover Flow"));
        assert(!strcmp(menu->items[5]->label,"Shuffle Songs"));
        assert(menu->items[5]->value==GO_TO_MUSIC_SHUFFLE);
        return menu->items[3]->value;
    }
    assert(!strcmp(menu->label,"Extras"));return GO_TO_FILEBROWSER;
}
static void simplelist_info_init(struct simplelist_info *i,char *title,int count,void *data)
{(void)data;assert(!strcmp(title,"Recently Played Albums"));memset(i,0,sizeof(*i));i->count=count;}
static bool simplelist_show_list(struct simplelist_info *i)
{
    static int calls;
    char label[260];
    assert(searches==0);
    assert(i->action_callback(ACTION_STD_OK,NULL)==ACTION_STD_CANCEL);
    if (!calls++) {
        i->get_name(0,NULL,label,sizeof(label));
        assert(!strcmp(label,"A - Artist A"));
        i->selection=0;
    } else i->selection=-1;
    return false;
}
#define open host_open
#define remove host_remove
#define rename host_rename
#include "music-ui-under-test.c"
#undef open
#undef remove
#undef rename

int main(int argc,char **argv)
{
    assert(argc==3);snprintf(root,sizeof(root),"%s",argv[1]);snprintf(scenario,sizeof(scenario),"%s",argv[2]);
    songs[0]=(struct song){"/Music/B2.mp3","B","Artist B",10,1,2};
    songs[1]=(struct song){"/Music/A2.mp3","A","Artist A",5,1,2};
    songs[2]=(struct song){"/Music/A1.mp3","A","Artist A",30,1,1};
    songs[3]=(struct song){"/Music/B1.mp3","B","Artist B",20,1,1};
    songs[4]=(struct song){"/Music/C1.mp3","C","Artist C",0,1,1};
    assert(podthings_music_menu(NULL)==GO_TO_COVER_FLOW);
    assert(podthings_extras_menu(NULL)==GO_TO_FILEBROWSER);
    assert(podthings_coverflow(NULL)==GO_TO_WPS);
    assert(podthings_coverflow_wps_return(GO_TO_PREVIOUS_BROWSER)==GO_TO_COVER_FLOW);
    assert(podthings_coverflow(NULL)==GO_TO_WPS);
    assert(podthings_coverflow_wps_return(GO_TO_PREVIOUS)==GO_TO_COVER_FLOW);
    assert(podthings_coverflow_wps_return(GO_TO_MUSIC)==GO_TO_MUSIC);
    assert(podthings_coverflow_wps_return(GO_TO_PREVIOUS)==GO_TO_PREVIOUS);
    usable=false;assert(podthings_coverflow(NULL)==GO_TO_PREVIOUS);usable=true;
    if (!strcmp(scenario,"empty"))
        for(int i=0;i<song_count;++i) songs[i].stamp=0;
    if (!strcmp(scenario,"enable_history") || !strcmp(scenario,"decline_history"))
        global_settings.runtimedb=false;
    if (!strcmp(scenario,"size_limit")) playlist.max_playlist_size=1;
    if (!strcmp(scenario,"party")) global_settings.party_mode=true;
    if (!strcmp(scenario,"shuffle")) global_settings.playlist_shuffle=true;
    int ret=podthings_recent_albums(NULL);
    bool playing=!strcmp(scenario,"play") || !strcmp(scenario,"enable_history") ||
                 !strcmp(scenario,"shuffle") || !strcmp(scenario,"missing");
    assert(ret==(playing ? GO_TO_WPS : GO_TO_PREVIOUS));
    assert(searches==0 && allocated==0);
    if(playing) {
        assert(amount==(!strcmp(scenario,"missing") ? 1 : 2));
        assert(started==(!strcmp(scenario,"shuffle") ? 1 : 0));
    } else assert(started==-1);
    if(!strcmp(scenario,"enable_history")) assert(saved==1 && dialogs==1 && global_settings.runtimedb);
    if(!strcmp(scenario,"decline_history")) assert(!saved && dialogs==1 && !global_settings.runtimedb);
    assert(!file_exists(ROCKBOX_DIR "/recent-album.tmp"));
    /* Aggregation uses the most recent track in an album, not the first one,
     * and keeps only the newest 24 distinct album/album-artist groups. */
    song_count=32;
    for(int i=0;i<song_count;++i) {
        snprintf(songs[i].path,sizeof(songs[i].path),"/Music/%d.mp3",i);
        snprintf(songs[i].album,sizeof(songs[i].album),"Album %d",i);
        strcpy(songs[i].artist,"Artist");songs[i].stamp=i+1;
    }
    assert(collect_recent() && recent_count==24);
    assert(recent[0].stamp==32 && recent[23].stamp==9);
    songs[0]=songs[31];songs[0].stamp=50;
    assert(collect_recent() && recent_count==24);
    assert(recent[0].stamp==50 && !strcmp(recent[0].album,"Album 31"));
    return 0;
}
