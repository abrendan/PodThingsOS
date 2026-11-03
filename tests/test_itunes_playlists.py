"""Exercise the actual portable firmware reader against synthetic iPod DBs."""
import ctypes as C
import hashlib
from pathlib import Path
import random
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "rockbox-firmware/apps"


def put(data, at, value):
    struct.pack_into("<I", data, at, value)


def chunk(tag, header, payload=b"", fields=None):
    data = bytearray(header)
    data[:4] = tag.encode()
    put(data, 4, header)
    put(data, 8, header + len(payload))
    for at, value in (fields or {}).items():
        put(data, at, value)
    return bytes(data) + payload


def text(kind, value, utf8=False):
    value = value.encode("utf-8" if utf8 else "utf-16le")
    return chunk("mhod", 24, struct.pack("<4I", 2 if utf8 else 1,
                                      len(value), 0, 0) + value, {12: kind})


def track(id, title, path, artist="Artist", utf8=False):
    payload = text(1, title, utf8) + text(4, artist, utf8) + text(2, path, utf8)
    return chunk("mhit", 156, payload, {12: 3, 16: id})


def member(id, position=None, legacy=False):
    payload = b"" if position is None else chunk(
        "mhod", 24, struct.pack("<5I", position, 0, 0, 0, 0), {12: 100})
    data = bytearray(chunk("mhip", 76, payload,
                          {12: int(position is not None), 24: id}))
    if legacy:
        put(data, 8, 76)
    return bytes(data)


def playlist(name, members=(), master=False, smart=False, utf8=False):
    meta = text(1, name, utf8)
    if smart:
        meta += chunk("mhod", 24, b"\0" * 72, {12: 50})
    return chunk("mhyp", 108, meta + b"".join(members),
                 {12: 2 if smart else 1, 16: len(members), 20: int(master)})


def section(type, records):
    tag = "mhlt" if type == 1 else "mhlp"
    list_header = bytearray(chunk(tag, 92))
    put(list_header, 8, len(records))
    return chunk("mhsd", 96, bytes(list_header) + b"".join(records), {12: type})


def database(tracks=None, playlists=None, extra=b""):
    if tracks is None:
        tracks = [
            track(42, "한국어 日本語 中文", ":iPod_Control:Music:F01:ABC.m4a",
                  "Björk", True),
            track(7, "Second Song", ":iPod_Control:Music:F00:DEF.mp3"),
        ]
    if playlists is None:
        playlists = [
            playlist("iPod Library", [member(42), member(7)], master=True),
            playlist("我的 음악 🎵", [member(7, 1), member(42, 0)]),
            playlist("Empty"),
            playlist("Smart Mix", [member(42)], smart=True),
        ]
    payload = section(1, tracks) + section(2, playlists) + extra
    return chunk("mhbd", 244, payload, {16: 0x30, 20: 3 if extra else 2})


class Track(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in ("id", "title", "artist", "path")]


class Playlist(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in ("title", "members", "end", "count")]


class Member(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in ("id", "position", "ordinal")]


READ = C.CFUNCTYPE(C.c_bool, C.c_void_p, C.c_uint32, C.c_void_p, C.c_size_t)


class Database(C.Structure):
    _fields_ = [
        ("read_at", READ), ("context", C.c_void_p),
        *[(n, C.c_uint32) for n in ("size", "tracks_at", "tracks_end",
                                   "playlists_at", "playlists_end",
                                   "track_count", "playlist_capacity", "playlist_count")],
        ("tracks", C.POINTER(Track)), ("playlists", C.POINTER(Playlist)),
        ("cache_at", C.c_uint32), ("cache_len", C.c_uint32),
        ("cache", C.c_ubyte * 512),
    ]


