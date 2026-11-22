# Example mod — how to make a mod

This folder is a complete mod. To try it, open `mod.json`, change `"enabled": false`
to `"enabled": true` and run `build` and `install` (see the main README).

To create your own: `python modloader.py new my_mod` (or copy this folder and rename it).

## Files in a mod

```
mods/my_mod/
  mod.json        required: name, stats, texts, scripts
  *.lua           optional: scripts listed in "scripts"
  files/          optional: files that replace game files
```

## mod.json, field by field

| Field | What it does |
|---|---|
| `name`, `version`, `author`, `description` | info shown by `list` |
| `enabled` | `false` turns the mod off without deleting it |
| `stats` | changes game values (damage, charges, cooldown, staff bonuses, XP...) |
| `text` | changes names and descriptions |
| `scripts` | Lua scripts that run during the game |
| `exe_patches` | byte patches for the game executable, for changes the data can't make (see the main README) |

### stats

```json
"stats": {
  "FireballProjectileSpellComponent": {   <- game object
    "BasePower": "*1.5",                   <- multiplies the original by 1.5
    "MaxStacks": "+2",                     <- adds 2 (use "-2" to subtract)
    "RestoreStackTime": 3.0                <- fixed value (times are in seconds)
  }
}
```

If several mods change the same value, the operations are applied in load order
(e.g. `*2` then `+1`).

How to find object and property names:

```sh
python modloader.py search Fireball                          # lists objects with "Fireball" in the name
python modloader.py props FireballProjectileSpellComponent   # shows what you can change
```

Useful objects:
- **Spells:** `...SpellComponent`, e.g. `FireballProjectileSpellComponent`, `BlizzardThrowableSpellComponent`. Properties: `BasePower`, `MaxStacks`, `RestoreStackTime`, `ProjectileSpeed`, `BaseElement` (0 Fire, 1 Ice, 2 Life, 3 Death, 4 Lightning, 5 Steam).
- **Staves:** passive in `<Class>Variant<N>StaffUpgradeFeatureComponent` (`AffectFactor1`, `ConditionalChance1`...) and damage in `...StaffWeaponComponent` (`StaffDamage`). See the table at the end to know which components a staff uses.
- **Levels:** `CharacterUpgradeManager` (`ExperienceToUpgrade`, `ExperienceCapNormal`, `ExperienceCapHardcore`). `python tools/xptable.py 100` computes the XP cap for a given max level.

You can only change what the object **defines**. If `props` doesn't list a property, it
comes from the parent type and must be changed there. Spell descriptions (tooltips) are
updated automatically; staff descriptions are fixed text and need to go in `text`.

### text

```json
"text": {
  "en": { "menu/spells:namefireball": "Small Fireball+" },    <- English only
  "*":  { "menu/items:ApprenticeStaff": "Cornelius's Staff+" } <- every language
}
```

The key is `file:key`. Most used files:
- `menu/spells`: spells. `name<spell>` and `description<spell>`; the internal name comes from `SpellName` (`fireball`).
- `menu/items`: staves. The key is the object name (`ApprenticeStaff`), and the bonus is in `stats<object>`.
- `menu/mainmenu/ninemenu`: main menu.

Languages: de en es fi fr it ja ru zh. To see every text, extract the originals with
`python modloader.py extract script1.fbq texts menu/spells` and look for the keys.

### scripts

See `example.lua`: it shows logging, mod values inside the code (`{{stat:...}}`),
variables that last between levels and a task repeated every 5 seconds.
The game uses **Lua 5.1**. Game API calls that are known to work:

| Call | What it does |
|---|---|
| `common.CommonUtils.getSelectedLocalPlayerCharacters()` | local player characters |
| `obj:findComponent(Class)` / `obj:findAllComponents(Class)` + `:next()` | find components |
| `getTypeManager():getTypeByUH(c:getType()):getName()` | type name of a component |
| `typeManager:findTypeByName('Name')` | a type from types.bin (changing it affects new instances) |
| `obj:findPropertyIndexByName('Prop')`, `obj:getPropertyValue(i)`, `obj:setPropertyValue(i, v)` | read/write properties |
| `NPModLoader.log(msg)` | write to `log/nineparchments.log` |
| `NPModLoader.every(name, ms, fn)` | repeat `fn` while the scene lasts |

`../live_tweaks/live.lua` is a bigger script you can learn from.

### files/

Any file in `files/<game path>` replaces the original. Example:
`files/data/gui/...`. Extract the original with `extract`, edit it and put it here.

Textures: the game only loads textures listed in its resource list (`resources.bin`). Replacing an existing
texture works, but a texture with a **new** name is not loaded. Reuse an existing name instead.

## Visual or gameplay?

The loader decides by itself:
- **Only texts, UI, textures, sounds:** *visual* mod, goes into `patch90.fbq`. Achievements keep working.
- **Stats, scripts, executable patches or other files:** *gameplay* mod, goes into `modpack.fbq` (needs `-mod=modpack.fbq`). Achievements are **disabled**, and in online co-op everyone needs the same `modpack.fbq`.

## Staves: in-game name → objects

Blink is shared by staves of the same family: changing it affects every staff that uses it.
"(default)" = the staff uses the generic melee attack.

