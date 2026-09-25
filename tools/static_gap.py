"""정적 영역(힙 시작 아래)에서 양쪽 스테이트 모두 손대지 않은 연속 구간을 찾는다.

힙 범위는 heap_walk.py 로 확정: 0x800E9D14 .. 0x803F4FF8
그 아래가 코드+데이터+BSS 다. 여기서 비어 있는 곳이 새 버퍼 후보다.

⚠️ 「두 스냅샷에서 0」은 「영원히 미사용」의 증명이 아니다. 후보를 좁히는 용도다.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

RAM = 0x80000000
HEAP_START = 0x800E9D14
PIX = 0x800C68B0
META_END = 0x800CBD4C


def main():
    boot = np.frombuffer(open(os.path.join(project.ROOT, 'work', 'hard_rdram.bin'), 'rb').read(),
                         dtype=np.uint8)
    midp = os.path.join(project.ROOT, 'work', 'rdram.bin')
    mid = np.frombuffer(open(midp, 'rb').read(), dtype=np.uint8) if os.path.exists(midp) else None

    lo, hi = 0x80000000, HEAP_START
    a = boot[lo - RAM:hi - RAM] != 0
    if mid is not None:
        a = a | (mid[lo - RAM:hi - RAM] != 0)

    print('정적 영역 %08X .. %08X  (%d KB)' % (lo, hi, (hi - lo) // 1024))
    print('  두 스테이트 합쳐 손댄 바이트: %d / %d (%.1f%%)'
          % (a.sum(), len(a), a.sum() * 100.0 / len(a)))

    # 연속 0 구간
    idx = np.flatnonzero(a)
    runs = []
    prev = -1
    for i in idx:
        if i - prev > 1:
            runs.append((prev + 1, i - prev - 1))
        prev = int(i)
    if prev + 1 < len(a):
        runs.append((prev + 1, len(a) - prev - 1))

    runs = [r for r in runs if r[1] >= 0x800]
    runs.sort(key=lambda r: -r[1])
    print('\n  손대지 않은 연속 구간 (>= 2KB), 큰 순 20개:')
    for off, ln in runs[:20]:
        s = lo + off
        tag = ''
        if s <= PIX < s + ln or PIX <= s < META_END:
            tag = '  (폰트 버퍼 인접)'
        print('     %08X .. %08X   %7d B (%d KB)%s' % (s, s + ln, ln, ln // 1024, tag))

    need240 = 240 * 224 + 240 * 4
    need170 = 170 * 224 + 170 * 4
    print('\n  필요량 참고: 170글리프 %d B (%d KB) / 240글리프 %d B (%d KB)'
          % (need170, need170 // 1024, need240, need240 // 1024))
    ok = [r for r in runs if r[1] >= need170]
    print('  170글리프를 담을 수 있는 구간: %d개' % len(ok))
    for off, ln in ok[:5]:
        print('     %08X .. %08X  %d KB' % (lo + off, lo + off + ln, ln // 1024))


if __name__ == '__main__':
    main()
