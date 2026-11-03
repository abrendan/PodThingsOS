"""Bounded Apple artwork parsing/conversion with real files and sanitizers."""
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

from test_itunes_playlists import chunk, database, text
from test_ipod_battery import function

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "rockbox-firmware/apps"
TRACK = "/iPod_Control/Music/F00/ABCD.mp3"
FORMATS = {1017: 56, 1016: 140, 1028: 100, 1029: 200, 1061: 56,
           1055: 128, 1068: 128, 1060: 320}


def music(link=0, dbid=0x123456789ABCDEF0):
    body = text(2, TRACK.replace("/", ":"))
    record = bytearray(chunk("mhit", 384, body, {12: 1, 16: 1, 352: link}))
    struct.pack_into("<Q", record, 112, dbid)
    return database([bytes(record)])


def thumb(fmt=1055, offset=0, filename=None, padding=0, encoding=2):
    canvas = FORMATS.get(fmt, 128)
    filename = filename or f":F{fmt}_1.ithmb"
    payload = filename.encode("utf-16le" if encoding == 2 else "ascii")
    # ArtworkDB's MHOD string body differs from iTunesDB's string body.
    name = chunk("mhod", 24, struct.pack("<IB3xI", len(payload), encoding, 0)
                 + payload, {12: 3})
    head = bytearray(chunk("mhni", 76, name,
                          {12: 1, 16: fmt, 20: offset, 24: canvas*canvas*2}))
    # Apple stores dimensions inclusive of the leading padding, not extents.
    struct.pack_into("<4h", head, 28, padding, padding,
                     canvas-padding, canvas-padding)
    return chunk("mhod", 24, bytes(head), {12: 2})


def artwork(thumbnails=None, dbid=0x123456789ABCDEF0, id=77):
    thumbnails = [thumb()] if thumbnails is None else thumbnails
    image = bytearray(chunk("mhii", 152, b"".join(thumbnails),
                            {12: len(thumbnails), 16: id}))
    struct.pack_into("<Q", image, 20, dbid)
    listing = bytearray(chunk("mhli", 92))
    struct.pack_into("<I", listing, 8, 1)
    return chunk("mhfd", 132, chunk("mhsd", 96, bytes(listing) + image, {12: 1}),
                 {20: 1})


class ITunesArtworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.exe = Path(cls.build.name) / "artwork"
        subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                        "-pthread", "-I", str(APPS), str(ROOT / "tests/artwork_harness.c"),
                        str(APPS / "podthings_itunesdb.c"), "-o", str(cls.exe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def fixture(self, music_data=None, art_data=None, formats=(1055,), offset=0):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / ".podthingsloader").mkdir()
        (root / "iPod_Control/iTunes").mkdir(parents=True)
        (root / "iPod_Control/Artwork").mkdir(parents=True)
        (root / "iPod_Control/iTunes/iTunesDB").write_bytes(music() if music_data is None else music_data)
        (root / "iPod_Control/Artwork/ArtworkDB").write_bytes(artwork() if art_data is None else art_data)
        for fmt in formats:
            size = FORMATS[fmt]
            # Top half red, bottom half blue. BMP output must be bottom-up BGR.
            pixels = b"\x00\xf8" * (size*size//2) + b"\x1f\x00" * (size*size//2)
            (root / f"iPod_Control/Artwork/F{fmt}_1.ithmb").write_bytes(b"\0"*offset+pixels)
        return root

    def run_reader(self, root, expected=True, track=TRACK, concurrent=False, usb=False):
        files = {p: hashlib.sha256(p.read_bytes()).digest()
                 for p in (root / "iPod_Control").rglob("*") if p.is_file()}
        command=[str(self.exe), str(root), track, str(int(expected))]
        if concurrent:
            command.append("threads")
        elif usb:
            command.append("usb")
        result = subprocess.run(command,
                                capture_output=True, text=True, timeout=15,
                                env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0"})
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        for p, digest in files.items():
            self.assertEqual(hashlib.sha256(p.read_bytes()).digest(), digest, str(p))
        if expected:
            names = result.stdout.strip().splitlines()
            self.assertEqual(len(names), 2)
            self.assertEqual(names[0], names[1])
            return root / names[0].lstrip("/")

    def test_artwork_scratch_is_safe_for_concurrent_callers(self):
        root=self.fixture(art_data=artwork([thumb(1060)]),formats=(1060,))
        path=self.run_reader(root,concurrent=True)
        bmp=path.read_bytes()
        self.assertEqual(struct.unpack_from("<ii",bmp,18),(320,320))
        self.assertEqual(bmp[54:57],b"\xff\0\0")
        stride=320*3
        self.assertEqual(bmp[54+stride*319:57+stride*319],b"\0\0\xff")

    def test_all_video_and_classic_rgb565_formats_and_pixels(self):
        for fmt, size in FORMATS.items():
            with self.subTest(fmt=fmt):
                root = self.fixture(art_data=artwork([thumb(fmt)]), formats=(fmt,))
                path = self.run_reader(root)
                bmp = path.read_bytes()
                self.assertEqual(bmp[:2], b"BM")
                self.assertEqual(struct.unpack_from("<ii", bmp, 18), (size, size))
                self.assertEqual(bmp[54:57], b"\xff\0\0")
                stride = (size*3+3)&~3
                self.assertEqual(bmp[54+stride*(size-1):57+stride*(size-1)], b"\0\0\xff")

    def test_modern_shared_image_link_overrides_old_track_dbid(self):
        root = self.fixture(music_data=music(link=77, dbid=9),
                            art_data=artwork(dbid=123))
        self.run_reader(root)

    def test_unusable_shared_link_falls_back_to_dbid_artwork(self):
        # A stale shared image can still exist but have no supported/available
        # thumbnails. It must not mask the usable legacy DBID match.
        linked = artwork([thumb(9999)], dbid=123, id=77)[320:]
        fallback = artwork([thumb()], id=78)[320:]
        listing = bytearray(chunk("mhli", 92))
        struct.pack_into("<I", listing, 8, 2)
        data = chunk("mhfd", 132,
                     chunk("mhsd", 96, bytes(listing)+linked+fallback, {12:1}),
                     {20:1})
        self.run_reader(self.fixture(music_data=music(link=77),art_data=data))

    def test_usb_disconnect_forces_fresh_full_source_fingerprints(self):
        self.run_reader(self.fixture(),usb=True)

    def test_largest_available_thumbnail_and_missing_larger_fallback(self):
        for files, expected in (((1055,1060),320),((1055,),128)):
            root = self.fixture(art_data=artwork([thumb(1055),thumb(1060)]), formats=files)
            bmp = self.run_reader(root).read_bytes()
            self.assertEqual(struct.unpack_from("<i",bmp,18)[0],expected)

    def test_offset_padding_utf8_path_and_case_insensitive_track(self):
        root = self.fixture(art_data=artwork([thumb(offset=16,padding=3,encoding=1)]),offset=16)
        bmp = self.run_reader(root, track=TRACK.lower()).read_bytes()
        self.assertEqual(struct.unpack_from("<ii",bmp,18),(122,122))

    def test_rectangular_itunes_bounds_and_pixels(self):
        for fmt, canvas in FORMATS.items():
            with self.subTest(fmt=fmt):
                thumbnail = bytearray(thumb(fmt))
                # 8px top padding, 4px left; right/bottom are canvas bounds.
                struct.pack_into("<4h", thumbnail, 24+28,
                                 8, 4, canvas, canvas)
                root = self.fixture(art_data=artwork([bytes(thumbnail)]),
                                    formats=(fmt,))
                bmp = self.run_reader(root).read_bytes()
                width, height = canvas-4, canvas-8
                self.assertEqual(struct.unpack_from("<ii", bmp, 18),
                                 (width, height))
                self.assertEqual(bmp[54:57], b"\xff\0\0")
                stride = (width*3+3)&~3
                self.assertEqual(bmp[54+stride*(height-1):57+stride*(height-1)],
                                 b"\0\0\xff")

    def test_out_of_canvas_or_empty_thumbnail_is_rejected(self):
        for y, x, bottom, right in ((0, 1, 128, 129), (0, 4, 128, 4),
                                    (-1, 0, 128, 128), (128, 0, 128, 128)):
            thumbnail = bytearray(thumb())
            struct.pack_into("<4h", thumbnail, 24+28, y, x, bottom, right)
            self.run_reader(self.fixture(art_data=artwork([bytes(thumbnail)])),
                            False)

    def test_bad_image_header_length_does_not_hide_other_albums(self):
        good = artwork()[320:]
        for head in (0, 8, 4096):
            with self.subTest(head=head):
                bad = bytearray(chunk("mhii", 28))
                struct.pack_into("<I", bad, 4, head)
                listing = bytearray(chunk("mhli", 92))
                struct.pack_into("<I", listing, 8, 2)
                data = chunk("mhfd", 132, chunk("mhsd", 96,
                             bytes(listing)+bad+good, {12: 1}), {20: 1})
                self.run_reader(self.fixture(art_data=data))

    def test_missing_unknown_corrupt_and_traversal_fail_without_source_writes(self):
        cases = (
            (b"", (1055,)), (artwork([thumb(9999)]),(1055,)),
            (artwork([thumb(filename=":../F1055_1.ithmb")]),(1055,)),
            (artwork([thumb(filename=":"+"A"*200)]),(1055,)),
            (artwork([thumb(filename=":"+"A"*200,encoding=1)]),(1055,)),
            (artwork(),()), (artwork([thumb(offset=999999)]),(1055,)),
            (artwork(dbid=1),(1055,)),
        )
        for data, formats in cases:
            with self.subTest(data=data[:12],formats=formats):
                self.run_reader(self.fixture(art_data=data,formats=formats),False)

    def test_non_itunes_library_never_requires_apple_database(self):
        root = self.fixture()
        (root / "iPod_Control/iTunes/iTunesDB").unlink()
        self.run_reader(root,False,track="/Music/Ordinary.mp3")

    def test_raw_artwork_changed_same_size_does_not_reuse_old_bitmap(self):
        root = self.fixture()
        first = self.run_reader(root)
        raw = root / "iPod_Control/Artwork/F1055_1.ithmb"
        raw.write_bytes(b"\xe0\x07"*(128*128))
        second = self.run_reader(root)
        self.assertNotEqual(first,second)
        self.assertEqual(second.read_bytes()[54:57],b"\0\xff\0")

    def test_corrupt_local_index_and_partial_bitmap_are_recoverable(self):
        root = self.fixture()
        path = self.run_reader(root)
        (root / ".podthingsloader/itunes-art/index").write_bytes(b"partial")
        path.write_bytes(b"BM")
        self.run_reader(root)

    def test_duplicate_broken_image_does_not_hide_usable_same_id(self):
        good = artwork()[320:]
        bad = artwork([thumb(9999)])[320:]
        listing = bytearray(chunk("mhli", 92))
        struct.pack_into("<I", listing, 8, 2)
        data = chunk("mhfd", 132,
                     chunk("mhsd", 96, bytes(listing)+good+bad, {12:1}),
                     {20:1})
        root = self.fixture(music_data=music(link=77), art_data=data)
        self.run_reader(root)

    def test_short_bounded_image_does_not_hide_other_albums(self):
        good = artwork()[320:]
        bad = chunk("mhii", 12)
        listing = bytearray(chunk("mhli", 92))
        struct.pack_into("<I", listing, 8, 2)
        data = chunk("mhfd", 132,
                     chunk("mhsd", 96, bytes(listing)+good+bad, {12:1}),
                     {20:1})
        root = self.fixture(art_data=data)
        self.run_reader(root)

    def test_truncated_source_records_are_bounded(self):
        original = artwork()
        for length in (0,11,23,131,244,len(original)-1):
            self.run_reader(self.fixture(art_data=original[:length]),False)

    def test_now_playing_metadata_ready_predicate_and_all_theme_guards(self):
        source = (APPS / "gui/skin_engine/skin_tokens.c").read_text()
        actual = function(source,"static bool podthings_metadata_ready(")
        shim = """
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#define AFMT_UNKNOWN 0
struct mp3entry {long length,filesize;int codectype;};
"""
        main = """
int main(void) {
 struct mp3entry p={0,0,0}, real={100,200,3}, untagged={0,200,3};
 assert(!podthings_metadata_ready(NULL));
 assert(!podthings_metadata_ready(&p));
 p.filesize=200;assert(!podthings_metadata_ready(&p));
 assert(podthings_metadata_ready(&real));
 assert(podthings_metadata_ready(&untagged));
 return 0;
}
"""
        path = Path(self.build.name) / "ready.c"
        exe = Path(self.build.name) / "ready"
        path.write_text(shim+actual+main)
        subprocess.run(["cc",str(path),"-o",str(exe)],check=True)
        subprocess.run([str(exe)],check=True)
        for variant in ("current","blue","purple"):
            wps = (ROOT / f"rockbox-firmware/wps/podthingsos-{variant}.320x240x16.wps").read_text()
            self.assertIn("%?pQ<%s%?it<%it|%fn>|Loading...>",wps)
            self.assertIn("%?pQ<%s%?ia<%ia|Unknown artist>|>",wps)
            self.assertIn("%?pQ<%s%?id<%id|Unknown album>|>",wps)

    def test_cover_flow_album_wide_priority_and_embedded_fallback(self):
        source = (APPS / "plugins/pictureflow/pictureflow.c").read_text()
        actual = function(source,"static bool get_albumart_for_index_from_db(")
        shim = r"""
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#define PODTHINGS_OS 1
#define TAGCACHE_BUFSZ 260
#define MAX_PATH 260
#define AA_TYPE_JPG 3
#define AA_CLEAR_FLAGS_MASK 255
enum {tag_filename,tag_album,tag_albumartist};
struct mp3_albumart {int type,size;long pos;};
struct mp3entry {bool has_embedded_albumart;struct mp3_albumart albumart;};
static struct mp3entry id3;
static struct {bool valid;char *result;int pos;} tcs;
static struct {struct {int seek,artist_seek;} album_index[1];} pf_idx;
static struct mp3_albumart pf_embedded;
static bool pf_has_embedded;
static int mode,finished,cur;
static bool search(void *s,int tag){(void)s;assert(tag==tag_filename);tcs.pos=0;return true;}
static void filter(void *s,int tag,long n){(void)s;(void)tag;(void)n;}
static bool next(void *s,char *buf,long n){
 (void)s;(void)buf;(void)n;
 if(tcs.pos==2)return false;
 cur=tcs.pos++;tcs.result=cur?"track2":"track1";return true;
}
static void finish(void *s){(void)s;++finished;}
static bool metadata(struct mp3entry *m,int fd,const char *path){
 (void)fd;(void)path;
 memset(m,0,sizeof(*m));
 if(mode==4 && cur==0)return false;
 m->has_embedded_albumart=(mode==0 && cur==0) ||
    (mode==1 && cur==1) || mode==2 || (mode==4 && cur==1);
 m->albumart=(struct mp3_albumart){AA_TYPE_JPG,1234,cur+20};return true;
}
static bool search_albumart_files(const struct mp3entry *m,const char *sz,char *buf,int n){
 (void)m;(void)sz;
 if(mode==0 && cur==1){snprintf(buf,n,"/itunes.bmp");return true;}
 return false;
}
static size_t copy(char *out,const char *s,size_t n){snprintf(out,n,"%s",s);return strlen(s);}
static void pause_thread(void){}
static struct {
 bool (*tagcache_search)(void *,int);
 void (*tagcache_search_add_filter)(void*,int,long);
 bool (*tagcache_get_next)(void*,char*,long);
 void (*tagcache_search_finish)(void*);
 bool (*get_metadata)(struct mp3entry*,int,const char*);
 size_t (*strlcpy)(char*,const char*,size_t);
 void (*yield)(void);
} api={search,filter,next,finish,metadata,copy,pause_thread},*rb=&api;
"""
        main = r"""
int main(void){
 for(mode=0;mode<5;mode++){
  char out[260]={0};finished=0;
  bool found=get_albumart_for_index_from_db(0,out,sizeof(out));
  assert(found==(mode!=3));assert(finished==1);
  if(mode==0)assert(!strcmp(out,"/itunes.bmp") && !pf_has_embedded);
  if(mode==1 || mode==4)assert(!strcmp(out,"track2") && pf_has_embedded && pf_embedded.pos==21);
  if(mode==2)assert(!strcmp(out,"track1") && pf_has_embedded && pf_embedded.pos==20);
 }
 tcs.valid=true;finished=0;
 char out[260];assert(!get_albumart_for_index_from_db(0,out,sizeof(out)) && !finished);
 return 0;
}
"""
        path = Path(self.build.name) / "priority.c"
        exe = Path(self.build.name) / "priority"
        path.write_text(shim+actual+main)
        subprocess.run(["cc","-std=c99","-Wall","-Wextra","-Werror",
                        "-fsanitize=undefined","-fno-sanitize-recover=all",
                        str(path),"-o",str(exe)],check=True)
        subprocess.run([str(exe)],check=True)


if __name__ == "__main__":
    unittest.main()
