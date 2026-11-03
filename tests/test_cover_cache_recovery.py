"""Execute production slide writes under short I/O; old covers must survive."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_ipod_battery import function

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / "rockbox-firmware/apps/plugins/pictureflow/pictureflow.c"


class CoverCacheRecovery(unittest.TestCase):
    def test_atomic_slide_write_preserves_old_cover_on_all_failures(self):
        body = "static bool " + function(FLOW.read_text(), "save_pfraw")
        source = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#define MAX_PATH 260
typedef unsigned short pix_t;
struct pfraw_header {int width,height;};
struct bitmap {int width,height;unsigned char *data;};
static int fail, writes;
static int wrapped_open(const char *p,int f,int m) {return open(p,f,m);}
static ssize_t wrapped_write(int fd,const void *p,size_t n) {
 ++writes;
 return write(fd,p,((fail==1 && writes==1)||(fail==2 && writes==2))?n-1:n);
}
static int wrapped_close(int fd) {int r=close(fd);return fail==3?-1:r;}
static int wrapped_rename(const char *a,const char *b) {return fail==4?-1:rename(a,b);}
static const struct {
 int (*snprintf)(char *,size_t,const char *,...);
 int (*open)(const char *,int,int);
 ssize_t (*write)(int,const void *,size_t);
 int (*close)(int);int (*rename)(const char *,const char *);int (*remove)(const char *);
} api={snprintf,wrapped_open,wrapped_write,wrapped_close,wrapped_rename,remove}, *rb=&api;
''' + body + r'''
int main(void) {
 unsigned char pixels[8]={1,2,3,4,5,6,7,8};
 struct bitmap bm={2,2,pixels};
 for(fail=1;fail<=4;fail++) {
  FILE *f=fopen("cover.pfraw","wb");assert(f);
  assert(fwrite("OLD COVER",1,9,f)==9);assert(!fclose(f));
  writes=0;assert(!save_pfraw("cover.pfraw",&bm));
  char old[10]={0};f=fopen("cover.pfraw","rb");assert(f);
  assert(fread(old,1,9,f)==9);fclose(f);assert(!strcmp(old,"OLD COVER"));
  assert(access("cover.pfraw.tmp",F_OK)!=0);
 }
 fail=0;writes=0;assert(save_pfraw("cover.pfraw",&bm));
 FILE *f=fopen("cover.pfraw","rb");struct pfraw_header h;
 assert(fread(&h,1,sizeof(h),f)==sizeof(h) && h.width==2 && h.height==2);
 unsigned char out[8];assert(fread(out,1,8,f)==8 && !memcmp(out,pixels,8));
 fclose(f);assert(access("cover.pfraw.tmp",F_OK)!=0);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "test.c").write_text(source)
            subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra",
                            "-Wno-sign-compare", "-Werror", "-fsanitize=undefined",
                            str(path / "test.c"), "-o", str(path / "test")],
                           check=True)
            subprocess.run([str(path / "test")], cwd=path, check=True)

    def test_interruption_does_not_complete_cache_and_warning_is_not_modal(self):
        source = FLOW.read_text()
        create = function(source, "create_albumart_cache")
        self.assertIn("== BUTTON_MENU", create)
        self.assertNotIn("> BUTTON_NONE", create)
        self.assertNotIn("Album art is bad:", source)
        self.assertIn("pf_cfg.cache_version != CACHE_VERSION &&\n"
                      "        aa_cache.inspected >= pf_idx.album_ct", source)
        increment = function(source, "incremental_albumart_cache")
        self.assertNotIn("rb->remove(aa_cache.pfraw_file)", increment)
        self.assertIn("config_save(CACHE_VERSION", increment)


if __name__ == "__main__":
    unittest.main()
