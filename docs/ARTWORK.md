# Album artwork

## Priority

Now Playing and Cover Flow prefer:

1. **iTunes-synced artwork**, when a matching usable thumbnail exists.
2. **Embedded artwork** in the music file, including normal non-iTunes libraries.
3. **The placeholder** when there is no supported usable image.

External folder/cover.jpg files are not a fourth priority in this release.
Now Playing respects the native album-art Off setting. Cover Flow remains a
separate cover browser.

Cover Flow checks tracks across the album, rather than only the first track.
Available iTunes artwork on a later track outranks an embedded cover found on
an earlier track. The first supported embedded JPEG is the album fallback.
Now Playing resolves the current file's artwork.

## Apple artwork

The reader uses `iPod_Control/iTunes/iTunesDB` and
`iPod_Control/Artwork/ArtworkDB`, then reads the referenced `.ithmb` file in
that Artwork directory. It understands the older 64-bit track DBID association
and the newer shared MHII-image-ID link used by Classic iTunes libraries.
Track pathname matching is case insensitive.

Supported cover formats:

| Device family | Format IDs | RGB565 canvas |
| --- | --- | --- |
| Photo/Color 4G | 1017, 1016 | 56×56, 140×140 |
| Video 5G/5.5G | 1028, 1029 | 100×100, 200×200 |
| Classic 6G | 1061, 1055, 1068, 1060 | 56×56, 128×128, 128×128, 320×320 |

The largest valid available thumbnail is selected. Padding and file offsets are
honored. Missing/unsupported/malformed Apple artwork falls back to embedded
art; no unknown pixel layout is guessed. UTF-8/UTF-16 ASCII thumbnail basenames
are supported; absolute paths and traversal are rejected.

ArtworkDB dimensions include the leading padding; the reader subtracts that
padding once to get the actual image extent. This matters for rectangular and
letterboxed covers as well as thumbnails occupying an entire canvas axis.
An unusable image header is skipped when its total record boundary is valid,
so it cannot suppress unrelated albums. Invalid total lengths still fail safely;
the reader never guesses where the next record starts.

This reads classic uncompressed iTunesDB/ArtworkDB, not Music.app desktop
caches, a desktop iTunes album-art folder, a Photo Database, iTunesCDB, encrypted
artwork or every newer iPod artwork format. Library limits are the existing
100,000-track iTunes reader and 200,000 ArtworkDB image records.

## Embedded artwork

The native firmware decoder handles **embedded JPEG**, with its existing ID3
unsynchronization and Vorbis base64 support. Common MP3/M4A/FLAC JPEG covers are
supported when recognized by the native metadata reader. Embedded PNG/BMP is
not newly supported by this change. Unsupported or corrupt embedded images
use the placeholder rather than pretending a decoder succeeded.

Cover Flow calls the same bounded native JPEG decoder as playback. The plugin
API version changes, so the complete matching plugin set must be installed.

## Local derived cache

Apple's files and music are opened read-only. The reader creates its own bounded
on-disk lookup index and derived BMPs in `/.podthingsloader/itunes-art/`.
This avoids scanning the entire iTunes library separately for every cover.
Source fingerprints validate the index; resolved track/image links are checked
against the current databases. Thumbnail-pixel hashes prevent reusing an old
bitmap merely because a re-sync retained the same filename and byte length.
Partial/corrupt derived index and BMP files are regenerated.

Cover Flow maintains its separate native slide cache. The old cache version
is invalidated automatically during this update; normal Update/Rebuild Cache
commands remain available in Cover Flow's menu after later library changes.
Caches consume disk space. They are derived, not the user's original artwork.

If covers still fail:

1. Confirm firmware **and all bundled plugins/themes** are from the same release.
2. Check that the native music database includes the affected files.
3. Confirm artwork was synced onto the iPod, not merely displayed in desktop
   iTunes. A missing ArtworkDB/ITHMB cannot be reconstructed from a playlist.
4. For non-iTunes music, check whether the file really embeds a supported JPEG.
5. Refresh Cover Flow's cover cache after re-syncing.

No physical device was connected during development. Tests use synthetic
Apple-format fixtures with known pixels and byte-for-byte source-file checks.
Real iTunes library/storage combinations still need device verification.

## Format references

Independently implemented against the documented structures and device tables:

- https://github.com/fadingred/libgpod/blob/master/src/db-itunes-parser.h
- https://github.com/fadingred/libgpod/blob/master/src/db-artwork-parser.c
- https://github.com/fadingred/libgpod/blob/master/src/itdb_itunesdb.c
- https://github.com/fadingred/libgpod/blob/master/src/itdb_device.c

Native PictureFlow/Rockbox authorship and GPL notices are retained in source
and distribution documentation. The on-device large PictureFlow logo is gone.
