# NPModLoader — mod loader for Nine Parchments (v1.1.0)

An unofficial mod loader for **Nine Parchments** (Frozenbyte). It lets you change spell and
staff stats, XP/levels, texts and UI, replace game files and run Lua scripts during the game —
without touching the original game files.

> Not affiliated with or endorsed by Frozenbyte. No game files are included; you need your own copy of the game.

## Features

- **Stat changes** for spells, staves, perks, XP and levels (`stats`), with absolute values or `*1.5` / `+10` modifiers; tooltips are regenerated to match the new values.
- **Text changes** (names, descriptions) per language.
- **File replacement** (UI, textures, audio, data) through a mod's `files/` folder.
- **Lua scripts** that run during the game, plus **live value editing** while the game is running.
- **Executable patches** (`exe_patches`) for changes that can't be made through game data — see below.
- **Automatic visual/gameplay split**: visual mods keep achievements working; gameplay mods go into a separate package.
- **Experimental online co-op mode** (`build --coop`).
- **Safe install/uninstall**: the loader tracks what it installed, refuses to overwrite files it didn't create, and `uninstall` restores everything.

### New in 1.2

- **`exe_patches` in `mod.json`**: a mod can now patch bytes in `nineparchments_64bit.exe` (addresses as shown by a disassembler).
  - Every patch is **validated before building**: the current bytes must match `original` (or `patched`), so a mod made for another game version fails with a clear error instead of corrupting the game.
  - Patches from different mods that **overlap** are reported as conflicts.
  - On the first patch the loader keeps a **backup of the original executable** (`build/modloader/backup/`).
  - `install` applies the patches; **reinstalling a newer version of a mod** first restores the spans it no longer uses, then applies the new ones.
  - `uninstall` **restores the original bytes**, and `status` shows how many patched spans are still applied (a Steam update or "Verify integrity of game files" restores the executable; just run `install` again).
  - `list` flags mods that patch the executable.

## How it works

The game natively loads extra `.fbq` packages. The loader merges every active mod and builds up to two of them:

| Package | Contains | How the game loads it | Achievements |
|---|---|---|---|
| `patch90.fbq` | visual / client mods (texts, UI, textures, audio) | automatically | keep working |
| `modpack.fbq` | gameplay mods (stats, scripts, other files) | launch option `-mod=modpack.fbq` | **disabled** |

Original game packages are never modified. The only exception is a mod that uses `exe_patches`: the loader then patches
`nineparchments_64bit.exe`, keeping a backup. `uninstall` removes everything the loader installed and restores the executable.

## Installation

1. Put the **NPModLoader** folder inside the game folder, next to `nineparchments_64bit.exe`:
   ```
   Nine Parchments/
     nineparchments_64bit.exe
     script1.fbq ...
     NPModLoader/        <- this folder
   ```
   In Steam: right-click the game > Manage > Browse local files.
2. Install **Python 3.8 or newer**. On Linux it is usually already installed; on Windows, get it from python.org and tick "Add Python to PATH".

## Usage

Open a terminal **inside the NPModLoader folder**. On Windows use `modloader.bat` instead of
`python modloader.py`; on Linux, `./modloader.sh` or `python3 modloader.py`.

```
python modloader.py list        shows the mods and whether each one is visual or gameplay
python modloader.py build       merges the active mods into packages (build/ folder)
python modloader.py install     copies the packages into the game folder
python modloader.py uninstall   removes everything the loader installed
python modloader.py status      shows what is installed
```

If there are gameplay mods, add this to the game's Steam launch options
(Properties > General > Launch Options):

- Windows: `-mod=modpack.fbq`
- Linux / Steam Deck (Proton): `%command% -mod=modpack.fbq`

To play without mods, remove that option (or run `uninstall`).

## Making mods

Start with **[`mods/example_mod/`](mods/example_mod/)**: a complete, commented mod with its own guide,
[`mods/example_mod/README.md`](mods/example_mod/README.md). It ships disabled — change
`"enabled": false` to `true` in its `mod.json` to try it.

A minimal mod is just a folder with a `mod.json`:

```json
{
  "name": "Stronger Fireball",
  "version": "1.0",
  "author": "you",
  "enabled": true,
  "stats": {
    "FireballProjectileSpellComponent": { "BasePower": "*2", "MaxStacks": "+1" }
  },
  "text": {
    "en": { "menu/spells:namefireball": "Big Fireball" }
  }
}
```

