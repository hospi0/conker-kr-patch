"""게임 힙을 순회해 실제 메모리 경계를 확정한다.

블록 헤더 (페이로드 12바이트 앞):
    +0  BE32 next   다음 블록 헤더
    +4  BE32 prev   이전 블록 헤더
    +8  BE32 (inuse << 24) | size      size 는 페이로드 크기
    +12 페이로드

확인 근거: 폰트 임시버퍼(0x802C97F0) 헤더가 0x802C97E4 에 있고
next = 0x802CBFF4 = 0x802C97E4 + 12 + 0x2804 로 정확히 맞는다.
in-use 바이트가 boot=01 / mid=00(해제) 로 바뀐다.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

RAM = 0x80000000
HDR = 12
SEED = 0x802C97E4          # 폰트 임시버퍼의 블록 헤더


def rd32(ram, a):
    return struct.unpack('>I', ram[a - RAM:a - RAM + 4])[0]


def walk(ram, seed=SEED, limit=200000):
    """seed 에서 prev 로 끝까지 거슬러 올라간 뒤 next 로 훑는다."""
    # 시작점 찾기
    a = seed
    seen = set()
    for _ in range(limit):
        p = rd32(ram, a + 4)
        if not (RAM <= p < RAM + len(ram)) or p in seen or p >= a:
            break
        seen.add(a)
        a = p
    start = a

    blocks = []
    a = start
    seen = set()
    for _ in range(limit):
        if a in seen or not (RAM <= a < RAM + len(ram) - HDR):
            break
        seen.add(a)
        nxt = rd32(ram, a)
        info = rd32(ram, a + 8)
        size = info & 0x00FFFFFF
        inuse = (info >> 24) & 0xFF
        blocks.append((a, size, inuse, nxt))
        if nxt == 0 or nxt <= a or not (RAM <= nxt < RAM + len(ram)):
            break
        a = nxt
    return blocks


def main():
    for name, label in (('hard_rdram.bin', 'boot'), ('rdram.bin', 'mid')):
        p = os.path.join(project.ROOT, 'work', name)
        if not os.path.exists(p):
            continue
        ram = open(p, 'rb').read()
        bs = walk(ram)
        if not bs:
            print('%s: 힙 순회 실패' % label)
            continue
        lo = bs[0][0]
        hi = bs[-1][0] + HDR + bs[-1][1]
        used = sum(b[1] for b in bs if b[2])
        free = sum(b[1] for b in bs if not b[2])
        print('=== %s ===' % label)
        print('  블록 %d개   힙 범위 %08X .. %08X  (%d KB)'
              % (len(bs), lo, hi, (hi - lo) // 1024))
        print('  사용 %d B (%d KB) / 미사용 %d B (%d KB)'
              % (used, used // 1024, free, free // 1024))
        big = sorted((b for b in bs if not b[2]), key=lambda b: -b[1])[:6]
        print('  큰 미사용 블록:')
        for a, s, u, nx in big:
            print('     %08X  payload %08X  %d B (%d KB)' % (a, a + HDR, s, s // 1024))
        print()


if __name__ == '__main__':
    main()
