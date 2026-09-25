"""Xbox판 「Conker: Live & Reloaded」 공식 일본어 대본을 N64 자막에 붙인다.

    python tools/xbox_ref.py [텍스트 디렉터리]   -> work/xbox_ref.json

리메이크판은 1인용 캠페인 대사를 원작에서 거의 그대로 가져왔다. 그래서 **공식 일본어
로컬라이즈**를 우리 자막에 1:1로 붙일 수 있고, 번역 품질 검수(어조·존대·농담 해석)의
오라클이 된다. ⚠️번역 입력이 아니라 **참조**로만 쓴다 — 리메이크는 일부 대사가 수정됐다.

포맷 (`dvddata/aid/text/<언어>/<씬>/default.bin`)
    'CAFF' 헤더 → `.data` 섹션 → `text` 청크 → 키 풀 → `LSBL` 문자열 테이블
    LSBL = magic(4) + hdr_len(4) + hdr(hdr_len) + count(4) + (u16 idx, u32 off)*count
           + 종단 엔트리 6B + UTF-16LE 문자열 블롭
    ★`off` 는 바이트가 아니라 **문자 수**다 (블롭 시작 = 테이블 끝 + 6).
언어 디렉터리끼리 엔트리 순서가 같아서 영↔일이 인덱스로 대응한다.
한 엔트리는 씬 전체이고 `{PMARKER}`/`{PARAGRAPH}` 로 대사가 나뉜다 — 이걸 쪼개면
N64 자막과 같은 입자가 된다.
"""
import glob
import io
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project

SPLIT = re.compile(r'\{(?:PMARKER|PARAGRAPH)\}')
TOKEN = re.compile(r'\{[A-Z]+\}')


def norm(t):
    """영문 대조용 정규화 — 대소문자·구두점·공백·토큰 차이를 지운다."""
    t = TOKEN.sub(' ', t)
    t = re.sub(r'[^a-z0-9]+', ' ', t.lower())
    return ' '.join(t.split())


def _read_lsbl(d, p):
    hl = struct.unpack_from('<I', d, p + 4)[0]
    t = p + 4 + hl
    if t + 4 > len(d):
        return None
    n = struct.unpack_from('<I', d, t)[0]
    t += 4
    if n > 20000 or t + n * 6 + 6 > len(d):
        return None
    ents = [struct.unpack_from('<HI', d, t + i * 6) for i in range(n)]
    blob = t + n * 6 + 6                       # ★종단 엔트리 6B 를 건너뛴다
    out = []
    for _, off in ents:
        s = blob + off * 2                     # ★문자 오프셋
        if s >= len(d):
            return None
        e = s
        while e < len(d) - 1 and not (d[e] == 0 and d[e + 1] == 0):
            e += 2
        out.append(d[s:e].decode('utf-16-le', 'replace'))
    return out


def read_strings(path):
    """가장 큰 LSBL 청크를 문자열 목록으로 (키 테이블도 LSBL 이라 크기로 고른다)."""
    d = open(path, 'rb').read()
    best, p = None, 0
    while True:
        p = d.find(b'LSBL', p)
        if p < 0:
            break
        r = _read_lsbl(d, p)
        if r and (best is None or len(''.join(r)) > len(''.join(best))):
            best = r
        p += 4
    return best or []


def load_pairs(root):
    """씬별 영↔일 세그먼트 쌍."""
    en_root = os.path.join(root, 'English')
    segs = []
    bad = []
    for scene in sorted(os.listdir(en_root)):
        fe = os.path.join(en_root, scene, 'default.bin')
        fj = os.path.join(root, 'Japanese', scene, 'default.bin')
        if not (os.path.exists(fe) and os.path.exists(fj)):
            continue
        a, b = read_strings(fe), read_strings(fj)
        if len(a) != len(b):
            bad.append(scene)
            continue
        for x, y in zip(a, b):
            xs, ys = SPLIT.split(x), SPLIT.split(y)
            if len(xs) != len(ys):                 # 마커 수가 다르면 통째로만 쓴다
                segs.append((scene, x.strip(), y.strip()))
                continue
            for u, v in zip(xs, ys):
                if u.strip():
                    segs.append((scene, u.strip(), v.strip()))
    return segs, bad


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else project.load_local().get('xbox_ref_dir')
    if not root or not os.path.isdir(root):
        raise SystemExit('Xbox 텍스트 디렉터리를 인자나 config/local.json 의 '
                         '"xbox_ref_dir" 로 지정할 것 (…/dvddata/aid/text)')
    segs, bad = load_pairs(root)
    print('씬 %d개 실패, 세그먼트 %d개' % (len(bad), len(segs)))

    table = {}
    for scene, en, jp in segs:
        n = norm(en)
        if n:
            table.setdefault(n, (scene, en, jp))

    out = {}
    hit = tot = 0
    for p in sorted(set(glob.glob(os.path.join(project.ROOT, 'trans', 'conker_kr_*.json'))
                        + glob.glob(os.path.join(project.ROOT, 'trans', '번역완',
                                                 'conker_kr_*.json')))):
        doc = json.load(io.open(p, encoding='utf-8'))
        for msg in doc['messages']:
            for s in msg['subs']:
                n = norm(s['en'])
                if len(n) < 10:                    # 짧은 문구는 오탐이 많다
                    continue
                tot += 1
                if n in table:
                    hit += 1
                    scene, en, jp = table[n]
                    out[s['id']] = {'scene': scene, 'en': s['en'],
                                    'ko': s.get('ko', ''), 'jp': jp}
    print('N64 자막 -> 공식 일본어 대응 %d / %d (%.1f%%)'
          % (hit, tot, hit * 100.0 / max(1, tot)))
    dst = os.path.join(project.ROOT, 'work', 'xbox_ref.json')
    with io.open(dst, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    print('-> work/xbox_ref.json')


if __name__ == '__main__':
    main()
