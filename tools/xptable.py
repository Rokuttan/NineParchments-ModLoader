#!/usr/bin/env python3
"""Nine Parchments experience table (reproduces CharacterUpgradeManager from the v1.1.0 executable).

XP for level L (L >= 2):  base + sum_{j=3..L} (0.9 - j/100) * base * 0.55     (float32)
Total XP to be at level N = sum of the XP of levels 1..N.
The game caps total XP at ExperienceCapNormal / ExperienceCapHardcore; the level is derived
from XP, and skill points = level - 1.  Originals: base 1000, caps 343295 (level 40) and 698900 (level 60).

Usage:
  xptable.py                  prints the original table
  xptable.py 100              XP cap for max level 100
  xptable.py 100 --base 500   same, with ExperienceToUpgrade = 500 (level up 2x faster)
"""
import struct
import sys


def f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]


C6, K = f32(0.9), f32(0.55)


def table(base=1000, max_level=400):
    """List of [(level, level XP, total XP)] computed incrementally, like the game does."""
    b = f32(float(base))
    step = f32(b * K)
    rows = [(1, 0, 0)]
    e = b
    total = 0.0
    for L in range(2, max_level + 1):
        if L >= 3:
            e = f32(e + f32(f32(C6 - f32(L / f32(100.0))) * step))
        lx = int(e)
        total = f32(total + lx)
        rows.append((L, lx, int(total)))
    return rows


def level_xp(L, base=1000):
    return table(base, max(L, 1))[L - 1][1]


def total_xp(N, base=1000):
    return table(base, max(N, 1))[N - 1][2]


def level_for(xp, base=1000):
    lv = 1
    for L, lx, tot in table(base):
        if lx <= 0 and L > 1:
            break
        if tot <= xp:
            lv = L
    return lv


def cap_for(N, base=1000):
    """XP cap that leaves the character exactly at level N (the game uses total + 1)."""
    return total_xp(N, base) + 1


def main(a):
    base = 1000
    if '--base' in a:
        base = int(a[a.index('--base') + 1])
        del a[a.index('--base'):a.index('--base') + 2]
    if len(a) > 1:
        N = int(a[1])
        bad = [L for L, lx, _ in table(base, N + 1) if L > 1 and lx <= 0]
        if bad:
            print(f'warning: the game formula gives XP <= 0 from level {bad[0]} on; use a lower level')
        cap = cap_for(N, base)
        print(f'ExperienceToUpgrade = {base}')
        print(f'max level {N} ({N - 1} skill points): XP cap = {cap}')
        print(f'total XP to reach level {N}: {total_xp(N, base)}')
        print(f'with the XP the original game allows (Normal 343295 / Hardcore 698900) you reach level '
              f'{level_for(343295, base)} / {level_for(698900, base)}')
        return 0
    rows = table(base, 140)
    print(' level     level XP   total XP   points')
    for L in list(range(1, 11)) + list(range(15, 61, 5)) + [80, 100, 120, 140]:
        _, lx, tot = rows[L - 1]
        print(f'{L:6} {lx:12} {tot:10} {L - 1:8}')
    print(f'\nNormal cap 343295 -> level {level_for(343295, base)}; Hardcore cap 698900 -> level {level_for(698900, base)}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
