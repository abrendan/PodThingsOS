"""Native browser flows with host UI/allocator/storage shims, not a simulator."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from test_itunes_playlists import APPS, ROOT, database, track, playlist, member, put


class ITunesBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        folder = Path(cls.temp.name)
        # Use the entire production browser body; only platform headers are
        # replaced by the explicit host shims in the harness.
        body = (APPS / "podthings_itunes.c").read_text()
        body = re.sub(r'^#include .*\n', '', body, flags=re.M)
        (folder / "itunes-ui-under-test.c").write_text(body)
        cls.exe = folder / "browser-test"
        subprocess.run([
            "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
            "-fsanitize=undefined", "-fno-sanitize-recover=all",
            "-I", str(folder), "-I", str(APPS),
            str(ROOT / "tests/itunes_ui_harness.c"),
            str(APPS / "podthings_itunesdb.c"), "-o", str(cls.exe),
        ], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_flow(self, scenario, db=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            apple = root / "iPod_Control"
            (apple / "iTunes").mkdir(parents=True)
            (apple / "Music/F00").mkdir(parents=True)
            (apple / "Music/F01").mkdir(parents=True)
            (root / ".podthingsloader").mkdir()
            (apple / "Music/F00/DEF.mp3").write_bytes(b"fixture-media")
            (apple / "Music/F01/ABC.m4a").write_bytes(b"fixture-media")
            if scenario != "no_db":
                (apple / "iTunes/iTunesDB").write_bytes(
                    db if db is not None else database())
            sentinel = root / ".podthingsloader/itunes-playback-a.m3u8"
            sentinel.write_bytes(b"existing playback must survive\n")
            before = {p.relative_to(root): hashlib.sha256(p.read_bytes()).digest()
                      for p in apple.rglob("*") if p.is_file()}
            result = subprocess.run([str(self.exe), tmp, scenario],
                                    capture_output=True, text=True,
                                    env={**os.environ, "UBSAN_OPTIONS": "halt_on_error=1"})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            after = {p.relative_to(root): hashlib.sha256(p.read_bytes()).digest()
                     for p in apple.rglob("*") if p.is_file()}
            self.assertEqual(before, after, "Apple database/media must be untouched")
            self.assertEqual(sentinel.read_bytes(), b"existing playback must survive\n")
            return result.stdout

    def test_browse_and_start_at_selected_track(self):
        self.run_flow("play")
        self.run_flow("shuffle")

    def test_cancel_back_empty_and_usb(self):
        for scenario in ("back", "empty", "usb", "usb_loading", "wps",
                         "cancel_replace", "party"):
            with self.subTest(scenario=scenario):
                self.run_flow(scenario)

    def test_failure_paths_preserve_source_and_active_playlist(self):
        for scenario in ("write_error", "rename_error", "oom_index",
                         "oom_members", "size_limit", "no_db"):
            with self.subTest(scenario=scenario):
                self.run_flow(scenario)
        self.run_flow("bad_db", b"invalid iTunes database")
        data = bytearray(database())
        user_playlist = data.index(b"mhyp", data.index(b"mhyp") + 4)
        put(data, data.index(b"mhip", user_playlist) + 8, 0xffffffff)
        self.run_flow("bad_members", bytes(data))

    def test_missing_protected_unsupported_tracks_are_reported(self):
        tracks = [
            track(42, "First", ":iPod_Control:Music:F01:ABC.m4a"),
            track(7, "Second", ":iPod_Control:Music:F00:DEF.mp3"),
            track(8, "DRM", ":iPod_Control:Music:F00:LOCK.m4p"),
            track(9, "Missing file", ":iPod_Control:Music:F00:gone.mp3"),
            track(10, "Not audio", ":iPod_Control:Music:F00:file.txt"),
        ]
        db = database(tracks=tracks, playlists=[
            playlist("Some unavailable", [member(id) for id in (999, 42, 7, 8, 9, 10)])])
        self.assertIn("Skipped 4", self.run_flow("skip", db))
        self.assertIn("missing, protected, or unsupported", self.run_flow("missing", db))


if __name__ == "__main__":
    unittest.main()
