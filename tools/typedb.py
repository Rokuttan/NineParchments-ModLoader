#!/usr/bin/env python3
"""Read/edit the Nine Parchments type database (types.bin in mission1.fbq; editor_types.bin in misc1.fbq).

Layout: "dST\\0" + u8 + u32 N + N strings (\\0) ; then "GenT" blocks with
  u32 size | "GenT" | u32 0xbf | u32 1 | u32 nA + nA*8 | u32 nB + nB*8 | u32 0 |
  LEB128 nProps | props: u32 name-index, u8 type, LEB128 size, data
Types handled here: 0x08 float32, 0x06/0x07 int32, 0x11 enum (1 byte), 0x24 time, 0x12 string.

The game reads types.bin from mission1.fbq (extract it with fbq.py unpack).
Only properties that an object defines itself can be changed; values inherited
from a parent type have to be changed on the parent.

Usage:
  typedb.py props types.bin OBJECT          (lists the numeric properties it defines)
  typedb.py find  types.bin TEXT            (searches objects by name)
  typedb.py get   types.bin OBJECT PROPERTY
  typedb.py set   types.bin OBJECT PROPERTY VALUE OUT.bin
"""
import struct
import sys


def leb(d, o):
    v = sh = 0
    while True:
        b = d[o]
        o += 1
        v |= (b & 0x7F) << sh
        sh += 7
        if not b & 0x80:
            return v, o


