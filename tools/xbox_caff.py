"""Xbox판 CAFF/LSBL 문자열 컨테이너 — 파서 + 재조립기.

    python tools/xbox_caff.py <텍스트루트>          # 전 파일 왕복(byte-identical) 검증
    python tools/xbox_caff.py <파일> --dump         # 문자열 목록 출력

구조 (`dvddata/aid/text/<언어>/<씬>/default.bin`)
    0x000 'CAFF' + 버전
    0x040 '.data' 섹션 서술자   — 크기 = 파일크기 - 0x180
    0x180 'text' 청크           — 크기 필드 0x194
          키 풀(UTF-16) → 'LSBL' 청크
    LSBL  magic(4) + hdr_len(4) + hdr(hdr_len) + count(4)
          + (u16 idx, u32 off)*count + 종단 6B + UTF-16LE 블롭
    ★off 는 바이트가 아니라 **문자 수**, 블롭은 빈틈 없이 연속, idx 는 0..n-1.

늘리기 위해 고쳐야 하는 크기 필드 (전부 블롭 바이트수에 정확히 비례함을 확인)
    .data 크기(0x50) / text 청크 크기(0x194) / LSBL hdr[2] / LSBL hdr[5]
    LSBL hdr[3], hdr[4] 는 **LSBL 시작 기준 절대 오프셋**이라 델타를 더한다.
"""
import os
import struct
import sys

SEC_DATA_SIZE = 0x50          # '.data' 서술자의 크기 필드
TEXT_CHUNK_SIZE = 0x194       # 'text' 청크의 크기 필드


class Caff(object):
    def __init__(self, data):
        self.raw = bytearray(data)
        d = self.raw
        assert bytes(d[:4]) == b'CAFF', 'CAFF 아님'
        self.p = d.find(b'LSBL')
        assert self.p > 0, 'LSBL 청크 없음'
        self.hlen = struct.unpack_from('<I', d, self.p + 4)[0]
        self.hdr = list(struct.unpack_from('<6I', d, self.p + 8))
        t = self.p + 4 + self.hlen
        self.n = struct.unpack_from('<I', d, t)[0]
        self.tab = t + 4
        self.blob = self.tab + self.n * 6 + 6
        ents = [struct.unpack_from('<HI', d, self.tab + i * 6) for i in range(self.n)]
        self.idx = [e[0] for e in ents]
        self.values = []
        for _, off in ents:
            s = self.blob + off * 2
            e = s
            while e < len(d) - 1 and not (d[e] == 0 and d[e + 1] == 0):
                e += 2
            self.values.append(bytes(d[s:e]).decode('utf-16-le'))
        self.blob_bytes = sum(len(v) + 1 for v in self.values) * 2
        self.tail = bytes(d[self.blob + self.blob_bytes:])

    def build(self, values=None):
        """values 를 넣어 새 파일 바이트를 만든다. 길이가 늘어도 된다."""
        vals = self.values if values is None else values
        assert len(vals) == self.n, '엔트리 수가 바뀌면 키 풀도 고쳐야 한다'
        out = bytearray(self.raw[:self.tab])
        cum = 0
        blob = bytearray()
        for i, v in enumerate(vals):
            out += struct.pack('<HI', self.idx[i], cum)
            b = v.encode('utf-16-le') + b'\x00\x00'
            blob += b
            cum += len(v) + 1
        out += self.raw[self.tab + self.n * 6:self.blob]   # 종단 엔트리 6B
        out += blob
        out += self.tail

        delta = len(blob) - self.blob_bytes
        if delta:
            def bump(off):
                v = struct.unpack_from('<I', out, off)[0]
                struct.pack_into('<I', out, off, v + delta)
            bump(SEC_DATA_SIZE)
            bump(TEXT_CHUNK_SIZE)
            for i in (2, 3, 4, 5):                          # 청크 크기 2·5, 절대오프셋 3·4
                v = self.hdr[i] + delta
                struct.pack_into('<I', out, self.p + 8 + i * 4, v)
        return bytes(out)


def roundtrip(root):
    ok = bad = 0
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if not fn.endswith('.bin'):
                continue
            p = os.path.join(dirpath, fn)
            src = open(p, 'rb').read()
            try:
                c = Caff(src)
                out = c.build()
            except Exception as ex:
                bad += 1
                print('  실패 %s: %s' % (os.path.relpath(p, root), ex))
                continue
            if out == src:
                ok += 1
            else:
                bad += 1
                n = next((i for i in range(min(len(out), len(src))) if out[i] != src[i]), -1)
                print('  불일치 %s (길이 %d/%d, 첫 차이 %05X)'
                      % (os.path.relpath(p, root), len(out), len(src), n))
    print('왕복 일치 %d / 불일치 %d' % (ok, bad))
    return bad == 0


if __name__ == '__main__':
    a = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2] == '--dump':
        c = Caff(open(a, 'rb').read())
        print('엔트리 %d, 블롭 %d B' % (c.n, c.blob_bytes))
        for i, v in enumerate(c.values):
            print('%3d %r' % (i, v[:100]))
    else:
        sys.exit(0 if roundtrip(a) else 1)
