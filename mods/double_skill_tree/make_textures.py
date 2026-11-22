#!/usr/bin/env python3
"""Generates the 5 purple bar layers used by the double_skill_tree mod for trees that are already purple.

Run it once, from anywhere, before "modloader.py build":

    python mods/double_skill_tree/make_textures.py

It reads the game's own skill bar textures from gui1.fbq (no game files are shipped with the mod),
makes a more vivid purple version of skill_icon_progress_violet01..05 and writes them to
files/data/gui/menu/skilltree/ inside this mod.

Why these file names: the game only loads textures listed in its resource list, so new names are
ignored. The layers take the place of the 3-point perk bar textures (skill_icon_progress3_*), which
exist in the game but are never used because no perk has 3 points. The executable patch asks for:
    k = 1..3 -> skill_icon_progress3_violet0k      k = 4..5 -> skill_icon_progress3_blue0(k-3)
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOADER = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(LOADER, 'tools'))
from fbq import Package, lz4_block_decompress  # noqa: E402

DIR = 'data/gui/menu/skilltree/'
HDR = 41                       # .fbi header size
OUT_NAMES = ['progress3_violet01', 'progress3_violet02', 'progress3_violet03',
             'progress3_blue01', 'progress3_blue02']


def find_game():
    env = os.environ.get('NINE_PARCHMENTS_DIR')
    for d in ([env] if env else []) + [os.path.dirname(LOADER)]:
        if d and os.path.exists(os.path.join(d, 'gui1.fbq')):
            return d
    raise SystemExit('Could not find gui1.fbq. Put NPModLoader inside the game folder '
                     '(or set NINE_PARCHMENTS_DIR to the game path).')


def c565(c):
    r, g, b = (c >> 11) & 31, (c >> 5) & 63, c & 31
    return (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2)


def e565(rgb):
    r, g, b = (max(0, min(255, int(x))) for x in rgb)
    return ((r * 31 + 127) // 255) << 11 | ((g * 63 + 127) // 255) << 5 | ((b * 31 + 127) // 255)


def vivid_block(blk):
    """BC2 block: 8 bytes of alpha + DXT1 color block. Recolors only the two color endpoints."""
    c0, c1, idx = struct.unpack_from('<HHI', blk, 8)

    def tr(c):
        r, g, b = c565(c)
        return e565((r * 1.25, g * 0.45, b * 1.7))
    n0, n1 = tr(c0), tr(c1)
    if (c0 > c1) != (n0 > n1) and n0 != n1:   # keep the 4-color mode: swap endpoints and indices
        n0, n1 = n1, n0
        idx ^= 0x55555555
    return blk[:8] + struct.pack('<HHI', n0, n1, idx)


def write_fbi(header, raw):
    """Stores the texture as a literal-only LZ4 block (valid LZ4, just not compressed)."""
    lz = bytearray()
    n = len(raw)
    lz.append(min(n, 15) << 4)
    if n >= 15:
        r = n - 15
        while r >= 255:
            lz.append(255)
            r -= 255
        lz.append(r)
    lz += raw
    h = bytearray(header)
    struct.pack_into('<II', h, 0x21, len(lz), len(raw))
    return bytes(h) + bytes(lz)


def main():
    game = find_game()
    pkg = Package(os.path.join(game, 'gui1.fbq'))
    out_dir = os.path.join(HERE, 'files', DIR)
    os.makedirs(out_dir, exist_ok=True)
    for k, name in enumerate(OUT_NAMES, 1):
        e = pkg.find(f'{DIR}skill_icon_progress_violet0{k}.fbi')
        if e is None:
            raise SystemExit(f'skill_icon_progress_violet0{k}.fbi not found in gui1.fbq (different game version?)')
        b = pkg.read(e)
        csize, usize = struct.unpack_from('<II', b, 0x21)
        raw = lz4_block_decompress(b[HDR:HDR + csize], usize)
        raw = b''.join(vivid_block(raw[i:i + 16]) for i in range(0, len(raw), 16))
        with open(os.path.join(out_dir, f'skill_icon_{name}.fbi'), 'wb') as f:
            f.write(write_fbi(b[:HDR], raw))
    print(f'{len(OUT_NAMES)} textures written to {out_dir}')
    print('Now run build_and_install.bat (Windows) or: modloader.py build  and  modloader.py install')


if __name__ == '__main__':
    main()
