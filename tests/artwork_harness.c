/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Compile the production reader, not a reimplementation. Never an iPod simulator. */
#define _POSIX_C_SOURCE 200809L
#define PODTHINGS_ART_HOST
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <pthread.h>
#include <sched.h>
#define ROCKBOX_DIR "/.podthingsloader"
#define MAX_PATH 260
static char root[1024];
struct mutex {pthread_mutex_t native;};
static void mutex_init(struct mutex *m) {assert(!pthread_mutex_init(&m->native,NULL));}
static void mutex_lock(struct mutex *m) {assert(!pthread_mutex_lock(&m->native));}
static void mutex_unlock(struct mutex *m) {assert(!pthread_mutex_unlock(&m->native));}
static int disable_irq_save(void) {return 0;}
static void restore_irq(int x) {(void)x;}
static void yield(void) {sched_yield();}
enum { SYS_EVENT_USB_EXTRACTED = 0x8002 };
static void (*usb_callback)(unsigned short, void *);
static bool add_event(unsigned short id, void (*fn)(unsigned short, void *))
{
    assert(id == SYS_EVENT_USB_EXTRACTED);
    usb_callback=fn;
    return true;
}
static off_t host_size(int fd) {struct stat s;return fstat(fd,&s)<0?-1:s.st_size;}
static void map(const char *p,char *out,size_t n) {
    assert(p[0]=='/' && !strstr(p,".."));
    int len=snprintf(out,n,"%s%s",root,p);assert(len>0 && (size_t)len<n);
}
static int host_open(const char *p,int flags,...) {
    if(flags & (O_WRONLY|O_RDWR|O_CREAT|O_TRUNC))
        assert(!strncmp(p,ROCKBOX_DIR "/",sizeof(ROCKBOX_DIR)));
    char out[1400];map(p,out,sizeof(out));return open(out,flags,0666);
}
static int host_remove(const char *p) {
    assert(!strncmp(p,ROCKBOX_DIR "/",sizeof(ROCKBOX_DIR)));
    char out[1400];map(p,out,sizeof(out));return remove(out);
}
static int host_rename(const char *p,const char *to) {
    assert(!strncmp(p,ROCKBOX_DIR "/",sizeof(ROCKBOX_DIR)));
    assert(!strncmp(to,ROCKBOX_DIR "/",sizeof(ROCKBOX_DIR)));
    char a[1400],b[1400];map(p,a,sizeof(a));map(to,b,sizeof(b));return rename(a,b);
}
static int host_mkdir(const char *p) {
    assert(!strncmp(p,ROCKBOX_DIR "/",sizeof(ROCKBOX_DIR)));
    char out[1400];map(p,out,sizeof(out));return mkdir(out,0777);
}
static bool file_exists(const char *p) {
    char out[1400];map(p,out,sizeof(out));return access(out,F_OK)==0;
}
#define open host_open
#define remove host_remove
#define rename host_rename
#define mkdir host_mkdir
#define ffilesize host_size
#include "../rockbox-firmware/apps/podthings_artwork.c"

static void *artwork_worker(void *arg)
{
    const char *track=arg;
    for(int i=0;i<20;i++) {
        char out[MAX_PATH]={0};
        assert(podthings_itunes_art(track,out,sizeof(out)));
        assert(file_exists(out));
    }
    return NULL;
}

int main(int argc,char **argv) {
    assert(argc>=4);
    snprintf(root,sizeof(root),"%s",argv[1]);
    for(int i=0;i<2;i++) {
        char out[MAX_PATH]={0};
        bool ok=podthings_itunes_art(argv[2],out,sizeof(out));
        assert(ok==atoi(argv[3]));
        if(ok) {
            assert(file_exists(out));
            printf("%s\n",out);
            assert(!strncmp(out,ROCKBOX_DIR "/itunes-art/",sizeof(ROCKBOX_DIR)+11));
        }
    }
    if(argc>4 && !strcmp(argv[4],"threads")) {
        /* Initialize via the serial calls above, then make the first worker
         * convert again rather than only testing an already-cached bitmap. */
        char out[MAX_PATH]={0};
        assert(podthings_itunes_art(argv[2],out,sizeof(out)));
        assert(remove(out)==0);
        pthread_t threads[4];
        for(int i=0;i<4;i++)
            assert(!pthread_create(&threads[i],NULL,artwork_worker,argv[2]));
        for(int i=0;i<4;i++) assert(!pthread_join(threads[i],NULL));
    }
    if(argc>4 && !strcmp(argv[4],"usb")) {
        assert(usb_callback);
        uint32_t hash=pa_hashes[0];
        pa_hashes[0]^=12345;
        usb_callback(SYS_EVENT_USB_EXTRACTED,NULL);
        char out[MAX_PATH];
        assert(podthings_itunes_art(argv[2],out,sizeof(out)));
        assert(pa_hashes[0]==hash && pa_seen_usb_epoch==pa_usb_epoch);
    }
    for(int fd=3;fd<128;fd++) assert(fcntl(fd,F_GETFD)==-1);
    return 0;
}