Helper commands:

```
python modloader.py new my_mod                                 creates mods/my_mod/mod.json
python modloader.py search Fireball                            searches game objects by name
python modloader.py props FireballProjectileSpellComponent     shows what you can change
python modloader.py extract script1.fbq FOLDER [filter]        extracts original game files
```

`load_order.txt` sets the order: mods further down win conflicts. Lines starting with `#` are disabled.

### Testing values while the game is running

The `mods/live_tweaks` mod (disabled by default) changes values while you play:
```
python modloader.py live set FireballProjectileSpellComponent.BasePower 300
python modloader.py live dump      (lists your spells)
python modloader.py live clear     (restores everything)
```
Changes are lost when the game closes. Once you find the right value, put it in `stats` in your mod.

### Executable patches (`exe_patches`)

Some changes live in the game's code, not in its data (for example, a hardcoded limit). For those, a mod can list
byte patches for `nineparchments_64bit.exe`:

```json
"exe_patches": [
  {
    "va": "0x14051d586",
    "original": "05",
    "patched": "0a",
    "note": "what this patch does"
  }
]
```

- `va`: virtual address of the first byte, as shown by a disassembler (image base `0x140000000`).
- `original` / `patched`: hex bytes, same length. The build fails if the executable contains neither.
- Longer code can go in unused padding (`int3`/`0xCC` bytes) and be reached with a `jmp`; the loader just writes bytes.
- Patches only target **Nine Parchments v1.1.0 (build 4722)**.
- The loader backs up the original executable on the first patch, and `uninstall` restores it.
- A mod with `exe_patches` counts as a gameplay mod. The patches are applied whether or not the game is started with `-mod=`.
- Every player in online co-op needs the same patches, the same as with any gameplay mod.

### Online co-op with gameplay mods (experimental)

```
python modloader.py build --coop
python modloader.py install
```
Puts everything (stats, scripts, texts) into `patch90.fbq`, which the game loads by itself. **Remove
`-mod=modpack.fbq` from the launch options.** The game does not compare this file between players,
so **every player must install the same `patch90.fbq`** (copy it from `build/modloader/`). If the
versions differ nobody is warned and each computer may use different values. Achievements are not
disabled in this mode. This mode has not been fully tested online yet.

## Important notes

- **Achievements:** disabled while the game is started with `-mod=modpack.fbq`, i.e. when there are gameplay mods. Visual-only mods don't disable them.
- **Online co-op:** with `modpack.fbq`, every player needs the **same** file. Visual mods are not part of the check.
- **Saves:** mods that change levels/XP are stored in your save. Back it up first.
- The game loads displayed text when a level starts: change level or restart the game after installing.

## Troubleshooting

| Message | Fix |
|---|---|
| "Could not find Nine Parchments" | the NPModLoader folder is not inside the game folder (or set `NINE_PARCHMENTS_DIR`) |
| "no active mods" | a mod needs `"enabled": true` and must not be commented out in `load_order.txt` |
| "already exists in the game folder and was not installed by the loader" | another mod already uses `modpack.fbq`/`patch90.fbq`; remove or rename it |
| "the bytes in the executable are not the expected ones" | the `exe_patches` were made for another game version, or another tool changed the executable |
| `status` shows fewer patched spans than expected | Steam restored the executable (update or file check): run `install` again |
| script doesn't run | check `log/nineparchments.log` in the game folder (`[modloader]` lines) and whether `np_modloader.txt` was created |

## Repository layout

```
modloader.py         the loader (command line)
modloader.bat/.sh    launchers for Windows / Linux
load_order.txt       mod load order
CHANGELOG.md         what changed in each version
mods/example_mod/    commented example mod + modding guide
mods/live_tweaks/    live value editing while the game runs
tools/               file format libraries, also usable on their own:
  fbq.py             .fbq package reader/writer (list/unpack/pack/verify)
  typedb.py          types.bin stats database reader/editor
  luachunk.py        Lua 5.1 bytecode reader/writer
  luadis.py          Lua 5.1 bytecode disassembler
  locale_regen.py    regenerates tooltips after stat changes
  xptable.py         XP/level table calculator
```

## License

[MIT](LICENSE)
