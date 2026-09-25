"""패치본 vs 원본 스테이트를 diff 해서 말풍선 폭 값을 찾는다.

같은 장면에서 원본은 줄 폭 ~120, 한글은 (내 모델상) ~98 이어야 하는데
실제 말풍선은 한글 쪽이 더 크다. 어느 값이 말풍선을 정하는지 실측한다.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

RAM = 0x80000000


def main():
    a = np.frombuffer(open(os.path.join(project.ROOT, 'work',
                                        "Conker's Bad Fur Day (U)_rdram.bin"), 'rb').read(),
                      dtype='>u4')
    b = np.frombuffer(open(os.path.join(project.ROOT, 'work', 'kr_rdram.bin'), 'rb').read(),
                      dtype='>u4')
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]

    print('=== 원본이 100~150, 패치본이 그보다 큰 워드 ===')
    m = (a >= 100) & (a <= 150) & (b > a) & (b < 4000)
    idx = np.flatnonzero(m)
    print('후보 %d개' % len(idx))
    for i in idx[:40]:
        print('   %08X : 원본 %-5d -> 한글 %-5d  (+%d)'
              % (RAM + int(i) * 4, int(a[i]), int(b[i]), int(b[i]) - int(a[i])))

    print('\n=== float 로도 확인 (원본 100~150.0) ===')
    fa = a.view('>f4') if a.dtype.itemsize == 4 else None
    af = np.frombuffer(a.tobytes(), dtype='>f4')
    bf = np.frombuffer(b.tobytes(), dtype='>f4')
    with np.errstate(invalid='ignore'):
        mf = (af >= 100) & (af <= 160) & (bf > af + 5) & (bf < 2000)
    idxf = np.flatnonzero(mf)
    print('후보 %d개' % len(idxf))
    for i in idxf[:30]:
        print('   %08X : 원본 %.1f -> 한글 %.1f' % (RAM + int(i) * 4, float(af[i]), float(bf[i])))


if __name__ == '__main__':
    main()
