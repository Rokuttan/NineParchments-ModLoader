# NPModLoader — mod loader for Nine Parchments (v1.1.0)

An unofficial mod loader for **Nine Parchments** (Frozenbyte). It lets you change spell and
staff stats, XP/levels, texts and UI, replace game files and run Lua scripts during the game —
without touching the original game files.

> Not affiliated with or endorsed by Frozenbyte. No game files are included; you need your own copy of the game.

> **This is the `double-skill-tree-MOD` branch.** It is the loader plus the
> **[Level cap 276 + double skill tree](mods/double_skill_tree/README.md)** mod. With it, every perk can be upgraded
> twice (5 → 10 points, with purple bars for the second round), the extra points really apply, and the level cap is
> raised to 276. See the mod's README for what it does and how to install it. The plain loader is on the `main` branch.

## Features

- **Stat changes** for spells, staves, perks, XP and levels (`stats`), with absolute values or `*1.5` / `+10` modifiers; tooltips are regenerated to match the new values.
- **Text changes** (names, descriptions) per language.
- **File replacement** (UI, textures, audio, data) through a mod's `files/` folder.
- **Lua scripts** that run during the game, plus **live value editing** while the game is running.
- **Executable patches** (`exe_patches`) for changes that can't be made through game data — see below.
- **Online co-op ready by default**: everything goes into `patch90.fbq`, which the game loads by itself. No launch options, no separate download.
- **Classic mode** (`build --modpack`): gameplay mods go into a separate `modpack.fbq`, loaded with `-mod=modpack.fbq`.
- **Safe install/uninstall**: the loader tracks what it installed, refuses to overwrite files it didn't create, and `uninstall` restores everything.

### New in 1.3

- **Co-op mode is now the default and built into the loader.** `build` puts every mod (stats, scripts, texts, textures) into `patch90.fbq`,
  which the game loads automatically: no `-mod=` launch option and nothing extra to download. It works in online co-op as long as
  every player installs the same `patch90.fbq`.
- The previous behavior is still available as `build --modpack`. `build --coop` still works, and now does the same as `build`.
- `live` (live tweaks) now also finds its script inside `patch90.fbq`.

### New in 1.2

- **`exe_patches` in `mod.json`**: a mod can now patch bytes in `nineparchments_64bit.exe` (addresses as shown by a disassembler).
  - Every patch is **validated before building**: the current bytes must match `original` (or `patched`), so a mod made for another game version fails with a clear error instead of corrupting the game.
  - Patches from different mods that **overlap** are reported as conflicts.
  - On the first patch the loader keeps a **backup of the original executable** (`build/modloader/backup/`).
  - `install` applies the patches; **reinstalling a newer version of a mod** first restores the spans it no longer uses, then applies the new ones.
  - `uninstall` **restores the original bytes**, and `status` shows how many patched spans are still applied (a Steam update or "Verify integrity of game files" restores the executable; just run `install` again).
  - `list` flags mods that patch the executable.

## How it works

The game natively loads extra `.fbq` packages. The loader merges every active mod into one of them:

| Mode | Package | Contains | How the game loads it | Achievements |
|---|---|---|---|---|
| **co-op (default)** — `build` | `patch90.fbq` | every mod | automatically | not disabled |
| classic — `build --modpack` | `patch90.fbq` | visual / client mods (texts, UI, textures, audio) | automatically | keep working |
| | `modpack.fbq` | gameplay mods (stats, scripts, other files) | launch option `-mod=modpack.fbq` | **disabled** |

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
python modloader.py build       merges the active mods into patch90.fbq (build/ folder)
python modloader.py install     copies the packages into the game folder
python modloader.py uninstall   removes everything the loader installed
python modloader.py status      shows what is installed
```

That's it: start the game normally. No launch options are needed. To play without mods, run `uninstall`.

**Classic mode:** `python modloader.py build --modpack` puts gameplay mods into a separate `modpack.fbq`. Then add this to
the game's Steam launch options (Properties > General > Launch Options):

- Windows: `-mod=modpack.fbq`
- Linux / Steam Deck (Proton): `%command% -mod=modpack.fbq`

Remove that option again when you go back to co-op mode or play without mods.

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

### Online co-op with mods

Co-op is the default, so just run `build` and `install`. **Every player must install the same `patch90.fbq`.**
Copy it from `build/modloader/`, or share the same `mods` folder and `load_order.txt` and let each player build it.
The game does not compare this file between players: if the versions differ, nobody is warned and each computer
may use different values. If `-mod=modpack.fbq` is still in your launch options from an older version, remove it.

## Important notes

- **Achievements:** the game only disables them when it is started with `-mod=modpack.fbq` (classic mode with gameplay mods). Co-op mode (default) and visual-only mods don't disable them.
- **Online co-op:** every player needs the **same** `patch90.fbq` (or, in classic mode, the same `modpack.fbq`).
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
