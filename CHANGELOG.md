# Changelog

## 1.2

- New `exe_patches` field in `mod.json`: byte patches for `nineparchments_64bit.exe`.
  - Patches are validated against the current executable when building (wrong game version → clear error, nothing is built).
  - Overlapping patches from different mods are reported as conflicts.
  - The original executable is backed up on the first patch (`build/modloader/backup/`).
  - `install` swaps patches from older mod versions for the new ones; `uninstall` restores the original bytes.
  - `status` reports how many patched spans are applied; `list` flags mods that patch the executable.
- Docs: executable patches, and a note that new texture names are not loaded (only existing ones can be replaced).

## 1.1

- First public release: stats, texts, file replacement, Lua scripts, live tweaks, experimental co-op mode.
