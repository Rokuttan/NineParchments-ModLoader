#!/usr/bin/env python3
"""Reader/writer for Nine Parchments .fbq packages (Frozenbyte engine).

Format (reverse engineered from nineparchments_64bit.exe v1.1.0):
  u32 version (=3) | u32 file count | u32 header size
  header: for each file
      name\\0 | u32 offset (relative to the end of the header) | u8 flag
      | u32 uncompressed size | u32 stored size | u32 checksum
  flag: 1 = stored uncompressed; 0 and 2 = LZ4 block
  checksum: Fletcher-32 (16-bit big-endian words, blocks of 360,
            initial value 0xFFFF) over the STORED bytes.

Usage:
  fbq.py list   PACKAGE.fbq [filter]
  fbq.py unpack PACKAGE.fbq DEST [filter]
  fbq.py pack   FOLDER OUT.fbq           (packs FOLDER/** uncompressed)
  fbq.py verify PACKAGE.fbq              (checks checksums and decompression)
"""
import os
import struct
import sys

VERSION = 3
FLAG_LZ4_A, FLAG_STORED, FLAG_LZ4_B = 0, 1, 2


def fletcher32(b: bytes) -> int:
    s1 = s2 = 0xFFFF
    n = len(b)
    words = n // 2
    i = 0
    while words:
        t = min(words, 360)
        words -= t
        for _ in range(t):
            s1 += (b[i] << 8) | b[i + 1]
            i += 2
            s2 += s1
        s1 = (s1 & 0xFFFF) + (s1 >> 16)
        s2 = (s2 & 0xFFFF) + (s2 >> 16)
    if n & 1 and b[n - 1]:
        s1 += b[n - 1]
        s2 += s1
        s1 = (s1 & 0xFFFF) + (s1 >> 16)
        s2 = (s2 & 0xFFFF) + (s2 >> 16)
    s1 = ((s1 >> 16) + (s1 & 0xFFFF)) & 0xFFFF
    s2 = ((s2 >> 16) + (s2 & 0xFFFF)) & 0xFFFF
    return (s2 << 16) | s1


def lz4_block_decompress(src: bytes, usize: int) -> bytes:
    dst = bytearray()
    i, n = 0, len(src)
    while i < n:
        t = src[i]
        i += 1
        lit = t >> 4
        if lit == 15:
            while True:
                b = src[i]
                i += 1
                lit += b
                if b != 255:
                    break
        dst += src[i:i + lit]
        i += lit
        if i >= n:
            break
        off = src[i] | (src[i + 1] << 8)
        i += 2
        m = t & 15
        if m == 15:
            while True:
                b = src[i]
                i += 1
                m += b
                if b != 255:
                    break
        m += 4
        st = len(dst) - off
        if off <= 0 or st < 0:
            raise ValueError('invalid LZ4 offset')
        for k in range(m):
            dst.append(dst[st + k])
    if len(dst) != usize:
        raise ValueError(f'LZ4 size {len(dst)} != {usize}')
    return bytes(dst)


class Entry:
    __slots__ = ('name', 'offset', 'flag', 'usize', 'csize', 'checksum')

    def __init__(self, name, offset, flag, usize, csize, checksum):
        self.name, self.offset, self.flag = name, offset, flag
        self.usize, self.csize, self.checksum = usize, csize, checksum


class Package:
    def __init__(self, path):
        self.path = path
        self.f = open(path, 'rb')
        ver, count, hsz = struct.unpack('<III', self.f.read(12))
        if ver != VERSION:
            raise ValueError(f'unexpected package version: {ver}')
        h = self.f.read(hsz)
        self.base = 12 + hsz
        self.entries = []
        p = 0
        for _ in range(count):
            e = h.index(b'\0', p)
            name = h[p:e].decode('latin1')
            p = e + 1
            off, flag, us, cs, ck = struct.unpack_from('<IBIII', h, p)
            p += 17
            self.entries.append(Entry(name, off, flag, us, cs, ck))

    def raw(self, e: Entry) -> bytes:
        self.f.seek(self.base + e.offset)
        return self.f.read(e.csize)

    def read(self, e: Entry) -> bytes:
        r = self.raw(e)
        if e.flag == FLAG_STORED:
            return r
        return lz4_block_decompress(r, e.usize)

    def find(self, name):
        for e in self.entries:
            if e.name == name:
                return e
        return None


def write_package(out_path, files):
    """files: list of (name_in_package, bytes). Written uncompressed (flag 1)."""
    seen = set()
    header = bytearray()
    blobs = []
    off = 0
    for name, data in files:
        name = name.replace('\\', '/').lstrip('/')
        if name in seen:
            raise ValueError(f'duplicate name: {name}')
        seen.add(name)
        enc = name.encode('latin1')
        if b'\0' in enc:
            raise ValueError(f'invalid name: {name!r}')
        header += enc + b'\0'
        header += struct.pack('<IBIII', off, FLAG_STORED, len(data), len(data), fletcher32(data))
        blobs.append(data)
        off += len(data)
    tmp = out_path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(struct.pack('<III', VERSION, len(files), len(header)))
        f.write(header)
        for b in blobs:
            f.write(b)
    os.replace(tmp, out_path)


def collect_dir(root):
    files = []
    for dp, dn, fn in os.walk(root):
        dn.sort()
        for n in sorted(fn):
            full = os.path.join(dp, n)
            rel = os.path.relpath(full, root).replace(os.sep, '/')
            with open(full, 'rb') as f:
                files.append((rel, f.read()))
    return files


def verify(path):
    pkg = Package(path)
    bad = 0
    for e in pkg.entries:
        raw = pkg.raw(e)
        if fletcher32(raw) != e.checksum:
            print('BAD CHECKSUM:', e.name)
            bad += 1
            continue
        try:
            pkg.read(e)
        except Exception as ex:
            print('DECOMPRESSION ERROR:', e.name, ex)
            bad += 1
    print(f'{len(pkg.entries)} files, {bad} problems')
    return bad == 0


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == 'list':
        pkg = Package(argv[2])
        flt = argv[3] if len(argv) > 3 else ''
        for e in pkg.entries:
            if flt in e.name:
                print(f'{e.flag} {e.usize:>10} {e.csize:>10} {e.checksum:08x} {e.name}')
    elif cmd == 'unpack':
        pkg = Package(argv[2])
        dst = argv[3]
        flt = argv[4] if len(argv) > 4 else ''
        n = 0
        for e in pkg.entries:
            if flt not in e.name:
                continue
            out = os.path.normpath(os.path.join(dst, e.name))
            if not out.startswith(os.path.normpath(dst) + os.sep):
                raise ValueError(f'path outside destination: {e.name}')
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, 'wb') as f:
                f.write(pkg.read(e))
            n += 1
        print(n, 'files extracted')
    elif cmd == 'pack':
        files = collect_dir(argv[2])
        write_package(argv[3], files)
        print(len(files), 'files packed into', argv[3])
    elif cmd == 'verify':
        return 0 if verify(argv[2]) else 1
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
