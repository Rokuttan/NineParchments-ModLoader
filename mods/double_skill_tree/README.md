# Level cap 276 + double skill tree

A mod for **Nine Parchments v1.1.0 (build 4722)**, made for [NPModLoader](../../README.md) 1.3 or newer (1.4+ for the Windows double-click files).

## What it does

- **Every perk can be upgraded twice.** A perk with 5 points can now go up to **10**. Perks that only take 1 point (such as Gislan's *Everbloom*) stay at 1.
- **The extra points really count.** Each point from 6 to 10 adds the same bonus as the first five. The game's own clamp that cut perk effects back to 5 points is removed.
- **Purple bars for the second round.** No new bars are added: from the 6th point on, the perk's existing bars turn purple one by one (7 points = 2 purple bars, 10 points = all 5 purple). Trees that are already purple use a brighter purple.
- **Level cap 276.** That's enough points to fill the biggest tree (Apprentice, 275 points) twice.
  - The original XP curve is kept up to **level 89**, where it peaks at **22,054 XP per level**.
  - From level 90 to 276, every level costs **22,054 XP**.
- **Manifest Darkness (Selius) fix.** This perk reads its orb count from a 5-row table and, without the fix, would spawn nothing at 6+ points. With the mod it keeps growing:

  | Points | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
  |---|---|---|---|---|---|---|---|---|---|---|
  | Orbs | 1 | 2 | 2 | 2 | 3 | 4 | 5 | 5 | 5 | 6 |

### How it works

Most of this lives in the game's code, not in its data, so the mod uses NPModLoader's `exe_patches`. It patches 8 small spans of `nineparchments_64bit.exe`:

- the per-perk point limit, plus a second limit hardcoded to 5;
- the effect clamp;
- the XP formula;
- the bar drawing;
- the Manifest Darkness table.

The loader checks every span before patching, keeps a backup of the original executable and restores it on `uninstall`. Each patch is described in [`mod.json`](mod.json), and the source of the added code is in [`asm/patch.s`](asm/patch.s).

The purple bars reuse textures the game already has. The game ignores textures with new names, so the brighter purple for purple trees goes into the 3-point perk bar textures, which exist but are never used because no perk has 3 points. Those 5 images are generated from your own copy of the game by `make_textures.py`, so no game files are distributed.

## How to install it in the loader

1. **Get the loader with the mod.** Either:
   - download this branch: on GitHub, switch the branch selector to **`double-skill-tree-MOD`**, then click **Code > Download ZIP**; or
   - download `double_skill_tree-2.5.zip` from the [Releases page](https://github.com/Rokuttan/NineParchments-ModLoader/releases) and extract it into the `mods` folder of an NPModLoader you already have (1.3 or newer), so you get `NPModLoader/mods/double_skill_tree/mod.json`.
2. **Place the loader.** The `NPModLoader` folder must be inside the game folder, next to `nineparchments_64bit.exe`.
3. **Check the load order.** Make sure `double_skill_tree` is listed in `load_order.txt` (it already is on this branch; add the line if you copied the mod into another loader).
4. **Close the game**, then generate the textures and install. You need Python 3.8 or newer.

   **Windows (double-click):**
   1. `NPModLoader\mods\double_skill_tree\make_textures.bat`, once.
   2. `NPModLoader\build_and_install.bat`.

   **Linux / Steam Deck, or a terminal on Windows** (in the `NPModLoader` folder; use `python3` on Linux):
   ```
   python mods/double_skill_tree/make_textures.py
   python modloader.py build
   python modloader.py install
   ```
5. **Start the game normally.** No launch options are needed.

To remove it, double-click `uninstall.bat` (or run `python modloader.py uninstall`). That removes the package and restores the original executable. `status.bat` shows whether the patches are applied.

### Notes

- **Saves:** levels and points are stored in your save. Back up your save before using the mod. If you uninstall the mod later, a character with more than 5 points in a perk or above the normal level cap may behave unexpectedly.
- **Online co-op:** every player needs the same mod, installed the same way. The loader's default mode puts everything into `patch90.fbq`.
- **Steam updates:** a Steam update or "Verify integrity of game files" restores the original executable. Run `build_and_install.bat` (or `python modloader.py install`) again. `python modloader.py status` shows whether the patches are applied.
- **Other game versions:** if your game is not v1.1.0 (build 4722), `build` stops with *"the bytes in the executable are not the expected ones"* and nothing is changed.
