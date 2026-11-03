# PodThings OS clickwheel navigation

These changes apply only to iPod Video 5G and Classic 6G.

| Screen | Control | Behavior |
| --- | --- | --- |
| Core menus and file/library lists | Wheel | Move selection |
| Core menus and file/library lists | Select | Enter or confirm |
| Core menus and file/library lists | Menu tap | Go back one level |
| Core menus and file/library lists | Menu hold | Main menu |
| Core menus and file/library lists | Previous / Next | Not Back / Enter |
| Now Playing | Menu tap | Return to the previous browser |
| Now Playing | Menu hold | Main menu |
| Now Playing | Previous / Next tap | Previous / next track |
| Now Playing | Previous / Next hold | Seek backward / forward |
| Now Playing | Play/Pause | Toggle playback |
| Settings editors | Menu tap | Cancel / return |
| QuickScreen | Menu | Exit |
| QuickScreen | Select | Adjust the top item |
| Bookmarks | Select + Play | Delete the selected bookmark |

Holding Menu no longer opens QuickScreen, and must not delete a bookmark.
The old horizontal-scrolling option must not restore Previous-as-Back.

This changes native Rockbox navigation, not its menus into a complete replica
of Apple's software. Plugins and specialized editing screens can have their
own controls. Play/seek behavior on Now Playing is retained; this change does
not add global track skipping to every menu.

Run the source-level mapping checks with:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

These checks preprocess the actual C keymap for both targets and another iPod
as a regression control. They are not substitutes for physical-device tests.
