/* SPDX-License-Identifier: GPL-2.0-or-later
 * Runs the production protocol with POSIX files and injectable I/O faults.
 * This is not an emulation of either iPod or its Apple boot chain.
 */
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include "config.h"
#include "podthings_boot.h"

static const char path[] = TEST_ROOT "/boot-official-once";
enum fault { NONE, OPEN, READ, WRITE, SYNC, CLOSE, REMOVE, FLUSH, SLEEP };
static enum fault fault;
static int flushes;
static int sleeps;
#ifdef HAVE_STORAGE_FLUSH
#define EXPECTED_FLUSHES 1
#else
#define EXPECTED_FLUSHES 0
#endif

int test_open(const char *name, int flags, ...)
{
    if (fault == OPEN) { errno = EIO; return -1; }
    return open(name, flags, 0600);
}
ssize_t test_read(int fd, void *data, size_t size)
{
    if (fault == READ) { errno = EIO; return -1; }
    return read(fd, data, size);
}
ssize_t test_write(int fd, const void *data, size_t size)
{
    return write(fd, data, fault == WRITE ? size - 1 : size);
}
int test_fsync(int fd)
{
    if (fault == SYNC) { errno = EIO; return -1; }
    return fsync(fd);
}
int test_close(int fd)
{
    int rc = close(fd);
    if (fault == CLOSE) { errno = EIO; return -1; }
    return rc;
}
int test_remove(const char *name)
{
    if (fault == REMOVE) { errno = EIO; return -1; }
    return remove(name);
}
int storage_flush(void)
{
    flushes++;
    return fault == FLUSH ? -1 : 0;
}
void storage_sleepnow(void) { sleeps++; }
bool storage_disk_is_active(void) { return fault == SLEEP; }
static bool exists(void) { return access(path, F_OK) == 0; }

int main(int argc, char **argv)
{
    assert(argc == 2);
    const char *mode = argv[1];
    assert(podthings_consume_official_boot() == 0);
    assert(flushes == 0);

    if (!strcmp(mode, "missing")) return 0;
    if (!strcmp(mode, "malformed") || !strcmp(mode, "empty"))
    {
        int fd = open(path, O_WRONLY | O_CREAT, 0600);
        assert(fd >= 0);
        if (!strcmp(mode, "malformed")) assert(write(fd, "bad", 3) == 3);
        assert(close(fd) == 0);
        assert(podthings_consume_official_boot() == -1);
        assert(!exists());
        assert(podthings_consume_official_boot() == 0);
        return 0;
    }

    if (!strcmp(mode, "open-fail")) fault = OPEN;
    if (!strcmp(mode, "short-write")) fault = WRITE;
    if (!strcmp(mode, "sync-fail")) fault = SYNC;
    if (!strcmp(mode, "close-fail")) fault = CLOSE;
    if (!strcmp(mode, "flush-create-fail")) fault = FLUSH;
    if (fault != NONE)
    {
        assert(!podthings_request_official_boot());
        assert(!exists());
        fault = NONE;
        assert(podthings_consume_official_boot() == 0);
        return 0;
    }

    assert(podthings_request_official_boot());
    assert(exists());
    assert(flushes == EXPECTED_FLUSHES);
    if (!strcmp(mode, "cancel"))
    {
        assert(podthings_cancel_official_boot());
        assert(!exists());
        assert(sleeps == 1); /* Cancellation also persists the deletion. */
        assert(podthings_consume_official_boot() == 0);
        return 0;
    }
    if (!strcmp(mode, "trailing-data"))
    {
        int fd = open(path, O_WRONLY | O_APPEND);
        assert(fd >= 0 && write(fd, "x", 1) == 1);
        assert(close(fd) == 0);
        assert(podthings_consume_official_boot() == -1);
        assert(!exists());
        assert(podthings_consume_official_boot() == 0);
        return 0;
    }
    if (!strcmp(mode, "read-fail")) fault = READ;
    if (!strcmp(mode, "remove-fail")) fault = REMOVE;
    if (!strcmp(mode, "flush-consume-fail")) fault = FLUSH;
    if (!strcmp(mode, "sleep-fail")) fault = SLEEP;
    if (fault != NONE)
    {
        assert(podthings_consume_official_boot() == -1);
        if (fault == REMOVE)
        {
            assert(exists());
            assert(podthings_consume_official_boot() == -1);
            fault = NONE;
            assert(podthings_consume_official_boot() == 1);
        }
        fault = NONE;
        assert(!exists());
        assert(podthings_consume_official_boot() == 0);
        return 0;
    }

    assert(!strcmp(mode, "one-shot"));
    assert(podthings_consume_official_boot() == 1);
    assert(!exists());
    assert(flushes == EXPECTED_FLUSHES * 2);
    assert(sleeps == 1);
    for (int reboot = 0; reboot < 5; reboot++)
        assert(podthings_consume_official_boot() == 0);
    assert(podthings_request_official_boot()); /* A new explicit action. */
    assert(podthings_consume_official_boot() == 1);
    assert(podthings_consume_official_boot() == 0);
    return 0;
}
