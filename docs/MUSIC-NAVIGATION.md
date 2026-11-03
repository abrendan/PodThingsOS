# Music-first navigation

## Home

The default home screen is now:

1. **Continue Listening** — current playback, or the normal saved-playlist resume.
2. **Music** — Browse Music, A-Z Jump, Search Music, Cover Flow, Playlists, Shuffle, Favorites.
3. **Recently Played Albums** — the 24 most recently played distinct
   album/album-artist groups, using the newest played track in each album.
4. **Favorites** — the native persistent shortcut collection.
5. **Settings** — Appearance, Music, Device, About and Advanced.
6. **Extras** — Files, Games & Plugins, Recording where available, Recent Bookmarks.

Files, database, plugins, recording and the other root entries are still
available in Settings → Advanced → Main Menu Configuration. A deliberately
customized root-menu order is preserved. To adopt the new home layout on such
an installation, reset **only the main menu configuration**, not all settings.

## Library and search

Browse Music uses the real native music database: album artists, artists,
albums, genres, years and songs. A-Z Jump groups album artists, artists, albums
or tracks into numeric, A–Z and other-character sections. The last group retains
access to non-Latin names. Search Music uses the native artist/album/title
search prompts and click-wheel keyboard.

Normal library Back/selection history remains in place. Leaving for playback
and returning to the same library root retains the native browser position.
Switching between Browse Music, A-Z and Search resets to that view's root,
rather than incorrectly reusing a different view's deeper history.
Custom tagnavi_user.config remains authoritative. A custom menu that removes
the standard main/a2z/search IDs may make those shortcuts unavailable; the
firmware reports this instead of opening an unrelated view.

The standard installed navigation config now uses `/.podthingsloader/` for
custom include paths as well as modernized labels. The internal parser's
Rockbox format signature is intentionally retained for compatibility.

## Database setup

These are local-library features; the native database still indexes the music:

- Build the database through Browse Music's normal initialization prompt.
  Database maintenance options remain in Settings → Advanced → General Settings.
- Make sure scan paths include the music on the iPod, including iPod_Control
  for synced iTunes tracks. Rebuild/update the database after adding music.
- Files and iTunes Playlists remain usable separately; iTunes playlist browsing
  does not itself build the native music database.

## Recently Played Albums

Listening history defaults on for fresh installations. Existing preferences
are not silently changed. If history is off, opening Recent Albums asks
permission to enable it. It is stored on the iPod, not uploaded.
It can also be changed in Settings → Music → Listening History.

History uses the existing native runtime/play-count rules and persisted
last-played serial values. It is not a fabricated sample list and is not
populated retroactively from Apple firmware's listening history. A newly
started song may not appear until its listening statistics are committed.
An empty history displays an explicit message.

Selecting an album prepares all its indexed tracks in disc/track order, then
uses the normal playback queue. Current-playlist replacement warnings,
party mode and shuffle/repeat settings still apply. Unavailable/protected tracks
are skipped with a count. Playback copies live in the firmware resource folder;
the source music and Apple database are not changed. Track ordering is stable
by native index when disc/track tags are absent or tied.

## Favorites

Use a saved playlist's normal context menu → **Add to Shortcuts** (wording may
vary by language) to pin it, then open it from Home → Favorites. The same native
collection can also hold tracks, folders and settings. Removing a shortcut
does not delete its target.

An iTunes playlist's read-only browser has no pin/edit context menu in this
release. Favorites is not a second iTunes library or a copy of its database.

## Cover Flow

**Music → Cover Flow** launches the native album-cover browser with a small
Cover Flow title, not the old large PictureFlow splash logo.
It provides wheel-controlled, perspective album-cover browsing and album-track
selection/playback. Its cache/preferences remain compatible with PictureFlow.

- It needs a usable native music database. Art priority is iTunes ArtworkDB/ITHMB,
  then supported embedded art, then a placeholder. See ARTWORK.md.
- Initial indexing/cover-cache building may take time. The old folder-only
  cover cache is automatically invalidated on this update. Albums without usable
  art use the engine's placeholder.
- Existing PictureFlow controls, settings and memory limitations apply. It is
  not Apple's proprietary Cover Flow software or a pixel-identical clone.
- The engine may stop current audio while it allocates its album-art buffer.
  This is an existing native plugin limitation, not seamless background playback.

## Shuffle

The Shuffle setting is directly in **Music → Shuffle**, rather than buried in
Settings → Music → Playback. It is the native persistent shuffle toggle, not
a new command that silently discards/replaces the current playlist.

## Settings

- **Appearance:** themes and display.
- **Music:** sound, playback, playlist settings and listening-history collection.
- **Device:** system/storage/USB controls, startup/shutdown and date/time.
- **About:** device/system information and the existing attribution/credits.
- **Advanced:** the complete general settings, recording settings, home-menu
  configuration and saved-settings management.

Reboot to Official Firmware remains directly in Settings and is also available
under Device. No old settings are intentionally removed.
