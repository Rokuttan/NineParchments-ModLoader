#!/usr/bin/env python3
"""Read and write Nine Parchments Lua 5.1 bytecode (.lub / .x64.lub).

The game uses Lua 5.1.4 with lua_Number = 4-byte float. The .lub files (32-bit)
use a 4-byte size_t and the .x64.lub files an 8-byte one. Each file's header
describes its format; numbers are kept as raw bytes, so reading and writing
returns exactly the same file.
"""
import struct


class Function:
    __slots__ = ('source', 'linedefined', 'lastlinedefined', 'nups', 'numparams',
                 'is_vararg', 'maxstacksize', 'code', 'constants', 'protos',
                 'lineinfo', 'locvars', 'upvalues')


class Chunk:
    """constants: list of (type, value). type 0=nil, 1=bool, 3=number (raw bytes), 4=string (bytes or None)."""

    def __init__(self, data: bytes):
        if data[:5] != b'\x1bLuaQ':
            raise ValueError('not Lua 5.1 bytecode')
        self.header = data[:12]
        endian, self.sint, self.ssize, self.sinstr, self.snum = data[6], data[7], data[8], data[9], data[10]
        if endian != 1:
            raise ValueError('only little-endian is supported')
        self.d = data
        self.p = 12
        self.main = self._func()
        if self.p != len(data):
            raise ValueError(f'{len(data) - self.p} trailing bytes')
        del self.d

    # --- reading
    def _int(self):
        v = int.from_bytes(self.d[self.p:self.p + self.sint], 'little', signed=True)
        self.p += self.sint
        return v

    def _size(self):
        v = int.from_bytes(self.d[self.p:self.p + self.ssize], 'little')
        self.p += self.ssize
        return v

    def _str(self):
        n = self._size()
        if n == 0:
            return None
        s = self.d[self.p:self.p + n - 1]
        self.p += n
        return s

    def _u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def _func(self):
        f = Function()
        f.source = self._str()
        f.linedefined = self._int()
        f.lastlinedefined = self._int()
        f.nups, f.numparams, f.is_vararg, f.maxstacksize = (self._u8() for _ in range(4))
        n = self._int()
        f.code = self.d[self.p:self.p + n * self.sinstr]
        self.p += n * self.sinstr
        f.constants = []
        for _ in range(self._int()):
            t = self._u8()
            if t == 0:
                f.constants.append((0, None))
            elif t == 1:
                f.constants.append((1, self._u8()))
            elif t == 3:
                f.constants.append((3, self.d[self.p:self.p + self.snum]))
                self.p += self.snum
            elif t == 4:
                f.constants.append((4, self._str()))
            else:
                raise ValueError(f'unknown constant type {t}')
        f.protos = [self._func() for _ in range(self._int())]
        n = self._int()
        f.lineinfo = self.d[self.p:self.p + n * self.sint]
        self.p += n * self.sint
        f.locvars = []
        for _ in range(self._int()):
            f.locvars.append((self._str(), self._int(), self._int()))
        f.upvalues = [self._str() for _ in range(self._int())]
        return f

    # --- writing
    def dump(self) -> bytes:
        out = bytearray(self.header)
        self._wfunc(out, self.main)
        return bytes(out)

    def _wint(self, out, v):
        out += int(v).to_bytes(self.sint, 'little', signed=True)

    def _wstr(self, out, s):
        if s is None:
            out += (0).to_bytes(self.ssize, 'little')
        else:
            out += (len(s) + 1).to_bytes(self.ssize, 'little') + s + b'\0'

    def _wfunc(self, out, f):
        self._wstr(out, f.source)
        self._wint(out, f.linedefined)
        self._wint(out, f.lastlinedefined)
        out += bytes((f.nups, f.numparams, f.is_vararg, f.maxstacksize))
        self._wint(out, len(f.code) // self.sinstr)
        out += f.code
        self._wint(out, len(f.constants))
        for t, v in f.constants:
            out.append(t)
            if t == 1:
                out.append(v)
            elif t == 3:
                out += v
            elif t == 4:
                self._wstr(out, v)
        self._wint(out, len(f.protos))
        for p in f.protos:
            self._wfunc(out, p)
        self._wint(out, len(f.lineinfo) // self.sint)
        out += f.lineinfo
        self._wint(out, len(f.locvars))
        for name, a, b in f.locvars:
            self._wstr(out, name)
            self._wint(out, a)
            self._wint(out, b)
        self._wint(out, len(f.upvalues))
        for u in f.upvalues:
            self._wstr(out, u)

    # --- helpers
    def globals_table(self):
        """name -> constant index pairs for the LOADK + SETGLOBAL pattern used by the locale files."""
        f = self.main
        regs = {}
        out = {}
        n = len(f.code) // self.sinstr
        for i in range(n):
            ins = struct.unpack_from('<I', f.code, i * 4)[0]
            op, a, bx = ins & 0x3F, (ins >> 6) & 0xFF, ins >> 14
            if op == 1:      # LOADK
                regs[a] = bx
            elif op == 7 and a in regs:   # SETGLOBAL
                name = f.constants[bx][1]
                out[name.decode('utf-8', 'replace')] = regs[a]
        return out

    def _setglobal_sites(self):
        """Lists (load_instruction_index, opcode, name) for each top-level 'name = constant'."""
        f = self.main
        last = {}
        out = []
        for i in range(len(f.code) // 4):
            ins = struct.unpack_from('<I', f.code, i * 4)[0]
            op, a, bx = ins & 0x3F, (ins >> 6) & 0xFF, ins >> 14
            if op in (1, 2):          # LOADK / LOADBOOL
                last[a] = (i, op)
            elif op == 7 and a in last:
                out.append((last[a][0], last[a][1], f.constants[bx][1].decode('utf-8', 'replace')))
        return out

    def _put(self, i, ins):
        c = bytearray(self.main.code)
        struct.pack_into('<I', c, i * 4, ins)
        self.main.code = bytes(c)

    def set_global_string(self, name, value: bytes):
        """Changes a key's text without touching other keys that share the same constant."""
        f = self.main
        for i, op, n in self._setglobal_sites():
            if n != name or op != 1:
                continue
            ins = struct.unpack_from('<I', f.code, i * 4)[0]
            k = ins >> 14
            shared = sum(1 for j in range(len(f.code) // 4)
                         if (struct.unpack_from('<I', f.code, j * 4)[0] & 0x3F) == 1
                         and struct.unpack_from('<I', f.code, j * 4)[0] >> 14 == k) > 1
            if shared:
                f.constants.append((4, value))
                k = len(f.constants) - 1
                if k >= 1 << 18:
                    raise ValueError('too many constants')
                self._put(i, (ins & 0x3FFF) | (k << 14))
            else:
                f.constants[k] = (4, value)
            return True
        return False

    def set_global_bool(self, name, value: bool):
        for i, op, n in self._setglobal_sites():
            if n == name and op == 2:
                ins = struct.unpack_from('<I', self.main.code, i * 4)[0]
                ins = (ins & ~(0x1FF << 23)) | ((1 if value else 0) << 23)
                self._put(i, ins & 0xFFFFFFFF)
                return True
        return False

    def append_loadstring_call(self, source: bytes):
        """Appends pcall(loadstring(source)) to the end of the main function.

        The instructions go right before the final RETURN, so every path that would end
        the script runs the mod code first. Uses fresh registers (above maxstacksize)
        so locals and closure upvalues are not touched.
        """
        f = self.main
        last = struct.unpack_from('<I', f.code, len(f.code) - 4)[0]
        if last & 0x3F != 30:
            raise ValueError('the main function does not end with RETURN')
        r = f.maxstacksize
        if r + 3 > 250:
            raise ValueError('not enough registers')

        def k(v):
            f.constants.append((4, v))
            return len(f.constants) - 1
        kp, kl, ks = k(b'pcall'), k(b'loadstring'), k(source)
        if ks >= 1 << 18:
            raise ValueError('too many constants')
        ins = [
            5 | (r << 6) | (kp << 14),                         # GETGLOBAL r   'pcall'
            5 | ((r + 1) << 6) | (kl << 14),                   # GETGLOBAL r+1 'loadstring'
            1 | ((r + 2) << 6) | (ks << 14),                   # LOADK     r+2 source
            28 | ((r + 1) << 6) | (2 << 14) | (2 << 23),       # CALL r+1 (1 arg, 1 result)
            28 | (r << 6) | (1 << 14) | (2 << 23),             # CALL r   (1 arg, 0 results)
        ]
        f.code = f.code[:-4] + b''.join(struct.pack('<I', i) for i in ins) + f.code[-4:]
        if f.lineinfo:
            line = f.lineinfo[-self.sint:]
            f.lineinfo = f.lineinfo[:-self.sint] + line * len(ins) + line
        f.maxstacksize = r + 3
