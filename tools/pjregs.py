"""Project64 .pj 헤더의 레지스터 블록에서 VI_ORIGIN(프레임버퍼 주소)을 찾는다.

RDRAM 이 시작하기 전(0x00 .. rdram_offset)이 레지스터 영역이다.
정확한 필드 배치를 몰라도, 프레임버퍼로 쓸 만한 물리주소 값을 골라내면 판정할 수 있다.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import pjstate


def main():
    path = sys.argv[1]
    with open(path, 'rb') as f:
        d = f.read()
    st = pjstate.load(path)
    hdr = d[:st['rdram_offset']]
    print('헤더 %d B (RDRAM 시작 %08X)' % (len(hdr), st['rdram_offset']))

    # 헤더는 32비트 워드 리틀엔디언으로 저장돼 있다 (ROM 헤더가 그랬다)
    n = len(hdr) // 4
    le = struct.unpack('<%dI' % n, hdr[:n * 4])
    be = struct.unpack('>%dI' % n, hdr[:n * 4])

    print('\n=== 프레임버퍼 후보 (RDRAM 물리 범위 0x00000000-0x00800000, 4KB 정렬, >=0x100000) ===')
    seen = {}
    for i, v in enumerate(le):
        if 0x00100000 <= v < 0x00800000 and v % 0x1000 == 0:
            seen.setdefault(v, []).append(i * 4)
    for v, offs in sorted(seen.items()):
        print('   물리 %08X  (= RAM %08X)   헤더 오프셋 %s'
              % (v, 0x80000000 + v, ['%03X' % o for o in offs[:6]]))
    if not seen:
        print('   없음')

    print('\n=== 가상주소 형태 후보 (0x80xxxxxx, 4KB 정렬) ===')
    seen2 = {}
    for i, v in enumerate(le):
        if 0x80100000 <= v < 0x80800000 and v % 0x1000 == 0:
            seen2.setdefault(v, []).append(i * 4)
    for v, offs in sorted(seen2.items()):
        print('   %08X   헤더 오프셋 %s' % (v, ['%03X' % o for o in offs[:6]]))
    if not seen2:
        print('   없음')


if __name__ == '__main__':
    main()
