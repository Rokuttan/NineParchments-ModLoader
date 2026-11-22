#!/usr/bin/env python3
"""Nine Parchments mod manager.

Each mod is a folder in ./mods with a mod.json file (see mods/example_mod/README.md).
The loader merges every active mod, in the order of load_order.txt.

Default (co-op mode): everything goes into patch90.fbq, which the game loads by itself.
                -> no launch option needed, works in online co-op
                -> every player must install the SAME patch90.fbq
                -> achievements are not disabled
With "build --modpack" (classic mode) it builds up to two packages:
  modpack.fbq   GAMEPLAY mods (stats, scripts, missions...).
                Loaded with the launch option  -mod=modpack.fbq
                -> achievements DISABLED (modAchievementsEnabled = false)
                -> online co-op only with players who have the SAME modpack.fbq
  patch90.fbq   VISUAL / client-side mods (text, UI, textures, audio, shaders).

Commands:
  modloader.py list                 lists the mods, their category and conflicts
  modloader.py build                builds patch90.fbq in ./build/modloader (co-op mode, the default)
  modloader.py build --modpack      classic mode: gameplay mods go into modpack.fbq (needs -mod=modpack.fbq)
  modloader.py install [--yes]      installs the built packages into the game folder
  modloader.py uninstall            removes everything the loader installed
  modloader.py status
  modloader.py new NAME             creates mods/NAME/mod.json for you to fill in
  modloader.py search TEXT          searches game objects (spells, staves...) by name
  modloader.py props OBJECT         shows the values an object defines (what you can change)
  modloader.py extract PACKAGE.fbq FOLDER [filter]   extracts original game files
  modloader.py live set Object.Prop VALUE   changes a value while the game runs (live_tweaks mod); VALUE accepts *1.5 and +10
  modloader.py live unset Object.Prop       restores the original value
  modloader.py live clear | show | dump     clears all / shows file and result / lists the player's spells
"""
import hashlib
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'tools'))
from fbq import Package, write_package  # noqa: E402
from typedb import TypeDB  # noqa: E402
from luachunk import Chunk  # noqa: E402
import locale_regen  # noqa: E402

VERSION = '1.4'
GAME_EXE = 'nineparchments_64bit.exe'


def find_game():
    """Game folder: NINE_PARCHMENTS_DIR environment variable, the loader's own folder, or its parent
    (the normal setup: the NPModLoader folder inside the game folder)."""
    env = os.environ.get('NINE_PARCHMENTS_DIR')
    if env:
        return env
    for d in (HERE, os.path.dirname(HERE)):
        if os.path.isfile(os.path.join(d, GAME_EXE)) and os.path.isfile(os.path.join(d, 'script1.fbq')):
            return d
    # default Steam install locations (Flatpak / native on Linux, Windows)
    for d in ('~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/Nine Parchments',
              '~/.local/share/Steam/steamapps/common/Nine Parchments',
              r'C:\Program Files (x86)\Steam\steamapps\common\Nine Parchments'):
        d = os.path.expanduser(d)
        if os.path.isfile(os.path.join(d, GAME_EXE)):
            return d
    return None


GAME = find_game() or ''
MODS = os.path.join(HERE, 'mods')
ORDER_FILE = os.path.join(HERE, 'load_order.txt')
OUT = os.path.join(HERE, 'build', 'modloader')
MANIFEST = os.path.join(OUT, 'installed.json')

COOP_INFO = '''
CO-OP MODE (default): everything went into patch90.fbq, which the game loads by itself.
  • No launch option is needed. If  -mod=modpack.fbq  is in the Steam launch options, REMOVE it.
  • EVERY player must install the SAME patch90.fbq (copy the build/modloader folder
    or the patch90.fbq file into each player's game folder). If only one player has the mod,
    values differ between the computers and the game may desync.
  • The game does not compare patch90.fbq between players: nobody is warned if they differ.
  • To play without mods: modloader.py uninstall.
'''

MODPACK = 'modpack.fbq'
CLIENT_PATCH = 'patch90.fbq'
TYPEDB_PATH = 'types.bin'
MOD_SETTINGS = ['data/script/misc/mod_settings.lub', 'data/script/misc/mod_settings.x64.lub']
MOD_VERSION_FILE = 'data/version/mod_version_1.1.0.ver'
LANGS = ['de', 'en', 'es', 'fi', 'fr', 'it', 'ja', 'ru', 'zh']

# Files that only change presentation on the local player's computer.
CLIENT_PREFIXES = ('data/locale/', 'data/gui/', 'data/audio/', 'data/shader/')
CLIENT_EXACT = ('data/particles.bin',)
CLIENT_EXTS = ('.fbi', '.fbatex')   # textures

GAMEPLAY = 'gameplay'
CLIENT = 'visual/client'

# ---------------------------------------------------------------------------------------------
# Achievement warning
# ---------------------------------------------------------------------------------------------

