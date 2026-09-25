"""RDRAM 사용 지도. 새 폰트 버퍼를 놓을 안전한 영역을 찾는다.

두 스테이트를 대조한다.
  hard_rdram.bin : 하드리셋 직후(부팅 중)
  rdram.bin      : 게임 중반(자막 표시 중)

두 시점 모두 손대지 않은 영역이 후보다. 다만 「지금 0」이 「영원히 미사용」의
증명은 아니다 — 동적 할당이 나중에 쓸 수 있다. 판정은 보수적으로 한다.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

RAM = 0x80000000
BS = 0x1000


def load(name):
    p = os.path.join(project.ROOT, 'work', name)
    if not os.path.exists(p):
        return None
    return np.frombuffer(open(p, 'rb').read(), dtype=np.uint8)


def block_profile(a):
    n = len(a) // BS
    v = a[:n * BS].reshape(n, BS)
    return (v != 0).sum(axis=1)


def main():
    boot = load('hard_rdram.bin')
    mid = load('rdram.bin')
    if boot is None:
        print('work/hard_rdram.bin 이 없다.')
        return
    names = [('boot', boot)]
    if mid is not None:
        names.append(('mid', mid))

    profs = {k: block_profile(v) for k, v in names}
    n = min(len(p) for p in profs.values())

    print('=== 64KB 단위 지도  (.=양쪽 전부 0, b=boot만 사용, m=mid만 사용, #=양쪽 사용) ===')
    line = ''
    rows = []
    for i in range(0, n, 16):
        bb = profs['boot'][i:i + 16].sum()
        mm = profs['mid'][i:i + 16].sum() if 'mid' in profs else 0
        c = '.' if (bb == 0 and mm == 0) else ('#' if (bb and mm) else ('b' if bb else 'm'))
        line += c
        if len(line) == 64:
            rows.append('%08X %s' % (RAM + (i - 63 * 16) * BS, line))
            line = ''
    if line:
        rows.append('%08X %s' % (RAM + (n - len(line) * 16) * BS, line))
    print('\n'.join(rows))

    print('\n=== 양쪽 모두 전부 0 인 연속 구간 (>= 32KB) ===')
    zero = np.ones(n, dtype=bool)
    for p in profs.values():
        zero &= (p[:n] == 0)
    runs = []
    s = None
    for i in range(n):
        if zero[i]:
            if s is None:
                s = i
        else:
            if s is not None and (i - s) * BS >= 0x8000:
                runs.append((s, i - s))
            s = None
    if s is not None and (n - s) * BS >= 0x8000:
        runs.append((s, n - s))
    for st, ln in runs:
        print('   %08X .. %08X   %7d B (%d KB)'
              % (RAM + st * BS, RAM + (st + ln) * BS, ln * BS, ln * BS // 1024))
    if not runs:
        print('   없음')

    print('\n=== 관심 지점 주변 ===')
    for lo, hi, label in ((0x800B0DC0, 0x800C68B0, '블록507 끝 ~ pix 버퍼 시작'),
                          (0x800CBD4C, 0x800E0000, 'meta 배열 끝 이후')):
        for k, p in profs.items():
            i0, i1 = (lo - RAM) // BS, (hi - RAM) // BS
            used = p[i0:i1]
            print('  %-28s %-5s : %d/%d 블록 사용, 총 비영바이트 %d'
                  % (label, k, (used != 0).sum(), len(used), used.sum()))


if __name__ == '__main__':
    main()