class TypeDB:
    def __init__(self, data: bytes):
        self.d = bytearray(data)
        if self.d[:4] != b'dST\0':
            raise ValueError('does not look like a types.bin')
        n = struct.unpack_from('<I', self.d, 5)[0]
        p = 9
        self.strings = []
        for _ in range(n):
            e = self.d.index(b'\0', p)
            self.strings.append(self.d[p:e].decode('latin1'))
            p = e + 1
        self.data_start = p
        self.index = {s: i for i, s in enumerate(self.strings)}

    def blocks(self):
        d = self.d
        o = self.data_start
        magic = b'GenT\xbf\x00\x00\x00'
        while True:
            m = d.find(magic, o)
            if m < 0:
                return
            s = m - 4
            yield s, struct.unpack_from('<I', d, s)[0]
            o = m + 8

    def _gent_props(self, s):
        """Yields (name, type, data_offset, size) for the block at s."""
        d = self.d
        o = s + 12
        for _ in range(2):
            k = struct.unpack_from('<I', d, o)[0]
            o += 4 + 8 * k
        o += 4
        cnt, o = leb(d, o)
        for _ in range(cnt):
            ni, t = struct.unpack_from('<IB', d, o)
            o += 5
            if t == 0x23:  # flag mask: custom layout
                o += 2
                _, c = struct.unpack_from('<II', d, o)
                o += 8 + 5 * c
                yield self.strings[ni], t, None, 0
                continue
            sz, o = leb(d, o)
            yield self.strings[ni], t, o, sz
            o += sz

    def _build_index(self):
        self._index = {}
        for s, ln in self.blocks():
            for pn, t, off, sz in self.props(s):
                if pn == 'Name' and t == 0x12:
                    n = self.strings[struct.unpack_from('<I', self.d, off)[0]]
                    self._index.setdefault(n, []).append(s)
                    break

    def find_object(self, name):
        # The index only stores block offsets; editing values does not move them.
        if not hasattr(self, '_index'):
            self._build_index()
        hits = self._index.get(name, [])
        if not hits:
            raw = self._find_raw(name)
            if raw is not None:
                return raw
        if len(hits) != 1:
            raise KeyError(f'object {name!r}: {len(hits)} matches')
        return hits[0]

    def _find_raw(self, name):
        """Objects in the second section of the file (block versions 0x20bf/0x24bf, e.g.
        CharacterUpgradeManager). Finds the Name property and reads the property
        count stored right before the Guid property."""
        if name not in self.index:
            return None
        cache = self.__dict__.setdefault('_raw', {})
        if name in cache:
            return cache[name]
        idx = struct.pack('<I', self.index[name])
        name_i = struct.pack('<IB', self.index['Name'], 0x12)
        guid_i = struct.pack('<IBB', self.index['Guid'], 0x0b, 8)
        found = []
        for size in (b'\x84\x00', b'\x04'):
            pat = name_i + size + idx
            o = self.d.find(pat)
            while o >= 0:
                g = o - 14
                if self.d[g:g + 6] == guid_i:
                    # LEB128 count right before the Guid (1 or 2 bytes)
                    if self.d[g - 2] & 0x80:
                        count = (self.d[g - 2] & 0x7F) | (self.d[g - 1] << 7)
                    else:
                        count = self.d[g - 1]
                    found.append(('raw', g, count))
                o = self.d.find(pat, o + 1)
        found = [f for f in found if not self._is_genT_offset(f[1])]
        res = found[0] if len(found) == 1 else None
        cache[name] = res
        return res

    def _is_genT_offset(self, off):
        return False

    def props(self, s):
        if isinstance(s, tuple):
            yield from self._raw_props(s[1], s[2])
            return
        yield from self._gent_props(s)

    def _raw_props(self, o, count):
        d = self.d
        for _ in range(count):
            ni, t = struct.unpack_from('<IB', d, o)
            o += 5
            if t == 0x23:
                o += 2
                _, c = struct.unpack_from('<II', d, o)
                o += 8 + 5 * c
                yield self.strings[ni], t, None, 0
                continue
            sz, o = leb(d, o)
            yield self.strings[ni], t, o, sz
            o += sz

    def object_names(self):
        if not hasattr(self, '_index'):
            self._build_index()
        return self._index.keys()

    def prop(self, obj, prop):
        s = self.find_object(obj)
        for pn, t, off, sz in self.props(s):
            if pn == prop:
                return t, off, sz
        raise KeyError(f'{obj} does not define {prop} (it may inherit the default value)')

    def get(self, obj, prop):
        t, off, sz = self.prop(obj, prop)
        if t == 0x08 and sz == 4:
            return struct.unpack_from('<f', self.d, off)[0]
        if t in (0x06, 0x07) and sz == 4:
            return struct.unpack_from('<i', self.d, off)[0]
        if t == 0x24 and sz == 8:  # fixed-point time: raw / 1,024,000 = seconds
            return struct.unpack_from('<q', self.d, off)[0] / 1024000.0
        if t == 0x11 and sz == 1:  # enum
            return self.d[off]
        return ('type 0x%02x' % t, bytes(self.d[off:off + sz]).hex())

    def set(self, obj, prop, value):
        t, off, sz = self.prop(obj, prop)
        if t == 0x08 and sz == 4:
            struct.pack_into('<f', self.d, off, float(value))
        elif t in (0x06, 0x07) and sz == 4:
            struct.pack_into('<i', self.d, off, int(round(float(value))))
        elif t == 0x11 and sz == 1:  # enum (0-255)
            v = int(round(float(value)))
            if not 0 <= v <= 255:
                raise ValueError('enum outside 0..255')
            self.d[off] = v
        elif t == 0x24 and sz == 8:  # time in seconds
            struct.pack_into('<q', self.d, off, int(round(float(value) * 1024000)))
        else:
            raise TypeError(f'{prop} has type 0x{t:02x}; only float/int/time are supported')

    def numeric_props(self, obj):
        out = {}
        for pn, t, off, sz in self.props(self.find_object(obj)):
            if t in (0x06, 0x07, 0x08, 0x24) and off is not None or (t == 0x11 and sz == 1):
                out[pn] = self.get(obj, pn)
        return out


def main(a):
    if len(a) >= 4 and a[1] == 'props':
        db = TypeDB(open(a[2], 'rb').read())
        for k, v in db.numeric_props(a[3]).items():
            print(f'{k} = {v:g}')
    elif len(a) >= 4 and a[1] == 'find':
        db = TypeDB(open(a[2], 'rb').read())
        for n in sorted(db.object_names()):
            if a[3].lower() in n.lower():
                print(n)
    elif len(a) >= 5 and a[1] == 'get':
        db = TypeDB(open(a[2], 'rb').read())
        print(db.get(a[3], a[4]))
    elif len(a) >= 7 and a[1] == 'set':
        db = TypeDB(open(a[2], 'rb').read())
        print('before:', db.get(a[3], a[4]))
        db.set(a[3], a[4], a[5])
        print('after:', db.get(a[3], a[4]))
        open(a[6], 'wb').write(db.d)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
