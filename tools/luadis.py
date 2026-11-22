#!/usr/bin/env python3
"""Simple Lua 5.1 bytecode disassembler (for studying the game's scripts).
Usage: luadis.py file.x64.lub [text-filter]"""
import struct
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from luachunk import Chunk  # noqa: E402

OPS = ('MOVE LOADK LOADBOOL LOADNIL GETUPVAL GETGLOBAL GETTABLE SETGLOBAL SETUPVAL SETTABLE NEWTABLE SELF '
       'ADD SUB MUL DIV MOD POW UNM NOT LEN CONCAT JMP EQ LT LE TEST TESTSET CALL TAILCALL RETURN FORLOOP '
       'FORPREP TFORLOOP SETLIST CLOSE CLOSURE VARARG').split()


def kstr(f, i):
    t, v = f.constants[i]
    if t == 4:
        return repr(v.decode('utf-8', 'replace'))
    if t == 3:
        return repr(struct.unpack('<f', v)[0])
    return repr(v)


def rk(f, x):
    return kstr(f, x - 256) if x >= 256 else f'R{x}'


def dis(f, path='main', out=print):
    src = f.source.decode('latin1', 'replace') if f.source else ''
    out(f'--- function {path} (lines {f.linedefined}-{f.lastlinedefined}) params={f.numparams} {src}')
    for i in range(len(f.code) // 4):
        ins = struct.unpack_from('<I', f.code, i * 4)[0]
        op = ins & 0x3F
        a, c, b, bx = (ins >> 6) & 0xFF, (ins >> 14) & 0x1FF, ins >> 23, ins >> 14
        sbx = bx - 131071
        n = OPS[op] if op < len(OPS) else f'OP{op}'
        if n in ('LOADK', 'GETGLOBAL', 'SETGLOBAL'):
            arg = f'R{a} {kstr(f, bx)}'
        elif n in ('GETTABLE', 'SELF'):
            arg = f'R{a} R{b} {rk(f, c)}'
        elif n == 'SETTABLE':
            arg = f'R{a}[{rk(f, b)}] = {rk(f, c)}'
        elif n in ('ADD', 'SUB', 'MUL', 'DIV', 'MOD', 'POW', 'EQ', 'LT', 'LE'):
            arg = f'{a} {rk(f, b)} {rk(f, c)}'
        elif n in ('JMP', 'FORLOOP', 'FORPREP'):
            arg = f'R{a} -> {i + 1 + sbx}'
        elif n == 'CLOSURE':
            arg = f'R{a} function {path}.{bx}'
        else:
            arg = f'{a} {b} {c}'
        out(f'  {i:4} {n:9} {arg}')
    for k, p in enumerate(f.protos):
        dis(p, f'{path}.{k}', out)


if __name__ == '__main__':
    c = Chunk(open(sys.argv[1], 'rb').read())
    lines = []
    dis(c.main, out=lines.append)
    if len(sys.argv) > 2:
        # show only functions that contain the filter
        block, keep = [], False
        for ln in lines + ['--- end']:
            if ln.startswith('---'):
                if keep:
                    print('\n'.join(block))
                block, keep = [ln], False
            else:
                block.append(ln)
                keep |= sys.argv[2] in ln
    else:
        print('\n'.join(lines))
