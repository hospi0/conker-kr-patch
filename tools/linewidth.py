"""게임과 같은 방식으로 줄 폭을 계산한다.

    advance = w + xoff        (레이아웃 패스: pen += (w+1) + xoff - 1)
    공백(0x20) = 4            (렌더러 코드에서 확인: addiu $t2, $t1, 4)
    줄바꿈(0x0A) 에서 줄이 끊긴다

말풍선은 줄 폭에 맞춰 커진다. 원본보다 넓어지면 화면 밖으로 밀려 잘린다.
번역문은 **모든 줄이 원본 줄 폭 이하**여야 안전하다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import font as fontmod
import charmap as cmapmod

SPACE_ADV = 4


class Metrics:
    def __init__(self, rom=None, glyphs=None, table=None):
        rom = project.load_rom() if rom is None else rom
        self.glyphs = glyphs if glyphs is not None else fontmod.parse_chain(rom)[0]
        self.table = table if table is not None else cmapmod.extract(rom)
        self.by_code = {}
        for i, c in enumerate(self.table):
            self.by_code.setdefault(c, i)

    def advance_of_code(self, code):
        if code == 0x20:
            return SPACE_ADV
        code = cmapmod.fold(code)
        i = self.by_code.get(code)
        if i is None:
            return None
        g = self.glyphs[i]
        xoff = g.b2 if g.b2 < 128 else g.b2 - 256
        return g.w + xoff

    def line_widths(self, data):
        """바이트열 -> 줄별 폭 리스트. 모르는 코드는 예외."""
        out = []
        cur = 0
        for b in data:
            if b == 0x0A:
                out.append(cur)
                cur = 0
                continue
            a = self.advance_of_code(b)
            if a is None:
                raise ValueError('매핑 없는 코드 0x%02X' % b)
            cur += a
        out.append(cur)
        return out


def main():
    rom = project.load_rom()
    m = Metrics(rom)
    for s in (b"Hi, you've reached,\nlike, Berri's place.",
              b'hi, berri !', b'hello. . .'):
        print('%-44r -> %s' % (s, m.line_widths(s)))


if __name__ == '__main__':
    main()
