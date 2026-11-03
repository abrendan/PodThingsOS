/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Read-only classic ArtworkDB/ITHMB reader. Format references:
 * libgpod db-itunes-parser.h, itdb_itunesdb.c, db-artwork-parser.c,
 * itdb_device.c; independently implemented, no libgpod code is copied.
 * Native Video/Classic cover formats are little-endian RGB565 canvases.
 */
#if !defined(PODTHINGS_ART_HOST) && !defined(PLUGIN)
#include "config.h"
#include "system.h"
#include "kernel.h"
#include "file.h"
#include "dir.h"
#include "metadata.h"
#include "settings.h"
#include "events.h"
#include "string-extra.h"
#include <stdio.h>
#endif
#include <stdint.h>
#include <string.h>
#include "podthings_artwork.h"
#include "podthings_itunesdb.h"

#define PA_DIR ROCKBOX_DIR "/itunes-art"
#define PA_INDEX PA_DIR "/index"
#ifdef PLUGIN
#define PA_TEMP PA_DIR "/index.plugin.tmp"
#define PA_BMP_TEMP ".plugin.tmp"
#else
#define PA_TEMP PA_DIR "/index.core.tmp"
#define PA_BMP_TEMP ".core.tmp"
#endif
#define PA_DB "/iPod_Control/iTunes/iTunesDB"
#define PA_ADB "/iPod_Control/Artwork/ArtworkDB"
#define PA_MAGIC 0x50415433u
#define PA_BUCKETS 256
#define PA_MAX_DB (256u * 1024 * 1024)
#define PA_MAX_INDEX (16u * 1024 * 1024)
struct pa_header {
    uint32_t magic, size[2], hash[2], buckets[3][PA_BUCKETS];
};
struct pa_record {uint32_t at, head, end;};
struct pa_row {uint32_t next, lo, hi, at;};
struct pa_thumb {
    char path[MAX_PATH];
    uint32_t offset, bytes;
    unsigned canvas, width, height, x, y;
};
static struct pa_header pa_header;
static struct mutex pa_mutex;
static bool pa_initialized;
static bool pa_rechecked;
static uint32_t pa_sizes[2], pa_samples[2], pa_hashes[2];
#if !defined(PLUGIN)
/* USB events must not wait for the artwork mutex: the audio thread may be
 * parked for USB. Invalidate lazily in the next serialized lookup instead. */
static volatile unsigned pa_usb_epoch;
static unsigned pa_seen_usb_epoch;
static void pa_usb_changed(unsigned short id, void *data)
{
    (void)id; (void)data;
    ++pa_usb_epoch;
}
#endif

