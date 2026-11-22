# Changelog

## 1.4

- Rewritten `modloader.bat`:
  - reliable Python 3.8+ detection (`py -3`, then `python`; skips the Microsoft Store placeholder);
  - clear message when Python is missing or too old;
  - exit code passed through;
  - fixed a command running twice when it failed.
- New Windows double-click helpers: `build_and_install.bat`, `uninstall.bat`, `status.bat`.
- `install`/`uninstall` stop before changing anything if a file is locked (game running) or read-only.
- `modloader.sh` falls back to `python` and checks the Python version.
- Python version check and UTF-8-safe error output in `modloader.py`.
- `.gitattributes` keeps Windows line endings in `.bat` files.

## 1.3

- Co-op mode is now the default and part of the loader: `build` puts every mod into `patch90.fbq`, which the game loads by
  itself. No `-mod=` launch option and nothing extra to download. Every player in online co-op needs the same `patch90.fbq`.
- The previous two-package behavior is now `build --modpack`. `build --coop` is still accepted (same as `build`).
- `live` checks for its script in `patch90.fbq` as well as `modpack.fbq`.

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
