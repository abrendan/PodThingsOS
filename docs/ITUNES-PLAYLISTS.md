# iTunes playlists — PodThings OS 0.6

## Use

1. Sync music and playlists to the iPod with iTunes as usual, then eject it.
2. Boot PodThings OS and open **Playlists → iTunes Playlists**.
3. Choose a playlist to browse its tracks. Select a track to start the playlist
   from that track. Menu goes back. Your normal shuffle/repeat settings apply.
4. **Playlists → Saved Playlists** retains the normal editable M3U/M3U8 catalog.

There is no manual import or database scan to run. Opening the iTunes browser
reads the current `iPod_Control/iTunes/iTunesDB` from disk. After another sync,
reopen the browser to see the new playlist names, membership and order.
Unicode playlist/track/artist names use the existing multilingual fonts.

## Read-only means the Apple library is never modified

- The browser never opens the iTunes database for writing and never changes
  synced playlists, music, play counts, ratings, smart rules or database checksums.
- iTunes views have no rename/delete/move/edit/save context menu.
- Playback uses a private M3U8 snapshot inside `/.podthingsloader/`, with a
  normal PodThings OS playback queue. The existing current-playlist replacement
  warning and party-mode protection still apply.
- Working-queue changes through the normal Current Playlist screen affect only
  this playback copy, **not** the iTunes playlist. There is no write-back/sync.
- Two internal playback slots prevent an unsuccessful/cancelled preparation
  from overwriting the file backing the current playlist. A failed low-level
  playback-engine load after accepting replacement is still reported explicitly;
  it is not a transactional rollback of the audio engine.
- USB events during browsing/loading close the reader and temporary copy before
  handing the disk to USB. Reopen the browser after syncing.

## Supported scope and limits

- Classic, uncompressed **iTunesDB** on iPod Video 5G/5.5G and Classic 6G,
  using standard `mhbd/mhsd/mhit/mhyp/mhip/mhod` records. Extended playlist
  dataset 3 is preferred to dataset 2, avoiding duplicate playlists.
- Normal synced playlists and the **last synced contents** of smart playlists.
  Smart rules are not evaluated on the iPod. The hidden master-library playlist
  is omitted. Empty playlists display an explicit message.
- Membership uses Apple track IDs, not filenames or display names. The reader
  preserves playlist-position metadata and repeated tracks, including legacy
  iTunes records whose item lengths exclude their metadata.
- Only local media paths under `/iPod_Control/` are accepted. Traversal, URLs,
  malformed text, truncated paths and out-of-bounds database records are rejected.
- Missing files, unresolved track IDs, `.m4p` protected purchases and unsupported
  file extensions are skipped with a count when starting a playable track.
  Selecting an unavailable track instead displays an error and does not replace
  the current playlist. No DRM decryption is added.
- Compressed **iTunesCDB**, iOS Music/SQLite libraries, streaming/cloud-only
  playlists, unsynced computer-only playlists and on-device smart-rule
  recalculation are not supported. A missing/invalid/unsupported database is
  reported, not silently treated as an empty library.
- The reader supports up to **100,000 library tracks**, **4,096 playlist
  records**, and **100,000 members per playlist**, subject to available memory.
  The normal current-playlist size setting also limits playable entries;
  exceeding it aborts preparation rather than silently cutting off the playlist.
  The index uses 16 bytes/track and 16 bytes/playlist; the selected playlist uses
  another 12 bytes/member, plus the small read cache and UI data.
- A playable file extension does not guarantee successful decoding of a damaged
  or otherwise unsupported audio file; normal playback-engine errors still apply.
- Font coverage is unchanged: broad BMP coverage including CJK; supplementary
  emoji/rare Han and complex shaping remain native-engine limitations.

## Verification

Host tests execute the actual C reader and browser body with synthetic iTunesDB
fixtures, platform UI/storage shims, and a real temporary filesystem. They check
UTF-16/UTF-8 names, positions, duplicate members, smart snapshots, missing files,
shuffle selection, cancellations, USB cleanup, allocation/storage failures,
corrupt records and source-file hashes. The browser harness runs with undefined
behavior sanitization. These tests are **not an iPod simulator** and do not
validate real audio decoding or every database produced by iTunes.

Hardware checklist: on each model, compare playlist names/order with Apple
firmware; play a mid-list track with shuffle off/on; try an empty playlist and
a missing/protected item; cancel the replacement prompt; sync changed playlists
over USB and reopen; confirm Apple firmware still sees the unchanged library.
No physical iPod or personal iTunes database was available for this release.
