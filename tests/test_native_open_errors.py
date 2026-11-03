"""Run native open/cleanup code: POSIX open stubs miss this failure."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_ipod_battery import function

ROOT = Path(__file__).resolve().parents[1]


class NativeOpenErrors(unittest.TestCase):
    def test_missing_request_errno_survives_native_descriptor_cleanup(self):
        source = (ROOT / "rockbox-firmware/firmware/common/file.c").read_text()
        internal = (ROOT / "rockbox-firmware/firmware/include/file_internal.h").read_text()
        macros = internal[internal.index("#define ERRNO "):internal.index("/** Misc. stuff **/")]
        code = r"""
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include "podthings_boot.h"
#define DEBUGF(...) ((void)0)
#define MAX_OPEN_FILES 2
#define MAX_DIRECTORY_SIZE 65536
#define FDO_BUSY 1
#define FDO_MASK 3
#define FD_WRITE 4
#define FD_WRONLY 8
#define FD_APPEND 16
#define FO_TRUNC 32
#define FF_PARENTINFO 64
#define FF_ANYTYPE 128
#define ATTR_DIRECTORY 16
#define ATTR_NEW_FILE 32
#define FO_SINGLE 1
#define O_TRUNC_THRESH 1024
#define ERRNO 0
#define RC 0
struct filestr_base { unsigned flags; int fatstr; };
struct filestr_desc {
    struct filestr_base stream;
    size_t offset, *sizep;
};
struct path_component_info {
    unsigned attr;
    size_t filesize;
    int parentinfo;
    const char *name;
    size_t length;
};
static struct filestr_desc open_streams[MAX_OPEN_FILES];
static size_t size;
static int scenario, cleanup_count, bad_closes;
static int alloc_filestr(struct filestr_desc **out)
{
    if (scenario == 4) { errno=EMFILE; return -1; }
    *out=&open_streams[0];
    (*out)->stream.flags=FDO_BUSY;
    return 0;
}
static int open_stream_internal(const char *p, unsigned f, struct filestr_base *s,
                                struct path_component_info *c)
{
    (void)p; (void)f; (void)s;
    *c=(struct path_component_info){.attr=scenario==2 ? ATTR_DIRECTORY : 0};
    if (scenario==3) { errno=EIO; return -1; }
    return scenario==0 ? 0 : 1;
}
static int close_stream_internal(struct filestr_base *s)
{ ++cleanup_count; s->flags=0; return 0; }
static int close_internal(struct filestr_desc *f)
{ return close_stream_internal(&f->stream); }
static void file_internal_lock_WRITER(void) {}
static void file_internal_unlock_WRITER(void) {}
static int create_stream_internal(int *p, const char *n, size_t l, unsigned a,
                                 unsigned c, struct filestr_base *s)
{ (void)p;(void)n;(void)l;(void)a;(void)c;(void)s;return 0; }
static void fat_rewind(int *p) { (void)p; }
static size_t *fileobj_get_sizep(struct filestr_base *s) { (void)s; return &size; }
static unsigned fileobj_get_flags(struct filestr_base *s) { (void)s; return FO_SINGLE; }
static int ftruncate_internal(struct filestr_desc *s, int n, bool b)
{ (void)s;(void)n;(void)b;return 0; }
static int rbfs_close(int fildes);
"""
        code += macros
        close = function(source, "int rbfs_close(int fildes)")
        # Observe the real bad-close branch without changing its behavior.
        close = close.replace('FILE_ERROR(EBADF, -2);',
                              '++bad_closes; FILE_ERROR(EBADF, -2);')
        code += close.replace("int rbfs_close(", "static int rbfs_close(")
        code += function(source, "static int open_internal_inner2(")
        code += function(source, "static int open_internal_inner1(")
        protocol = (ROOT / "rockbox-firmware/firmware/common/podthings_boot.c").read_text()
        code += """
#define open(path, flags) open_internal_inner1(path, flags, 0)
#define close rbfs_close
static bool cancel_request(const char *path) { (void)path; return true; }
"""
        code += function(protocol, "static int consume_request(")
        code += function(protocol, "int podthings_boot_select(")
        code += function(protocol, "int podthings_boot_resolve_disk(")
        code += function(protocol, "int podthings_boot_resolve(")
        code += r"""
int main(void)
{
    scenario=0; errno=0;
    assert(open_internal_inner1("/.podthingsloader/boot-official-once",O_RDONLY,0)<0);
    /* Before the fix, the duplicate descriptor close overwrites ENOENT with
       EBADF. The boot policy then vetoes defaults, Hold AND one-time boots. */
    assert(cleanup_count>=1);
    assert(errno==ENOENT);
    assert(open_internal_inner1("/.podthingsloader/boot-rockbox-once",O_RDONLY,0)<0);
    assert(errno==ENOENT);
    int apple_once=consume_request("boot-official-once","apple",5);
    int rockbox_once=consume_request("boot-rockbox-once","rockbox",7);
    int disk_once=consume_request("boot-disk-once","Disk\n",5);
    assert(apple_once==0 && rockbox_once==0 && disk_once==0);
    /* Absent requests must not override any preference or Hold selection. */
    for (int target=0; target<3; target++)
    {
        assert(podthings_boot_resolve(target,false,apple_once,rockbox_once)==target);
        assert(podthings_boot_resolve(target,true,apple_once,rockbox_once)==
               (target==PODTHINGS_BOOT_OS ? PODTHINGS_BOOT_APPLE : PODTHINGS_BOOT_OS));
        assert(podthings_boot_resolve_disk(target,false,apple_once,rockbox_once,
                                           disk_once)==target);
        assert(podthings_boot_resolve_disk(target,true,apple_once,rockbox_once,
                                           disk_once)==
               (target==PODTHINGS_BOOT_OS ? PODTHINGS_BOOT_APPLE : PODTHINGS_BOOT_OS));
    }
    /* A valid one-time request plus the other absent request must also work. */
    assert(podthings_boot_resolve(0,false,1,rockbox_once)==PODTHINGS_BOOT_APPLE);
    assert(podthings_boot_resolve(0,false,apple_once,1)==PODTHINGS_BOOT_ROCKBOX);
    scenario=1;
    assert(open_internal_inner1("present",O_RDONLY,0)==0);
    assert(!rbfs_close(0));
    scenario=2;
    assert(open_internal_inner1("directory",O_RDONLY,0)<0);
    assert(errno==EISDIR);
    scenario=3;
    assert(open_internal_inner1("io-error",O_RDONLY,0)<0);
    assert(errno==EIO);
    scenario=4;
    assert(open_internal_inner1("no-descriptors",O_RDONLY,0)<0);
    assert(errno==EMFILE);
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "native.c").write_text(code)
            subprocess.run(["cc", "-std=gnu99", "-Wall", "-Wextra", "-Werror",
                            f"-I{ROOT / 'rockbox-firmware/firmware/export'}",
                            "-fsanitize=undefined", str(path / "native.c"),
                            "-o", str(path / "native")], check=True)
            subprocess.run([str(path / "native")], check=True, timeout=5)
