"""말풍선 폭 모델 — 측정 루프를 그대로 재현하고 메시지 단위 예산을 검사한다.

근거 = 측정 함수 `RDRAM 0x802D08D4` 디스어셈블 + 실기 스테이트 3종 실측(오차 0).

    말풍선폭(자막구조체 +0x38) = 1.15 * Wmax + 10.35
    Wmax = 그 메시지에 속한 모든 자막의 최대 줄 폭

★★번역 제약은 줄 단위가 아니라 **메시지 단위**다.
  한 자막이라도 미번역으로 남으면 그 영문이 자모 글리프(advance 13)로 측정돼
  메시지 전체의 말풍선이 부풀고, 텍스트 원점이 화면 밖으로 계산돼 왼쪽에 붙는다.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

SPACE_ADV = 4
MIN_LINE_H = 12
BUBBLE_K = 1.15
BUBBLE_C = 10.35

# 런타임 배치 (블록 507 이 RAM 0x80082B20 에 그대로 올라간다)
RAM_CHARMAP = 0x80085930
RAM_META = 0x800CBBD0


class Metrics:
    """글리프 메타 + charmap. ROM 에서도, RDRAM 덤프에서도 만들 수 있다."""

    def __init__(self, table, meta):
        self.table = list(table)
        self.meta = list(meta)                 # [(w+1, h+1, xoff, yoff)] * 95
        self.fold = not any(0x61 <= c <= 0x7A for c in self.table)
        self.by_code = {}
        for i, c in enumerate(self.table):
            self.by_code.setdefault(c, i)      # 원본 charmap 은 중복이 있다

    @classmethod
    def from_rom(cls, rom=None):
        import font as fontmod
        import charmap as cmapmod
        rom = project.load_rom() if rom is None else rom
        gs, _ = fontmod.parse_chain(rom)
        meta = [(g.w + 1, g.h + 1, g.b2, g.flag) for g in gs]
        return cls(cmapmod.extract(rom), meta)

    @classmethod
    def from_rdram(cls, path):
        d = open(path, 'rb').read()
        table = d[RAM_CHARMAP - 0x80000000:RAM_CHARMAP - 0x80000000 + 95]
        m = d[RAM_META - 0x80000000:RAM_META - 0x80000000 + 95 * 4]
        meta = [tuple(m[i * 4:i * 4 + 4]) for i in range(95)]
        return cls(table, meta)

    def lookup(self, code):
        """룩업 루틴 0x802D0C40 재현. 0x60=공백 센티널, 못 찾으면 원래 코드.

        ★대소문자 접기(0x61~0x7A -= 0x20)는 **패치본에선 제거**돼 있다(블록66 +0xC60).
          charmap 이 0x61~0x7A 를 실제로 쓰면 접기가 없는 빌드이므로 접지 않는다.
          이걸 맞추지 않으면 폭 계산이 통째로 어긋난다.
        """
        if self.fold and 0x61 <= code <= 0x7A:
            code -= 0x20
        if code == 0x20:
            return 0x60
        i = self.by_code.get(code)
        return i if i is not None else code

    def advance(self, slot):
        w1, h1, xoff, yoff = self.meta[slot]
        if xoff > 127:
            xoff -= 256
        return w1 + xoff - 1                   # pen += (w+1) + xoff - 1


def measure(data, m, token_width=0):
    """측정 함수 0x802D08D4 재현.

    반환 (폭, 높이, 줄별폭).  폭 = 줄별 pen 의 최대값.

    ★줄을 끊는 것은 **원시 바이트 0x0A 뿐**이다. 0xBD 같은 토큰은 줄을 끊지 않고
      pen 에 토큰 폭만 더한다 (그래서 0xBD 로 이어진 대사는 한 줄로 누적된다).
    """
    pen = 0
    maxw = 0
    line_h = 0
    total_h = 0
    lines = []
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b == 0x00:
            break
        if b == 0xBC:                          # 2바이트 토큰, 폭 0
            i += 2
            continue
        v = m.lookup(b)
        if v == 0x60:                          # 공백
            pen += SPACE_ADV
            line_h = max(line_h, MIN_LINE_H)
            i += 1
            continue
        if 0xA1 <= v < 0xA8:                   # 폭 0
            i += 1
            continue
        if v >= 0xA8:                          # 디스패처 토큰 (버튼 아이콘 등)
            pen += token_width
            i += 1
            continue
        if b == 0x0A:                          # ★줄바꿈: 원시 바이트로 판정
            maxw = max(maxw, pen)
            lines.append(pen)
            pen = 0
            line_h = max(line_h, MIN_LINE_H)
            total_h += line_h
            line_h = 0
            i += 1
            continue
        w1, h1, xoff, yoff = m.meta[v]
        pen += m.advance(v)
        line_h = max(line_h, yoff + h1)
        i += 1
    maxw = max(maxw, pen)
    lines.append(pen)
    total_h += max(line_h, MIN_LINE_H)
    return maxw, total_h, lines


SEPARATORS = (0x00, 0xBD)


def split_message(buf):
    """자막 추출 함수 0x80380878 재현: 0x00 으로 나누고 연속된 0x00 은 건너뛴다.

    ★`0xBD` 도 분리자로 취급한다. 추출 함수 자체는 0x00 만 보지만,
      메시지가 활성화될 때 게임이 버퍼의 0xBD 를 **제자리에서 0x00 으로 치환**한다
      (같은 메시지가 대기 중엔 `berri !\\xbdhello`, 표시 중엔 `berri !\\x00hello`).
      실기 확인: "hi, berri !" 말풍선의 +0x38 = 118.45 = 1.15*94+10.35,
      94 는 페이지별 폭 [55,54,94,43,75] 의 최대값이다 (이어붙이면 212 가 되어 어긋난다).
    """
    out = []
    i = 0
    n = len(buf)
    while i < n:
        while i < n and buf[i] in SEPARATORS:
            i += 1
        if i >= n:
            break
        j = i
        while j < n and buf[j] not in SEPARATORS:
            j += 1
        out.append(buf[i:j])
        i = j
    return out


def bubble_width(wmax):
    return BUBBLE_K * wmax + BUBBLE_C


def message_budget(subs, m, token_width=0):
    """메시지의 Wmax 와 말풍선 폭."""
    ws = [measure(s, m, token_width)[0] for s in subs]
    wmax = max(ws) if ws else 0
    return wmax, bubble_width(wmax), ws


def check(orig_subs, new_subs, m_orig, m_new, token_width=0):
    """번역본이 원문 예산 안에 드는가."""
    wo, bo, lo = message_budget(orig_subs, m_orig, token_width)
    wn, bn, ln = message_budget(new_subs, m_new, token_width)
    return {
        'orig_wmax': wo, 'orig_bubble': bo, 'orig_each': lo,
        'new_wmax': wn, 'new_bubble': bn, 'new_each': ln,
        'ok': wn <= wo, 'over': wn - wo,
    }


def _selftest():
    """실기 스테이트 3종으로 모델을 검증한다 (구조체 +0x38 실측값과 대조)."""
    root = os.path.join(project.ROOT, 'work')
    cases = [
        # (덤프, 메시지 시작 0xBF 주소, 자막 수, 실측 +0x38)
        ('원본_rdram.bin', 0x801E8BD0, 5, 187.45),
        ('poc_rdram.bin', 0x801E8BA0, 5, 198.95),
        ('패치본_rdram.bin', 0x801E8BC0, 5, 285.20),
        # ★0xBD 로 나뉜 메시지 — 페이지가 각각 자막이다 (이어붙이면 212 -> 254.15 로 어긋난다)
        ('bd_rdram.bin', 0x801E8CF0, 5, 118.45),
        # 메시지 통째 번역 후 (자막 5개 전부 한글) — 말풍선이 원본보다 작아졌다
        ('kr2_rdram.bin', 0x801E8C00, 5, 146.05),
    ]
    ok = True
    for name, base, count, expect in cases:
        p = os.path.join(root, name)
        if not os.path.exists(p):
            print('  건너뜀 (없음): %s' % name)
            continue
        d = open(p, 'rb').read()
        m = Metrics.from_rdram(p)
        s = base - 0x80000000
        assert d[s] == 0xBF, '%s: 0x%08X 가 0xBF 가 아니다 (%02X)' % (name, base, d[s])
        subs = split_message(d[s + 1:s + 1 + 0x200])[:count]
        wmax, bub, each = message_budget(subs, m)
        good = abs(bub - expect) < 0.05
        ok &= good
        print('  %-18s Wmax=%3d  말풍선 %7.2f (실측 %7.2f) %s  각 자막 %s'
              % (name, wmax, bub, expect, 'OK' if good else '불일치', each))
    return ok


if __name__ == '__main__':
    print('말풍선 폭 모델 자체검증 (구조체 +0x38 실측 대조)')
    if _selftest():
        print('통과')
    else:
        print('실패')
        sys.exit(1)