| Staff | Object (name/`text`) | Passive | Blink | Melee damage |
|---|---|---|---|---|
| Carabel's Icicle | `B_IceStaff` | `IceVariant1StaffUpgradeFeatureComponent` | `IceBlinkVariantStaffUpgradeFeatureComponent` | `IceStaffWeaponComponent` |
| Cornelius's Staff | `ApprenticeStaff` | `ApprenticeVariant1StaffUpgradeFeatureComponent` | `ApprenticeBlinkVariantStaffUpgradeFeatureComponent` | `(default)` |
| Gislan's Staff of Verdure | `D_HealerStaff` | `HealerVariant1StaffUpgradeFeatureComponent` | `HealerBlinkVariantStaffUpgradeFeatureComponent` | `HealerNoDgmStaffWeaponComponent` |
| Marvek's Kindling Staff | `C_FireStaff` | `FireVariant1StaffUpgradeFeatureComponent` | `FireBlinkVariantStaffUpgradeFeatureComponent` | `FireStaffWeaponComponent` |
| Nim's Boreal Broom | `G_ShamanStaff_1` | `BroomVariant2StaffUpgradeFeatureComponent` | `BroomBlinkVariantStaffUpgradeFeatureComponent` | `BroomStaffWeaponComponent` |
| Nim's Enchanted Broom | `G_ShamanStaff` | `BroomVariant1StaffUpgradeFeatureComponent` | `BroomBlinkVariantStaffUpgradeFeatureComponent` | `BroomStaffWeaponComponent` |
| Nim's Worn-Out Broom | `G_ShamanStaff_2` | `BroomVariant3StaffUpgradeFeatureComponent` | `BroomBlinkVariantStaffUpgradeFeatureComponent` | `BroomStaffWeaponComponent` |
| Owl's Lightning Rod | `F_ElectricStaff` | `ElectricVariant1StaffUpgradeFeatureComponent` | `ElectricBlinkVariantStaffUpgradeFeatureComponent` | `(default)` |
| Rudolfus's Moon Staff | `E_WarlockStaff` | `WarlockVariant1StaffUpgradeFeatureComponent` | `WarlockBlinkVariantStaffUpgradeFeatureComponent` | `(default)` |
| The Blade of Anastasis | `S_AstralbossStaff` | `ScytheVariant1StaffUpgradeFeatureComponent` | `ScytheBlinkVariantStaffUpgradeFeatureComponent` | `ScytheStaffWeaponComponent` |
| The Copper Rod | `F_ElectricStaff_1` | `ElectricVariant2StaffUpgradeFeatureComponent` | `ElectricBlinkVariantStaffUpgradeFeatureComponent` | `(default)` |
| The Cornflower Staff | `ApprenticeStaff_1` | `ApprenticeVariant2StaffUpgradeFeatureComponent` | `ApprenticeBlinkVariantStaffUpgradeFeatureComponent` | `(default)` |
| The Crescent Staff | `E_WarlockStaff_2` | `WarlockVariant3StaffUpgradeFeatureComponent` | `WarlockBlinkVariantStaffUpgradeFeatureComponent` | `(default)` |
| The Emberlight Staff | `C_FireStaff_2` | `FireVariant3StaffUpgradeFeatureComponent` | `FireBlinkVariantStaffUpgradeFeatureComponent` | `FireStaffWeaponComponent` |
| The Entomaniac's Staff | `AA_InsectStaff` | `InsectVariant1StaffUpgradeFeatureComponent` | `InsectBlinkVariantStaffUpgradeFeatureComponent` | `(default)` |
| The Eventide Icicle | `B_IceStaff_2` | `IceVariant3StaffUpgradeFeatureComponent` | `IceBlinkVariantStaffUpgradeFeatureComponent` | `IceStaffWeaponComponent` |
| The Forester's Staff | `ApprenticeStaff_2` | `ApprenticeVariant3StaffUpgradeFeatureComponent` | `ApprenticeBlinkVariantStaffUpgradeFeatureComponent` | `(default)` |
| The Occultist's Staff | `E_WarlockStaff_1` | `WarlockVariant2StaffUpgradeFeatureComponent` | `WarlockBlinkVariantStaffUpgradeFeatureComponent` | `(default)` |
| The Rimy Icicle | `B_IceStaff_1` | `IceVariant2StaffUpgradeFeatureComponent` | `IceBlinkVariantStaffUpgradeFeatureComponent` | `IceStaffWeaponComponent` |
| The Scythe of Anastasis | `S_AstralbossStaffHC` | `ScytheVariant2StaffUpgradeFeatureComponent` | `ScytheBlinkVariantStaffUpgradeFeatureComponent` | `ScytheStaffHCWeaponComponent` |
| The Searing Staff | `C_FireStaff_1` | `FireVariant2StaffUpgradeFeatureComponent` | `FireBlinkVariantStaffUpgradeFeatureComponent` | `FireStaffFireDmgWeaponComponent` |
| The Staff of Alcyon | `D_HealerStaff_2` | `HealerVariant3StaffUpgradeFeatureComponent` | `HealerBlinkVariantStaffUpgradeFeatureComponent` | `(default)` |
| The Staff of Quackening | `AA_DuckStaff` | `DuckStaffVariant1UpgradeFeatureComponent` | `DuckStaffBlinkVariantUpgradeFeatureComponent` | `(default)` |
| The Staff of Serenity | `D_HealerStaff_1` | `HealerVariant2StaffUpgradeFeatureComponent` | `HealerBlinkVariantStaffUpgradeFeatureComponent` | `(default)` |
| The Wolfram Rod | `F_ElectricStaff_2` | `ElectricVariant3StaffUpgradeFeatureComponent` | `ElectricBlinkVariantStaffUpgradeFeatureComponent` | `(default)` |