class Reader:
    def __init__(self, lib, data, fail_at=None):
        self.data = data
        self.before = hashlib.sha256(data).digest()
        self.lib, self.db = lib, Database()
        self.reads = 0

        @READ
        def read(_, offset, out, size):
            self.reads += 1
            if fail_at is not None and offset + size > fail_at:
                return False
            if offset + size > len(data):
                raise AssertionError("Firmware attempted an out-of-bounds read")
            C.memmove(out, data[offset:offset + size], size)
            return True

        self.callback = read
        self.opened = lib.itdb_open(C.byref(self.db), read, None, len(data))
        self.indexed = False
        if self.opened:
            self.tracks = (Track * max(1, self.db.track_count))()
            self.playlists = (Playlist * max(1, self.db.playlist_capacity))()
            self.indexed = lib.itdb_index(C.byref(self.db), self.tracks, self.playlists)

    def text(self, at, size=256, truncate=True):
        buf = C.create_string_buffer(size)
        ok = self.lib.itdb_text(C.byref(self.db), at, buf, size, truncate)
        return ok, buf.value.decode("utf-8")

    def members(self, index):
        pl = self.playlists[index]
        items = (Member * max(1, pl.count))()
        ok = self.lib.itdb_members(C.byref(self.db), C.byref(pl), items)
        return ok, items[:pl.count]

    def path(self, id, size=260):
        track = self.lib.itdb_find(C.byref(self.db), id)
        buf = C.create_string_buffer(size)
        ok = self.lib.itdb_path(C.byref(self.db), track, buf, size)
        return ok, buf.value.decode("utf-8", errors="replace")


class ITunesReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        lib = Path(cls.temp.name) / "reader.so"
        subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                        "-shared", "-fPIC",
                        str(APPS / "podthings_itunesdb.c"), "-o", str(lib)],
                       check=True)
        cls.lib = C.CDLL(str(lib))
        cls.lib.itdb_open.argtypes = [C.POINTER(Database), READ, C.c_void_p, C.c_uint32]
        cls.lib.itdb_open.restype = C.c_bool
        cls.lib.itdb_index.argtypes = [C.POINTER(Database), C.POINTER(Track),
                                      C.POINTER(Playlist)]
        cls.lib.itdb_index.restype = C.c_bool
        cls.lib.itdb_members.argtypes = [C.POINTER(Database), C.POINTER(Playlist),
                                        C.POINTER(Member)]
        cls.lib.itdb_members.restype = C.c_bool
        cls.lib.itdb_text.argtypes = [C.POINTER(Database), C.c_uint32, C.c_void_p,
                                     C.c_size_t, C.c_bool]
        cls.lib.itdb_text.restype = C.c_bool
        cls.lib.itdb_find.argtypes = [C.POINTER(Database), C.c_uint32]
        cls.lib.itdb_find.restype = C.POINTER(Track)
        cls.lib.itdb_path.argtypes = [C.POINTER(Database), C.POINTER(Track),
                                     C.c_void_p, C.c_size_t]
        cls.lib.itdb_path.restype = C.c_bool

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_unicode_titles_order_and_read_only(self):
        r = Reader(self.lib, database())
        self.assertTrue(r.indexed)
        self.assertEqual(r.db.playlist_count, 3)  # no master copy
        self.assertEqual(r.text(r.playlists[0].title), (True, "我的 음악 🎵"))
        ok, members = r.members(0)
        self.assertTrue(ok)
        self.assertEqual([m.id for m in members], [42, 7])
        self.assertEqual(r.text(r.tracks[1].title), (True, "한국어 日本語 中文"))
        self.assertEqual(r.path(42), (True, "/iPod_Control/Music/F01/ABC.m4a"))
        self.assertEqual(r.members(1), (True, []))
        self.assertEqual(r.members(2)[1][0].id, 42)  # synced smart snapshot
        self.assertEqual(hashlib.sha256(r.data).digest(), r.before)
        self.assertLess(r.reads, 80)  # bounded sector cache, not per-byte disk I/O

    def test_dataset_three_preferred_without_duplicate_playlists(self):
        r = Reader(self.lib, database(extra=section(3, [
            playlist("Newer list", [member(7)])])))
        self.assertTrue(r.indexed)
        self.assertEqual(r.db.playlist_count, 1)
        self.assertEqual(r.text(r.playlists[0].title)[1], "Newer list")

    def test_legacy_mhip_duplicate_members_and_missing_track(self):
        r = Reader(self.lib, database(playlists=[playlist("Old", [
            member(7, 2, True), member(42, 0, True),
            member(42, 1, True), member(999, 3, True)])]))
        ok, entries = r.members(0)
        self.assertTrue(ok)
        self.assertEqual([m.id for m in entries], [42, 42, 7, 999])
        self.assertFalse(r.path(999)[0])

    def test_reject_traversal_urls_injection_and_truncated_paths(self):
        for path in (":iPod_Control:Music:..:secret.mp3",
                     "/iPod_Control/Music//a.mp3", "/iPod_Control/./a.mp3",
                     "/iPod_Control/Music\\x.mp3", "https://example.com/a.mp3",
                     ":iPod_Control:Music:bad\ntrack.mp3"):
            r = Reader(self.lib, database(tracks=[track(1, "x", path)],
                                         playlists=[playlist("x", [member(1)])]))
            self.assertTrue(r.indexed)
            self.assertFalse(r.path(1)[0], path)
        r = Reader(self.lib, database())
        self.assertFalse(r.path(42, size=12)[0])
        ok, value = r.text(r.tracks[1].title, size=8)
        self.assertTrue(ok)
        self.assertEqual(value, "한국")  # never splits a UTF-8 codepoint

    def test_duplicate_ids_counts_and_invalid_member_rejected(self):
        r = Reader(self.lib, database(tracks=[
            track(1, "a", ":iPod_Control:Music:a.mp3"),
            track(1, "b", ":iPod_Control:Music:b.mp3")]))
        self.assertFalse(r.indexed)
        malformed = bytearray(database())
        put(malformed, malformed.index(b"mhlt") + 8, 0xffffffff)
        self.assertFalse(Reader(self.lib, bytes(malformed)).opened)
        malformed = bytearray(database())
        user_playlist = malformed.index(b"mhyp", malformed.index(b"mhyp") + 4)
        put(malformed, malformed.index(b"mhip", user_playlist) + 8, 0xffffffff)
        r = Reader(self.lib, bytes(malformed))
        self.assertTrue(r.indexed)
        self.assertFalse(r.members(0)[0])

    def test_bad_string_encoding_and_read_errors(self):
        data = bytearray(database())
        at = data.index("我的 음악 🎵".encode("utf-16le"))
        data[at:at + 2] = b"\x00\xdc"  # lone low surrogate
        r = Reader(self.lib, bytes(data))
        self.assertTrue(r.indexed)
        self.assertFalse(r.text(r.playlists[0].title)[0])
        data = bytearray(database())
        at = data.index("한국어 日本語 中文".encode("utf-8"))
        data[at] = 0xff
        r = Reader(self.lib, bytes(data))
        self.assertFalse(r.text(r.tracks[1].title)[0])
        self.assertFalse(Reader(self.lib, database(), fail_at=500).indexed)
        self.assertFalse(Reader(self.lib, b"not an iTunes database").opened)

    def test_truncation_and_deterministic_corruption_no_out_of_bounds(self):
        original = database()
        for end in range(0, len(original), 31):
            self.assertFalse(Reader(self.lib, original[:end]).indexed)
        rng = random.Random(6)
        for _ in range(350):
            data = bytearray(original)
            at = rng.randrange(len(data) - 4)
            data[at:at + 4] = rng.randbytes(4)
            r = Reader(self.lib, bytes(data))
            if r.indexed:
                for i in range(r.db.playlist_count):
                    r.text(r.playlists[i].title)
                    ok, entries = r.members(i)
                    if ok:
                        for entry in entries:
                            r.path(entry.id)


if __name__ == "__main__":
    unittest.main()