WARNING_CLI = """
╔══════════════════════════════════════════════════════════════════════════╗
║  WARNING: mods that change gameplay are active                           ║
║                                                                          ║
║  While the game is started with  -mod=modpack.fbq :                      ║
║   • Steam ACHIEVEMENTS are DISABLED (none will unlock);                  ║
║   • online co-op only works with players who have exactly the same       ║
║     modpack.fbq (same mods, same order, same versions).                  ║
║                                                                          ║
║  To go back to normal, remove  -mod=modpack.fbq  from the Steam          ║
║  launch options (or run  modloader.py uninstall).                        ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

# Texts shown inside the game (main menu) when gameplay mods are active.
# itemAchievements = menu item; titleAchievementsMenu = achievements screen title;
# infoStartGame = notice shown when starting a new game (the sentence is appended to it).
WARNING_GAME = {
    'en': ('Achievements (disabled: mods)', 'Achievements - disabled by gameplay mods',
           'Gameplay mods are active: achievements are disabled.'),
    'de': ('Erfolge (deaktiviert: Mods)', 'Erfolge - durch Gameplay-Mods deaktiviert',
           'Gameplay-Mods sind aktiv: Erfolge sind deaktiviert.'),
    'es': ('Logros (desactivados: mods)', 'Logros - desactivados por mods de jugabilidad',
           'Hay mods de jugabilidad activos: los logros están desactivados.'),
    'fr': ('Succès (désactivés : mods)', 'Succès - désactivés par des mods de gameplay',
           'Des mods de gameplay sont actifs : les succès sont désactivés.'),
    'it': ('Obiettivi (disattivati: mod)', 'Obiettivi - disattivati dalle mod di gioco',
           'Mod di gioco attive: gli obiettivi sono disattivati.'),
    'fi': ('Saavutukset (pois käytöstä: modit)', 'Saavutukset - pois käytöstä pelimodien vuoksi',
           'Pelimodit ovat käytössä: saavutukset on poistettu käytöstä.'),
    'ru': ('Достижения (отключены: моды)', 'Достижения - отключены модами геймплея',
           'Активны моды геймплея: достижения отключены.'),
    'ja': ('実績（MODにより無効）', '実績 - ゲームプレイMODにより無効', 'ゲームプレイMODが有効です：実績は無効になります。'),
    'zh': ('成就（已因模组禁用）', '成就 - 已因玩法模组禁用', '玩法模组已启用：成就已禁用。'),
}
WARNING_FILE = 'menu/mainmenu/ninemenu'

# Scripts: the loader appends to scene_loaded_never_skipped.lua (run on every scene load, including
# when continuing a save) a call to pcall(loadstring(BOOTSTRAP + the mods' scripts)).
SCENE_HOOK = ['data/script/gameplay/scene_loaded_never_skipped.lub', 'data/script/gameplay/scene_loaded_never_skipped.x64.lub']
BOOTSTRAP = r'''-- generated by NPModLoader (Nine Parchments)
NPModLoader = NPModLoader or { gen = 0, tasks = {} }
NPModLoader.gen = NPModLoader.gen + 1
function NPModLoader.log(msg)
  if logger then logger:info('[modloader] ' .. tostring(msg)) end
end
-- Runs fn every ms milliseconds for as long as the current scene lasts.
function NPModLoader.every(name, ms, fn)
  NPModLoader.tasks[name] = { fn = fn, ms = ms, gen = NPModLoader.gen, errors = 0 }
  NPModLoader_run(name, NPModLoader.gen)
end
function NPModLoader_run(name, gen)
  local t = NPModLoader.tasks[name]
  if t == nil or t.gen ~= gen or gen ~= NPModLoader.gen then return end
  local ok, err = pcall(t.fn)
  if not ok then
    t.errors = t.errors + 1
    if t.errors <= 5 then NPModLoader.log('error in ' .. name .. ': ' .. tostring(err)) end
  end
  state:runLuaStringWithDelay('NPModLoader_run("' .. name .. '",' .. gen .. ')', t.ms)
end
if NPModLoader.gen == 1 then NPModLoader.log('active: %(mods)s') end
-- heartbeat: confirms the hook ran and that io works in the game folder
pcall(function()
  local f = io.open('np_modloader.txt', 'w')
  if f then f:write('modloader active, scene ' .. NPModLoader.gen .. ': %(mods)s\n'); f:close() end
end)
'''


# ---------------------------------------------------------------------------------------------
# Reading mods
# ---------------------------------------------------------------------------------------------

class Mod:
    def __init__(self, folder):
        self.id = os.path.basename(folder)
        self.dir = folder
        with open(os.path.join(folder, 'mod.json'), encoding='utf-8') as f:
            m = json.load(f)
        self.name = m.get('name', self.id)
        self.version = str(m.get('version', '1.0'))
        self.author = m.get('author', '')
        self.description = m.get('description', '')
        self.enabled = m.get('enabled', True)
        self.stats = m.get('stats', {})          # {Object: {Property: value | "*1.5" | "+10"}}
        self.text = m.get('text', {})            # {lang|"*": {"key" | "file:key": text}}
        self.scripts = []                        # Lua scripts run on every scene load
        self.exe_patches = m.get('exe_patches', [])   # [{va, original, patched, note}] in the game executable
        for sc in m.get('scripts', []):
            path = os.path.join(folder, sc)
            if not os.path.isfile(path):
                raise SystemExit(f'[{self.id}] script not found: {sc}')
            self.scripts.append(path)
        self.files = {}                          # path in the game -> file on disk
        fdir = os.path.join(folder, 'files')
        for dp, dn, fn in os.walk(fdir):
            dn.sort()
            for n in sorted(fn):
                full = os.path.join(dp, n)
                if dp == fdir and n.upper() in ('README.TXT', 'README.MD', 'LEIA-ME.TXT'):
                    continue  # instructions, not game files
                self.files[os.path.relpath(full, fdir).replace(os.sep, '/')] = full

    def gameplay_reasons(self):
        r = []
        if self.stats:
            r.append(f'changes stats ({sum(len(v) for v in self.stats.values())} values)')
        if self.scripts:
            r.append(f'runs {len(self.scripts)} Lua script(s) during the game')
        for path in self.files:
            if not is_client_path(path):
                r.append(f'replaces {path}')
        if self.exe_patches:
            r.append(f'patches the game executable ({len(self.exe_patches)} span(s))')
        return r

    @property
    def category(self):
        return GAMEPLAY if self.gameplay_reasons() else CLIENT


def is_client_path(path):
    return (path.startswith(CLIENT_PREFIXES) or path in CLIENT_EXACT
            or (path.startswith('data/root/') and path.endswith(CLIENT_EXTS)))


def discover():
    mods = {}
    if os.path.isdir(MODS):
        for n in sorted(os.listdir(MODS)):
            if os.path.isfile(os.path.join(MODS, n, 'mod.json')):
                mods[n] = Mod(os.path.join(MODS, n))
    order, commented = [], set()
    if os.path.exists(ORDER_FILE):
        for line in open(ORDER_FILE, encoding='utf-8'):
            raw = line.strip()
            if raw.startswith('#'):
                name = raw.lstrip('#').strip()
                if name in mods:
                    commented.add(name)
                continue
            line = raw.split('#', 1)[0].strip()
            if line and line in mods and line not in order:
                order.append(line)
    new = [m for m in mods if m not in order and m not in commented]
    if new or not os.path.exists(ORDER_FILE):
        order += new
        with open(ORDER_FILE, 'w', encoding='utf-8') as f:
            f.write('# Load order: mods further down win conflicts.\n')
            f.write('# To disable a mod, comment its line out with # or set "enabled": false in its mod.json.\n')
            for n in order:
                f.write(n + '\n')
    disabled = [m for m in mods if m not in order]
    active = [mods[n] for n in order if mods[n].enabled]
    return active, [mods[n] for n in mods if not mods[n].enabled or n in disabled]


# ---------------------------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------------------------

def apply_value(old, spec):
    if isinstance(spec, (int, float)):
        return float(spec)
    s = str(spec).strip()
    if s[:1] in '*x':
        return old * float(s[1:])
    if s[:1] in '+-':
        return old + float(s)
    return float(s)


class Builder:
    def __init__(self, mods, log=print, coop=False):
        self.mods = mods
        self.coop = coop    # True: everything goes into patch90.fbq (no -mod=), for online co-op
        self.log = log
        self.errors = []
        self.warnings = []
        self.script = Package(os.path.join(GAME, 'script1.fbq'))
        self._lang_index = {}

    # --- texts ----------------------------------------------------------------------------
    def locale_files(self, lang):
        """{'menu/spells': [.lub/.x64.lub paths in gui and autogenerated]}"""
        if lang not in self._lang_index:
            idx = {}
            for e in self.script.entries:
                for base in ('data/locale/gui/', 'data/locale/autogenerated/gui/'):
                    pre = base + lang + '/'
                    if e.name.startswith(pre) and e.name.endswith('.lub'):
                        rel = e.name[len(pre):]
                        rel = rel[:-8] if rel.endswith('.x64.lub') else rel[:-4]
                        idx.setdefault(rel, []).append(e.name)
            self._lang_index[lang] = idx
        return self._lang_index[lang]

    def find_key(self, lang, key, texts):
        """Returns the list of files (all variants) that define the key."""
        if ':' in key:
            rel, key = key.split(':', 1)
            files = self.locale_files(lang).get(rel)
            if not files:
                raise KeyError(f'locale file {lang}/{rel} does not exist')
            return key, files
        hits = []
        for rel, files in self.locale_files(lang).items():
            c = self.chunk(files[0], texts)
            if key in c.globals_table():
                hits.append((rel, files))
        if not hits:
            raise KeyError(f'key {key!r} does not exist in {lang}')
        if len(hits) > 1:
            raise KeyError(f'key {key!r} exists in several {lang} files '
                           f'({", ".join(h[0] for h in hits)}); use "file:key"')
        return key, hits[0][1]

    def chunk(self, name, texts):
        data = texts.get(name)
        if data is None:
            data = self.script.read(self.script.find(name))
        return Chunk(data)

    def set_text(self, texts, files, key, value, resolver=None):
        for name in files:
            c = self.chunk(name, texts)
            v = value
            if resolver and '/autogenerated/' in name:
                v = resolve_placeholders(value, resolver)
            if c.set_global_string(key, v.encode('utf-8')):
                texts[name] = c.dump()

    # --- main build -----------------------------------------------------------------------
    def build(self):
        gameplay = [m for m in self.mods if m.category == GAMEPLAY]
        client = [m for m in self.mods if m.category != GAMEPLAY]
        pack_files = {}     # name in the game -> (bytes, mod that provided it)
        patch_files = {}
        if self.coop:
            pack_files = patch_files    # co-op mode: a single package, loaded as patch90.fbq
        as_pack = bool(gameplay) and not self.coop
        owner = {}

        # 1) replacement files
        for m in self.mods:
            for path, src in m.files.items():
                if path in owner:
                    self.warnings.append(f'conflict: {path} comes from "{owner[path]}" and "{m.id}"; "{m.id}" wins')
                owner[path] = m.id
                data = open(src, 'rb').read()
                (patch_files if is_client_path(path) else pack_files)[path] = (data, m.id)

        # 2) stats
        mpk = Package(os.path.join(GAME, 'mission1.fbq'))
        raw = pack_files.pop(TYPEDB_PATH, (None,))[0] or mpk.read(mpk.find(TYPEDB_PATH))
        db_old, db = TypeDB(mpk.read(mpk.find(TYPEDB_PATH))), TypeDB(raw)
        stat_owner = {}
        changed = 0
        for m in gameplay:
            for obj, props in m.stats.items():
                for prop, spec in props.items():
                    k = f'{obj}.{prop}'
                    try:
                        old = db.get(obj, prop)
                        if not isinstance(old, (int, float)):
                            raise TypeError(f'{k} is not numeric')
                        new = apply_value(old, spec)
                        db.set(obj, prop, new)
                    except (KeyError, TypeError, ValueError) as ex:
                        self.errors.append(f'[{m.id}] {k}: {ex}')
                        continue
                    if k in stat_owner:
                        self.warnings.append(f'conflict: {k} changed by "{stat_owner[k]}" and "{m.id}"; applied in sequence')
                    stat_owner[k] = m.id
                    changed += 1
                    self.log(f'  [{m.id}] {k}: {old:.7g} -> {db.get(obj, prop):.7g}')

        # 3) texts: tooltips regenerated from the new values, then the mods' own texts
        texts = {}
        regen_log = []
        if changed:
            texts.update(locale_regen.regen_all(self.script, db_old, db, log=regen_log))
            self.log(f'  {len(regen_log)} description snippets updated with the new values')
        resolver = locale_regen.Resolver(db)
        text_owner = {}
        for m in self.mods:
            for lang_spec, entries in m.text.items():
                langs = LANGS if lang_spec == '*' else [lang_spec]
                for lang in langs:
                    for key, value in entries.items():
                        try:
                            k, files = self.find_key(lang, key, texts)
                        except KeyError as ex:
                            if lang_spec == '*':
                                continue
                            self.errors.append(f'[{m.id}] text: {ex}')
                            continue
                        tk = f'{lang}:{k}'
                        if tk in text_owner and text_owner[tk] != m.id:
                            self.warnings.append(f'conflict: text {tk} from "{text_owner[tk]}" and "{m.id}"; "{m.id}" wins')
                        text_owner[tk] = m.id
                        self.set_text(texts, files, k, value, resolver)

        # 4) in-game achievement notice (only with -mod=; patchNN.fbq never disables achievements)
        if as_pack:
            for lang, (item, title, info) in WARNING_GAME.items():
                files = self.locale_files(lang).get(WARNING_FILE, [])
                for key, val in (('itemAchievements', item), ('titleAchievementsMenu', title)):
                    self.set_text(texts, files, key, val)
                for name in files:
                    c = self.chunk(name, texts)
                    g = c.globals_table()
                    if 'infoStartGame' in g:
                        base = c.main.constants[g['infoStartGame']][1].decode('utf-8')
                        c.set_global_string('infoStartGame', f'{base}<br>{info}'.encode('utf-8'))
                        texts[name] = c.dump()

        # 5) distribute: texts go to the client package, unless there are gameplay mods
        #    (then they go to the modpack, which has priority, so the patch can't override them).
        text_target = pack_files if as_pack else patch_files
        for name, data in texts.items():
            text_target[name] = (data, 'loader')

        # 6) Lua scripts
        scripted = [m for m in self.mods if m.scripts]
        if scripted:
            src = self.bootstrap(scripted, db)
            if src is not None:
                for name in SCENE_HOOK:
                    c = Chunk(self.script.read(self.script.find(name)))
                    c.append_loadstring_call(src.encode('utf-8'))
                    pack_files[name] = (c.dump(), 'loader')
                self.log(f'  scripts: {", ".join(m.id for m in scripted)} (hooked into scene_loaded_never_skipped.lua)')

        exe_patches = collect_exe_patches(self.mods, self.errors)
        if exe_patches:
            self.log(f'  executable: {len(exe_patches)} span(s) will be patched on install')

        if self.errors:
            return {}, gameplay   # never build half a package

        outputs = {}
        os.makedirs(OUT, exist_ok=True)
        if self.coop:
            if changed or TYPEDB_PATH in owner:
                patch_files[TYPEDB_PATH] = (bytes(db.d), 'loader')
            if gameplay:
                manifest = {'coop': True, 'mods': [{'id': m.id, 'version': m.version} for m in self.mods]}
                patch_files['data/modloader/modlist.json'] = (
                    json.dumps(manifest, indent=1, sort_keys=True).encode('utf-8'), 'loader')
        elif gameplay:
            if changed or TYPEDB_PATH in owner:
                pack_files[TYPEDB_PATH] = (bytes(db.d), 'loader')
            for name in MOD_SETTINGS:
                c = Chunk(self.script.read(self.script.find(name)))
                if not c.set_global_bool('modAchievementsEnabled', False):
                    raise RuntimeError('mod_settings.lua has an unexpected format')
                pack_files[name] = (c.dump(), 'loader')
            version = open(os.path.join(GAME, 'data/version/current_version.ver'), 'rb').read()
            pack_files[MOD_VERSION_FILE] = (version, 'loader')
            manifest = {'mods': [{'id': m.id, 'version': m.version} for m in self.mods]}
            pack_files['data/modloader/modlist.json'] = (
                json.dumps(manifest, indent=1, sort_keys=True).encode('utf-8'), 'loader')
            outputs[MODPACK] = pack_files
        if patch_files:
            outputs[CLIENT_PATCH] = patch_files

        for stale in (MODPACK, CLIENT_PATCH):
            p = os.path.join(OUT, stale)
            if stale not in outputs and os.path.exists(p):
                os.remove(p)
        result = {}
        for name, files in outputs.items():
            path = os.path.join(OUT, name)
            write_package(path, sorted((k, v[0]) for k, v in files.items()))  # fixed order: same build = same file
            sha = hashlib.sha256(open(path, 'rb').read()).hexdigest()
            result[name] = {'files': len(files), 'sha256': sha}
            self.log(f'  -> {path} ({len(files)} files, SHA-256 {sha[:16]}…)')
        with open(os.path.join(OUT, 'build.json'), 'w') as f:
            json.dump({'outputs': result, 'coop': self.coop, 'gameplay': [m.id for m in gameplay],
                       'client': [m.id for m in client], 'exe_patches': _patches_to_json(exe_patches)},
                      f, indent=2)
        return result, gameplay


def _bootstrap(self, mods, db):
    parts = [BOOTSTRAP % {'mods': ', '.join(m.id for m in mods)}]
    pat = re.compile(r'\{\{stat:([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)\}\}')
    for m in mods:
        for path in m.scripts:
            code = open(path, encoding='utf-8').read()

            def stat(mt):
                try:
                    v = db.get(mt.group(1), mt.group(2))
                    if not isinstance(v, (int, float)):
                        raise TypeError('not numeric')
                    return repr(float(v))
                except (KeyError, TypeError) as ex:
                    self.errors.append(f'[{m.id}] {os.path.basename(path)}: {mt.group(0)}: {ex}')
                    return '0'
            code = pat.sub(stat, code)
            name = f'{m.id}/{os.path.basename(path)}'
            parts.append(f'do -- {name}\n'
                         f'  local ok, err = pcall(function()\n{code}\n  end)\n'
                         f'  if not ok then NPModLoader.log("error starting {name}: " .. tostring(err)) end\n'
                         f'end\n')
    src = '\n'.join(parts)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'bootstrap.lua'), 'w', encoding='utf-8') as f:
        f.write(src)   # copy for inspection
    return src


Builder.bootstrap = _bootstrap


def resolve_placeholders(text, resolver):
    def rep(m):
        expr = m.group(1)
        if not locale_regen.refs_in(expr):
            return m.group(0)
        try:
            v = locale_regen.evaluate(expr, resolver)
        except (KeyError, ValueError):
            return m.group(0)
        return f'{v:.2f}'.rstrip('0').rstrip('.')
    return locale_regen.PLACEHOLDER.sub(rep, text)


# ---------------------------------------------------------------------------------------------
# Executable patches (exe_patches)
# ---------------------------------------------------------------------------------------------

EXE_BACKUP = os.path.join(OUT, 'backup', GAME_EXE + '.original')


def exe_path():
    return os.path.join(GAME, GAME_EXE)


def va_to_offset(data, va):
    """Virtual address (as shown by a disassembler, image base 0x140000000) -> file offset."""
    pe = int.from_bytes(data[0x3c:0x40], 'little')
    nsec = int.from_bytes(data[pe + 6:pe + 8], 'little')
    opt = int.from_bytes(data[pe + 20:pe + 22], 'little')
    base = int.from_bytes(data[pe + 48:pe + 56], 'little')
    for i in range(nsec):
        o = pe + 24 + opt + 40 * i
        vaddr, rsize, rptr = (int.from_bytes(data[o + k:o + k + 4], 'little') for k in (12, 16, 20))
        if base + vaddr <= va < base + vaddr + rsize:
            return va - base - vaddr + rptr
    raise ValueError(f'address {va:#x} is outside the executable')


def collect_exe_patches(mods, errors):
    """Returns [(offset, original, patched, mod)] validated against the current executable."""
    out = []
    if not any(m.exe_patches for m in mods):
        return out
    data = open(exe_path(), 'rb').read()
    # original copy (made on the first install): allows replacing spans of an older mod version
    backup = open(EXE_BACKUP, 'rb').read() if os.path.exists(EXE_BACKUP) else None
    for m in mods:
        for p in m.exe_patches:
            try:
                off = va_to_offset(data, int(str(p['va']), 16))
                orig, new = bytes.fromhex(p['original']), bytes.fromhex(p['patched'])
                if len(orig) != len(new):
                    raise ValueError('original and patched have different lengths')
                cur = data[off:off + len(orig)]
                if cur not in (orig, new) and not (backup and backup[off:off + len(orig)] == orig):
                    raise ValueError('the bytes in the executable are not the expected ones (different game version?)')
            except (KeyError, ValueError) as ex:
                errors.append(f'[{m.id}] exe_patches {p.get("va")}: {ex}')
                continue
            for o2, or2, n2, m2 in out:
                if off < o2 + len(or2) and o2 < off + len(orig):
                    errors.append(f'[{m.id}] exe_patches {p["va"]}: overlaps a span of "{m2}"')
            out.append((off, orig, new, m.id))
    return out


def exe_apply(patches, undo=False):
    """Writes the 'patched' bytes (or the original ones if undo). Returns how many spans changed."""
    if not patches:
        return 0
    path = exe_path()
    data = bytearray(open(path, 'rb').read())
    changed = 0
    for off, orig, new, _ in patches:
        want, other = (orig, new) if undo else (new, orig)
        cur = bytes(data[off:off + len(orig)])
        if cur == want:
            continue
        if cur != other:
            print(f'warning: executable span {off:#x} changed (game update?); left it alone')
            continue
        data[off:off + len(orig)] = want
        changed += 1
    if changed:
        if not undo and not os.path.exists(EXE_BACKUP):
            os.makedirs(os.path.dirname(EXE_BACKUP), exist_ok=True)
            shutil.copyfile(path, EXE_BACKUP)
            print('backup of the original executable:', EXE_BACKUP)
        with open(path + '.tmp', 'wb') as f:
            f.write(data)
        shutil.copymode(path, path + '.tmp')
        os.replace(path + '.tmp', path)
    return changed


def _patches_from_json(lst):
    return [(p['offset'], bytes.fromhex(p['original']), bytes.fromhex(p['patched']), p['mod']) for p in lst]


def _patches_to_json(lst):
    return [{'offset': o, 'original': a.hex(), 'patched': b.hex(), 'mod': m} for o, a, b, m in lst]


# ---------------------------------------------------------------------------------------------
# Installing
# ---------------------------------------------------------------------------------------------

def load_manifest():
    return json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {'files': {}}


def save_manifest(m):
    os.makedirs(OUT, exist_ok=True)
    json.dump(m, open(MANIFEST, 'w'), indent=2)


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def ensure_writable(names):
    """Stops before changing anything if a file is locked (on Windows: the game is running) or read-only."""
    for name in names:
        p = os.path.join(GAME, name)
        if not os.path.exists(p):
            continue
        try:
            open(p, 'r+b').close()
        except OSError:
            raise SystemExit(f'{name} is in use or read-only.\n'
                             'Close the game (and wait for Steam to finish any update or file check), then try again.')


def install(assume_yes):
    info_path = os.path.join(OUT, 'build.json')
    if not os.path.exists(info_path):
        raise SystemExit('run "modloader.py build" first')
    info = json.load(open(info_path))
    man = load_manifest()
    ensure_writable(list(info['outputs']) + list(man['files']) +
                    ([GAME_EXE] if info.get('exe_patches') or man.get('exe') else []))
    if MODPACK in info['outputs']:
        print(WARNING_CLI)
        if not assume_yes:
            ans = input('Type "yes" to install anyway: ').strip().lower()
            if ans not in ('yes', 'y'):
                raise SystemExit('installation cancelled')
    # remove old loader packages that are no longer part of the build
    for name in list(man['files']):
        if name not in info['outputs']:
            remove_installed(name, man)
    for name in info['outputs']:
        src, dst = os.path.join(OUT, name), os.path.join(GAME, name)
        if os.path.exists(dst) and name not in man['files']:
            raise SystemExit(f'{name} already exists in the game folder and was not installed by the loader; not overwriting it')
        if os.path.exists(dst) and sha(dst) != man['files'][name]:
            raise SystemExit(f'{name} in the game folder was modified by something else; not overwriting it')
        shutil.copyfile(src, dst + '.tmp')
        os.replace(dst + '.tmp', dst)
        man['files'][name] = sha(dst)
        print('installed:', dst)
    # executable: undo spans from old builds that are gone, apply the new ones
    new_p = _patches_from_json(info.get('exe_patches', []))
    old_p = [p for p in _patches_from_json(man.get('exe', [])) if p[:3] not in [q[:3] for q in new_p]]
    if old_p:
        print(f'executable: {exe_apply(old_p, undo=True)} old span(s) restored')
    if new_p:
        print(f'executable: {exe_apply(new_p)} span(s) patched ({len(new_p)} in total)')
    man['exe'] = _patches_to_json(new_p)
    save_manifest(man)
    if info.get('coop'):
        print(COOP_INFO)
    elif MODPACK in info['outputs']:
        print('\nIn Steam: Nine Parchments > Properties > Launch Options:\n'
              f'    Windows:          -mod={MODPACK}\n'
              f'    Linux (Proton):   %command% -mod={MODPACK}\n')
    else:
        print('\nOnly visual mods: no launch option is needed. '
              'If "-mod=modpack.fbq" is in your Steam launch options, remove it.')


def remove_installed(name, man):
    p = os.path.join(GAME, name)
    if os.path.exists(p):
        if sha(p) != man['files'][name]:
            print(f'warning: {name} was modified outside the loader; left in place')
        else:
            os.remove(p)
            print('removed:', p)
    del man['files'][name]


def uninstall():
    man = load_manifest()
    ensure_writable(list(man['files']) + ([GAME_EXE] if man.get('exe') else []))
    for name in list(man['files']):
        remove_installed(name, man)
    if man.get('exe'):
        n = exe_apply(_patches_from_json(man['exe']), undo=True)
        print(f'executable: {n} span(s) restored to the original')
        man['exe'] = []
    save_manifest(man)
    print('Remember to remove "-mod=modpack.fbq" from the Steam launch options, if it is there.')


TEMPLATE = {
    'name': 'My mod',
    'version': '1.0',
    'author': '',
    'description': 'Describe what the mod does here.',
    'enabled': True,
    'stats': {},
    'text': {},
}


def cmd_new(a):
    if len(a) < 3 or not re.fullmatch(r'[A-Za-z0-9_\-]+', a[2]):
        print('usage: modloader.py new FOLDER_NAME   (letters, digits, _ or -)')
        return 2
    d = os.path.join(MODS, a[2])
    if os.path.exists(d):
        print('already exists:', d)
        return 1
    os.makedirs(d)
    with open(os.path.join(d, 'mod.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(TEMPLATE, name=a[2]), f, ensure_ascii=False, indent=2)
        f.write('\n')
    discover()  # adds it to load_order.txt
    print('created:', os.path.join(d, 'mod.json'))
    print('See mods/example_mod/README.md for what goes into "stats", "text", "files" and "scripts".')
    return 0


def _game_types():
    mpk = Package(os.path.join(GAME, 'mission1.fbq'))
    return TypeDB(mpk.read(mpk.find(TYPEDB_PATH)))


def cmd_search(a):
    if len(a) < 3:
        print('usage: modloader.py search TEXT'); return 2
    db = _game_types()
    hits = sorted(n for n in db.object_names() if a[2].lower() in n.lower())
    for n in hits[:300]:
        print(n)
    print(f'-- {len(hits)} object(s)' + (' (showing 300)' if len(hits) > 300 else ''))
    return 0


def cmd_props(a):
    if len(a) < 3:
        print('usage: modloader.py props OBJECT'); return 2
    db = _game_types()
    try:
        props = db.numeric_props(a[2])
    except KeyError as ex:
        print(ex, '- use "search" to find the right name'); return 1
    if not props:
        print('(this object defines no numeric properties; its values come from the parent type)')
    for k, v in props.items():
        print(f'  "{k}": {v:.7g}')
    return 0


def cmd_extract(a):
    if len(a) < 4:
        print('usage: modloader.py extract PACKAGE.fbq OUTPUT_FOLDER [part of the path]'); return 2
    src = a[2] if os.path.isabs(a[2]) else os.path.join(GAME, a[2])
    pkg = Package(src)
    flt = a[4].lower() if len(a) > 4 else ''
    n = 0
    for e in pkg.entries:
        if flt and flt not in e.name.lower():
            continue
        dst = os.path.join(a[3], *e.name.split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as f:
            f.write(pkg.read(e))
        n += 1
    print(f'{n} file(s) extracted to {a[3]}')
    return 0


def cmd_list():
    active, inactive = discover()
    if not active and not inactive:
        print('no mods in', MODS)
    for m in active:
        print(f'[active]   {m.id}  —  {m.name} v{m.version}  ({m.category})')
        for r in m.gameplay_reasons()[:5]:
            print('             ·', r)
    for m in inactive:
        print(f'[inactive] {m.id}  —  {m.name} v{m.version}')
    if any(m.category == GAMEPLAY for m in active):
        print('\nGameplay mods are active: in online co-op every player needs the same patch90.fbq'
              ' (or the same modpack.fbq with "build --modpack").')


def status():
    man = load_manifest()
    if man.get('exe'):
        data = open(exe_path(), 'rb').read()
        ok = sum(data[o:o + len(a)] == b for o, a, b, _ in _patches_from_json(man['exe']))
        print(f'{GAME_EXE}: {ok}/{len(man["exe"])} spans patched ' + ('ok' if ok == len(man['exe']) else
              '(run install again: Steam probably restored the file)'))
    if not man['files'] and not man.get('exe'):
        print('nothing installed')
    for name, h in man['files'].items():
        p = os.path.join(GAME, name)
        st = 'ok' if os.path.exists(p) and sha(p) == h else ('MISSING' if not os.path.exists(p) else 'MODIFIED')
        print(f'{name}: {st}')


LIVE_FILE, LIVE_STATUS, LIVE_DUMP = 'np_live.txt', 'np_live_status.txt', 'np_live_dump.txt'


def _live_lines():
    p = os.path.join(GAME, LIVE_FILE)
    return open(p, encoding='utf-8').read().splitlines() if os.path.exists(p) else []


def _live_write(lines):
    with open(os.path.join(GAME, LIVE_FILE), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + ('\n' if lines else ''))


def _live_show(wait=0):
    import time
    st = os.path.join(GAME, LIVE_STATUS)
    before = os.path.getmtime(st) if os.path.exists(st) else 0
    end = time.time() + wait
    while wait and time.time() < end and (not os.path.exists(st) or os.path.getmtime(st) == before):
        time.sleep(0.2)
    print('--', LIVE_FILE); print('\n'.join(_live_lines()) or '(empty)')
    if os.path.exists(st) and os.path.getmtime(st) != before or not wait:
        print('--', LIVE_STATUS, '(reply from the game)')
        print(open(st, encoding='utf-8').read().rstrip() if os.path.exists(st) else '(the game has not replied yet)')
    else:
        print(f'-- the game did not reply within {wait:g}s (is it running, inside a level, with the live_tweaks mod installed?)')


def _live_installed():
    """True/False whether an installed package (modpack.fbq or patch90.fbq) contains the live script;
    None if neither exists."""
    found = None
    for name in (MODPACK, CLIENT_PATCH):
        r = _live_in(os.path.join(GAME, name))
        if r:
            return True
        if r is False:
            found = False
    return found


def _live_in(path):
    if not os.path.exists(path):
        return None
    try:
        p = Package(path)
        e = p.find('data/script/gameplay/scene_loaded_never_skipped.x64.lub')
        if not e:
            return False
        return any(t == 4 and v and b'NPLive' in v for t, v in Chunk(p.read(e)).main.constants)
    except Exception:
        return None


def cmd_live(a):
    if len(a) < 3:
        print(__doc__); return 2
    inst = _live_installed()
    if not inst:
        print('WARNING: the mod packages installed in the game ' + ('do not exist' if inst is None else 'do not contain the live_tweaks mod') +
              '.\n         Enable it in its mod.json, then run "python3 modloader.py build" and "install".')
    sub = a[2]
    lines = [l for l in _live_lines() if l.strip()]
    if sub in ('set', 'unset'):
        if len(a) < 4 + (sub == 'set') or a[3].count('.') != 1:
            print('usage: live set Object.Property VALUE'); return 2
        key = a[3]
        obj, prop = key.split('.')
        if sub == 'set':
            val = a[4]
            try:
                float(val.lstrip('*+'))
            except ValueError:
                print('invalid value:', val); return 2
            try:  # check against the original types.bin to catch typos
                from typedb import TypeDB
                mpk = Package(os.path.join(GAME, 'mission1.fbq'))
                db = TypeDB(mpk.read(mpk.find(TYPEDB_PATH)))
                print(f'{key}: original value in types.bin = {db.get(obj, prop)}')
            except KeyError as ex:
                print('warning:', ex, '(the game may still accept it if the property is inherited)')
        lines = [l for l in lines if not re.match(r'\s*' + re.escape(key) + r'\s*=', l)]
        if sub == 'set':
            lines.append(f'{key} = {val}')
        _live_write(lines)
        _live_show(wait=3)
    elif sub == 'clear':
        _live_write([]); _live_show(wait=3)
    elif sub == 'dump':
        _live_write(lines + ['!dump']); _live_show(wait=3)
        _live_write(lines)
        d = os.path.join(GAME, LIVE_DUMP)
        if os.path.exists(d):
            print('--', LIVE_DUMP); print(open(d, encoding='utf-8').read().rstrip())
    elif sub == 'show':
        _live_show()
    else:
        print(__doc__); return 2
    return 0


def main(a):
    for stream in (sys.stdout, sys.stderr):
        try:  # Windows consoles without UTF-8 must not crash on box-drawing characters
            stream.reconfigure(errors='replace')
        except AttributeError:
            pass
    if len(a) < 2:
        print(__doc__)
        return 2
    cmd = a[1]
    if cmd in ('new', 'novo'):
        return cmd_new(a)
    if not GAME:
        print('Could not find Nine Parchments.\n'
              'Put the NPModLoader folder INSIDE the game folder (where nineparchments_64bit.exe is),\n'
              'or set the NINE_PARCHMENTS_DIR environment variable to the game path.')
        return 1
    if cmd == 'list':
        cmd_list()
    elif cmd == 'build':
        active, _ = discover()
        if not active:
            print('no active mods')
            return 1
        coop = '--modpack' not in a     # co-op mode is the default; "--coop" is still accepted
        b = Builder(active, coop=coop)
        print(f'building {len(active)} mod(s)' + (' in co-op mode (everything in patch90.fbq)' if coop else ' in classic mode (modpack.fbq)') + '...')
        result, gameplay = b.build()
        for w in b.warnings:
            print('WARNING:', w)
        for e in b.errors:
            print('ERROR:', e)
        if b.errors:
            print('\nNo package was built: fix the errors above.')
            return 1
        if coop:
            print(COOP_INFO)
        elif gameplay:
            print(WARNING_CLI)
        return 0
    elif cmd == 'install':
        install('--yes' in a)
    elif cmd == 'uninstall':
        uninstall()
    elif cmd == 'status':
        status()
    elif cmd in ('extract', 'extrair'):
        return cmd_extract(a)
    elif cmd in ('search', 'buscar'):
        return cmd_search(a)
    elif cmd == 'props':
        return cmd_props(a)
    elif cmd == 'live':
        return cmd_live(a)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    if sys.version_info < (3, 8):
        sys.exit('NPModLoader needs Python 3.8 or newer (this is %d.%d).' % sys.version_info[:2])
    sys.exit(main(sys.argv))