static uint32_t pa_le32(const unsigned char *p)
{return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;}
static unsigned pa_le16(const unsigned char *p) {return p[0] | (unsigned)p[1]<<8;}
static void pa_put32(unsigned char *p, uint32_t v)
{for (int i=0;i<4;i++) p[i]=(v>>(i*8))&255;}
static bool pa_read(void *ctx, uint32_t pos, void *out, size_t n)
{
    int fd=*(int *)ctx;
    return lseek(fd,pos,SEEK_SET)==(off_t)pos && read(fd,out,n)==(ssize_t)n;
}
static bool pa_record(int fd, uint32_t pos, uint32_t end, const char *tag,
                      unsigned min, struct pa_record *r)
{
    unsigned char b[12];
    if (pos>end || end-pos<min || min<12 ||
        !pa_read(&fd,pos,b,12) || memcmp(b,tag,4)) return false;
    r->at=pos; r->head=pa_le32(b+4);
    uint32_t total=pa_le32(b+8);
    if (r->head<min || r->head>total || total>end-pos) return false;
    r->end=pos+total; return true;
}
static bool pa_num(int fd, uint32_t at, uint32_t *out)
{
    unsigned char b[4]; if (!pa_read(&fd,at,b,4)) return false;
    *out=pa_le32(b); return true;
}
static uint32_t pa_hash(uint32_t hash, const void *data, size_t n)
{
    const unsigned char *p=data;
    while(n--) hash=(hash^*p++)*16777619u;
    return hash;
}
static void pa_path_hash(const char *path, uint32_t *lo, uint32_t *hi)
{
    *lo=2166136261u; *hi=0x9e3779b9u;
    while(*path) {
        unsigned char c=*path++;
        if(c>='A' && c<='Z') c+='a'-'A';
        *lo=pa_hash(*lo,&c,1); *hi=pa_hash(*hi,&c,1);
    }
}
static bool pa_fingerprint(int fd, int which)
{
    off_t length=ffilesize(fd);
    if(length<24 || length>(off_t)PA_MAX_DB) return false;
    /* All private artwork helpers run under pa_mutex. Keep large scratch
     * buffers off callers' small stacks (notably the audio thread). */
    static unsigned char block[1024];
    uint32_t size=length, sample=2166136261u;
    unsigned n=size<sizeof(block)?size:sizeof(block);
    if(!pa_read(&fd,0,block,n)) return false;
    sample=pa_hash(sample,block,n);
    if(!pa_read(&fd,size-n,block,n)) return false;
    sample=pa_hash(sample,block,n);
    if(pa_sizes[which]!=size || pa_samples[which]!=sample) {
        uint32_t hash=2166136261u;
        for(uint32_t at=0;at<size;) {
            n=size-at<sizeof(block)?size-at:sizeof(block);
            if(!pa_read(&fd,at,block,n)) return false;
            hash=pa_hash(hash,block,n); at+=n; yield();
        }
        pa_sizes[which]=size;pa_samples[which]=sample;pa_hashes[which]=hash;
        pa_rechecked=false;
    }
    return true;
}
static bool pa_store(int fd, unsigned table, uint32_t lo,uint32_t hi,uint32_t at)
{
    unsigned bucket=(lo^hi)&(PA_BUCKETS-1);
    off_t pos=lseek(fd,0,SEEK_END);
    struct pa_row row={pa_header.buckets[table][bucket],lo,hi,at};
    if(pos<(off_t)sizeof(pa_header) || pos>(off_t)(PA_MAX_INDEX-sizeof(row)) ||
       write(fd,&row,sizeof(row))!=sizeof(row)) return false;
    pa_header.buckets[table][bucket]=pos;return true;
}
static bool pa_track_path(struct itdb *db, uint32_t at, char *path, size_t size,
                          uint32_t *lo,uint32_t *hi,uint32_t *link)
{
    struct pa_record r,m;
    int fd=*(int *)db->context;
    uint32_t count,type,pos;
    if(!pa_record(fd,at,db->tracks_end,"mhit",120,&r) ||
       !pa_num(fd,at+12,&count) || count>(r.end-at-r.head)/16 ||
       !pa_num(fd,at+112,lo) || !pa_num(fd,at+116,hi)) return false;
    *link=0;
    if(r.head>=356 && !pa_num(fd,at+352,link)) return false;
    pos=at+r.head;
    for(uint32_t i=0;i<count;i++) {
        if(!pa_record(fd,pos,r.end,"mhod",16,&m) || !pa_num(fd,pos+12,&type))
            return false;
        if(type==2) {
            struct itdb_track t={0};t.path=pos;
            return itdb_path(db,&t,path,size);
        }
        pos=m.end;
    }
    return false;
}
static bool pa_build(int out, struct itdb *db, int artwork, uint32_t art_size)
{
    memset(&pa_header,0,sizeof(pa_header));
    pa_header.magic=PA_MAGIC;
    for(int i=0;i<2;i++) {pa_header.size[i]=pa_sizes[i];pa_header.hash[i]=pa_hashes[i];}
    if(write(out,&pa_header,sizeof(pa_header))!=sizeof(pa_header)) return false;
    uint32_t pos=db->tracks_at;
    int fd=*(int *)db->context;
    for(uint32_t i=0;i<db->track_count;i++) {
        struct pa_record r;
        char path[MAX_PATH];uint32_t lo,hi,link;
        if(!pa_record(fd,pos,db->tracks_end,"mhit",20,&r)) return false;
        if(r.head>=120 && pa_track_path(db,pos,path,sizeof(path),&lo,&hi,&link)) {
            pa_path_hash(path,&lo,&hi);
            if(!pa_store(out,0,lo,hi,pos)) return false;
        }
        pos=r.end;yield();
    }
    struct pa_record root,section,image;
    uint32_t count,type,images,at;
    if(!pa_record(artwork,0,art_size,"mhfd",24,&root) ||
       !pa_num(artwork,20,&count) || count>(root.end-root.head)/16) return false;
    pos=root.head;bool found=false;
    for(uint32_t i=0;i<count;i++) {
        if(!pa_record(artwork,pos,root.end,"mhsd",16,&section) ||
           !pa_num(artwork,pos+12,&type)) return false;
        if((type&0xffff)==1) {
            unsigned char list[12];
            at=pos+section.head;
            if(found || !pa_read(&artwork,at,list,12) || memcmp(list,"mhli",4))
                return false;
            uint32_t head=pa_le32(list+4);images=pa_le32(list+8);
            if(head<12 || head>section.end-at || images>200000 ||
               images>(section.end-at-head)/28) return false;
            at+=head;found=true;
            for(uint32_t j=0;j<images;j++) {
                uint32_t id,lo,hi;
                /* A bounded record with an unusable image header must not
                 * suppress every other album. Never guess past a broken
                 * length: only skip when the next boundary is trustworthy. */
                unsigned char span[12];
                if(at>section.end || section.end-at<sizeof(span) ||
                   !pa_read(&artwork,at,span,sizeof(span)) ||
                   memcmp(span,"mhii",4)) return false;
                uint32_t total=pa_le32(span+8);
                if(total<12 || total>section.end-at) return false;
                image.head=pa_le32(span+4);image.end=at+total;
                /* A bad header length does not invalidate a trustworthy
                 * total record boundary or artwork for unrelated albums. */
                if(image.head>=28 && image.head<=total &&
                   pa_num(artwork,at+16,&id) &&
                   pa_num(artwork,at+20,&lo) && pa_num(artwork,at+24,&hi)) {
                    if((lo||hi) && !pa_store(out,1,lo,hi,at)) return false;
                    if(id && !pa_store(out,2,id,0,at)) return false;
                }
                at=image.end;yield();
            }
        }
        pos=section.end;
    }
    return found && lseek(out,0,SEEK_SET)==0 &&
           write(out,&pa_header,sizeof(pa_header))==sizeof(pa_header);
}
static int pa_index(struct itdb *db,int art, bool force)
{
    if(!pa_fingerprint(*(int *)db->context,0) || !pa_fingerprint(art,1)) return -1;
    int fd=open(PA_INDEX,O_RDONLY);
    if(fd>=0) {
        bool ok=!force && read(fd,&pa_header,sizeof(pa_header))==sizeof(pa_header) &&
                pa_header.magic==PA_MAGIC && ffilesize(fd)<=(off_t)PA_MAX_INDEX;
        for(int i=0;i<2;i++)
            ok=ok && pa_header.size[i]==pa_sizes[i] && pa_header.hash[i]==pa_hashes[i];
        if(ok) return fd;
        close(fd);
    }
    mkdir(PA_DIR);
    fd=open(PA_TEMP,O_WRONLY|O_CREAT|O_TRUNC,0666);
    if(fd<0) return -1;
    bool ok=pa_build(fd,db,art,pa_sizes[1]);
    if(close(fd)<0) ok=false;
    if(!ok || rename(PA_TEMP,PA_INDEX)<0) {remove(PA_TEMP);return -1;}
    return open(PA_INDEX,O_RDONLY);
}
static uint32_t pa_lookup(int fd,unsigned table,uint32_t lo,uint32_t hi)
{
    uint32_t at=pa_header.buckets[table][(lo^hi)&255];
    off_t size=ffilesize(fd);
    for(unsigned n=0;at && n<500000;n++) {
        struct pa_row r;
        if(at<sizeof(pa_header) || at>(uint32_t)size ||
           (uint32_t)size-at<sizeof(r) || !pa_read(&fd,at,&r,sizeof(r))) return 0;
        if(r.lo==lo && r.hi==hi) return r.at;
        /* Links are strictly backwards: reject cycles and corrupt caches. */
        if(r.next>=at) return 0;
        at=r.next;
    }
    return 0;
}

/* ArtworkDB can contain more than one image with a shared ID/DBID after a
 * sync. Return successive matching rows rather than letting the last, broken
 * image mask older usable thumbnails. Caller bounds attempts independently. */
static uint32_t pa_next_image(int fd,uint32_t lo,uint32_t hi,
                              uint32_t *cursor)
{
    uint32_t at=*cursor;
    off_t size=ffilesize(fd);
    for(unsigned n=0;at && n<500000;n++) {
        struct pa_row r;
        if(at<sizeof(pa_header) || at>(uint32_t)size ||
           (uint32_t)size-at<sizeof(r) || !pa_read(&fd,at,&r,sizeof(r)) ||
           r.next>=at) break;
        at=r.next;
        if(r.lo==lo && r.hi==hi) {*cursor=at;return r.at;}
    }
    *cursor=0;return 0;
}
static unsigned pa_canvas(uint32_t format)
{
    switch(format) {
    /* Photo/Color cover art, RGB565 little endian (not photo-library tiles). */
    case 1017:return 56; case 1016:return 140;
    case 1028:return 100; case 1029:return 200;
    case 1061:return 56; case 1055:case 1068:return 128;
    case 1060:return 320; default:return 0;
    }
}
static bool pa_thumb(int fd,uint32_t at,uint32_t end,struct pa_thumb *thumb)
{
    struct pa_record mhni,name;
    unsigned char b[36];
    if(!pa_record(fd,at,end,"mhni",36,&mhni) || !pa_read(&fd,at,b,sizeof(b)))
        return false;
    unsigned canvas=pa_canvas(pa_le32(b+16));
    unsigned right=pa_le16(b+34),bottom=pa_le16(b+32);
    int x=(int16_t)pa_le16(b+30),y=(int16_t)pa_le16(b+28);
    /* Apple's dimensions include the leading padding: they are the right
     * and bottom bounds, NOT pixel extents to add to x/y a second time.
     * Rectangular covers often use the entire canvas in the other axis. */
    if(!canvas || x<0 || y<0 || right<=(unsigned)x || bottom<=(unsigned)y ||
       right>canvas || bottom>canvas ||
       pa_le32(b+24)<canvas*canvas*2) return false;
    unsigned width=right-x,height=bottom-y;
    if(!pa_record(fd,at+mhni.head,mhni.end,"mhod",24,&name) ||
       name.end-name.at<36 ||
       !pa_read(&fd,name.at,b,sizeof(b)) || pa_le16(b+12)!=3) return false;
    uint32_t bytes=pa_le32(b+24),start=name.at+36;
    if(!bytes || bytes>name.end-start || bytes>240) return false;
    unsigned char raw[240];
    if(!pa_read(&fd,start,raw,bytes)) return false;
    char base[121];unsigned used=0;
    if(b[28]==2) {
        if(bytes&1) return false;
        for(unsigned i=0;i<bytes;i+=2) {
            unsigned c=pa_le16(raw+i);
            if(!c && i+2==bytes) break;
            if(!c || c>127 || used>=sizeof(base)-1) return false;
            base[used++]=c;
        }
    } else if(b[28]<=1) {
        for(unsigned i=0;i<bytes;i++) {
            if(!raw[i] && i+1==bytes) break;
            if(!raw[i] || raw[i]>127 || used>=sizeof(base)-1) return false;
            base[used++]=raw[i];
        }
    } else return false;
    base[used]=0;
    /* Only accept a basename in Apple's Artwork directory; no traversal. */
    const char *file=base[0]==':'?base+1:base;
    if(!*file || strchr(file,':') || strchr(file,'/') || strchr(file,'\\') ||
       strstr(file,"..") || !strstr(file,".ithmb")) return false;
    if(snprintf(thumb->path,sizeof(thumb->path),"/iPod_Control/Artwork/%s",file)
       >=(int)sizeof(thumb->path)) return false;
    thumb->canvas=canvas;thumb->width=width;thumb->height=height;
    thumb->x=x;thumb->y=y;
    if(!pa_read(&fd,at,b,28)) return false;
    thumb->offset=pa_le32(b+20);thumb->bytes=canvas*canvas*2;
    return true;
}
static bool pa_choose(int fd,uint32_t at,uint32_t end,struct pa_thumb *best)
{
    struct pa_record image,child;
    uint32_t count,type;
    if(!pa_record(fd,at,end,"mhii",28,&image) || !pa_num(fd,at+12,&count) ||
       count>(image.end-at-image.head)/16) return false;
    at+=image.head;memset(best,0,sizeof(*best));
    for(uint32_t i=0;i<count;i++) {
        if(!pa_record(fd,at,image.end,"mhod",16,&child) ||
           !pa_num(fd,at+12,&type)) break;
        struct pa_thumb candidate;
        if((type&0xffff)==2 && pa_thumb(fd,at+child.head,child.end,&candidate) &&
           candidate.width*candidate.height>best->width*best->height) {
            int file=open(candidate.path,O_RDONLY);
            if(file>=0) {
                off_t size=ffilesize(file);
                if(size>=0 && candidate.offset<=(uint32_t)size &&
                   candidate.bytes<=(uint32_t)size-candidate.offset)
                    *best=candidate;
                close(file);
            }
        }
        at=child.end;
    }
    return best->canvas!=0;
}
static bool pa_bitmap(const struct pa_thumb *t,char *out,size_t size)
{
    int in=open(t->path,O_RDONLY);
    if(in<0) return false;
    off_t length=ffilesize(in);
    if(t->offset>(uint32_t)length || t->bytes>(uint32_t)length-t->offset) {
        close(in);return false;
    }
    /* pa_mutex covers hashing, conversion and all yields in this helper.
     * Core and plugin builds each own their own copy of these buffers. */
    static unsigned char row[960];
    uint32_t hash=2166136261u;
    for(uint32_t at=0;at<t->bytes;) {
        unsigned n=t->bytes-at<sizeof(row)?t->bytes-at:sizeof(row);
        if(!pa_read(&in,t->offset+at,row,n)) {close(in);return false;}
        hash=pa_hash(hash,row,n);at+=n;yield();
    }
    if(snprintf(out,size,PA_DIR "/%08lx-%ux%u-%u-%u.bmp",
       (unsigned long)hash,t->width,t->height,t->x,t->y)>=(int)size) {
        close(in);return false;
    }
    unsigned stride=(t->width*3+3)&~3u;
    unsigned char header[54]={ 'B','M' };
    pa_put32(header+2,54+stride*t->height);pa_put32(header+10,54);
    pa_put32(header+14,40);pa_put32(header+18,t->width);
    pa_put32(header+22,t->height);header[26]=1;header[28]=24;
    pa_put32(header+34,stride*t->height);
    int cached=open(out,O_RDONLY);
    if(cached>=0) {
        bool valid=ffilesize(cached)==(off_t)(54+stride*t->height) &&
                   read(cached,row,54)==54 && !memcmp(header,row,54);
        close(cached);
        if(valid) {close(in);return true;}
        remove(out); /* Disposable derived bitmap, never Apple data. */
    }
    static char temp[MAX_PATH]; /* pa_mutex held through rename/cleanup */
    if(snprintf(temp,sizeof(temp),"%s" PA_BMP_TEMP,out)>=(int)sizeof(temp)) {
        close(in);return false;
    }
    int fd=open(temp,O_WRONLY|O_CREAT|O_TRUNC,0666);
    if(fd<0) {close(in);return false;}
    bool ok=write(fd,header,54)==54;
    static unsigned char source[640];
    for(unsigned y=0;ok && y<t->height;y++) {
        uint32_t off=t->offset+((t->y+t->height-1-y)*t->canvas+t->x)*2;
        ok=pa_read(&in,off,source,t->width*2);memset(row,0,stride);
        for(unsigned x=0;ok && x<t->width;x++) {
            unsigned pixel=pa_le16(source+x*2);
            row[x*3]=(pixel&31)*255/31;
            row[x*3+1]=((pixel>>5)&63)*255/63;
            row[x*3+2]=((pixel>>11)&31)*255/31;
        }
        if(ok) ok=write(fd,row,stride)==(ssize_t)stride;
        yield();
    }
    close(in);if(close(fd)<0) ok=false;
    if(ok) ok=rename(temp,out)==0;
    if(!ok) remove(temp);
    return ok;
}
bool podthings_itunes_art(const char *track,char *out,size_t size)
{
    if(!track || strncasecmp(track,"/iPod_Control/Music/",20)) return false;
    int old=disable_irq_save();
    if(!pa_initialized) {
        mutex_init(&pa_mutex);
#if !defined(PLUGIN)
        add_event(SYS_EVENT_USB_EXTRACTED, pa_usb_changed);
#endif
        pa_initialized=true;
    }
    restore_irq(old);
    mutex_lock(&pa_mutex);
#if !defined(PLUGIN)
    if(pa_seen_usb_epoch!=pa_usb_epoch) {
        pa_seen_usb_epoch=pa_usb_epoch;
        memset(pa_sizes,0,sizeof(pa_sizes));
        pa_rechecked=false;
    }
#endif
    bool result=false;int music=open(PA_DB,O_RDONLY),art=open(PA_ADB,O_RDONLY);
    if(music<0 || art<0) goto done;
    struct itdb db;
    off_t length=ffilesize(music);
    if(length<24 || length>(off_t)PA_MAX_DB ||
       !itdb_open(&db,pa_read,&music,length)) goto done;
    for(int attempt=0;attempt<2;attempt++) {
        /* A missing cover is normal: never rescan/rewrite the entire library
         * for every album without art. Permit one stale-index retry per source
         * fingerprint, not one rebuild per track. */
        if(attempt && pa_rechecked) break;
        if(attempt) pa_rechecked=true;
        int index=pa_index(&db,art,attempt!=0);
        if(index<0) break;
        uint32_t lo,hi,id,link,at,hash1,hash2;
        static char actual[MAX_PATH]; /* pa_mutex held for the whole lookup */
        pa_path_hash(track,&hash1,&hash2);
        at=pa_lookup(index,0,hash1,hash2);
        bool matched=at && pa_track_path(&db,at,actual,sizeof(actual),&lo,&hi,&link)
                       && !strcasecmp(actual,track);
        for(int candidate=0;matched && candidate<2 && !result;candidate++) {
            unsigned table=candidate==0?2:1;
            uint32_t keylo=candidate==0?link:lo, keyhi=candidate==0?0:hi;
            if(!keylo && !keyhi) continue;
            uint32_t cursor=pa_header.buckets[table][(keylo^keyhi)&255];
            for(unsigned n=0;cursor && n<64 && !result;n++) {
            uint32_t image=pa_next_image(index,keylo,keyhi,&cursor);
            if(!image) break;
            /* Revalidate against current source, including same-size re-syncs. */
            uint32_t alo,ahi;
            if(!pa_num(art,image+16,&id) || !pa_num(art,image+20,&alo) ||
               !pa_num(art,image+24,&ahi) ||
               !(candidate==0 ? link && id==link : lo==alo && hi==ahi)) continue;
            struct pa_thumb thumb={0};
            if(pa_choose(art,image,pa_sizes[1],&thumb))
                result=pa_bitmap(&thumb,out,size);
            }
        }
        close(index);
        if(result) break;
        if(matched && !link && !lo && !hi) break;
    }
done:
    if(music>=0) close(music);
    if(art>=0) close(art);
    mutex_unlock(&pa_mutex);return result;
}
