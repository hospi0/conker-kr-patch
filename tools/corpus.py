"""번역 모집단 확정 — 압축해제 코퍼스에서 대사·UI 문자열을 전수 추출한다.

2단계로 뽑는다.

  1) 씨앗   : 어절 구조로 「영어 문장」인 런만 고른다 (사전 불필요).
              공백으로 나눈 낱말이 3개 이상이고, 낱말 길이가 14 이하이며,
              70% 이상이 모음을 포함할 것.
  2) 확장   : 씨앗에서 좌우로 **텍스트 영역**(유효문자 ∪ 구분자)을 따라 번져 나가
              그 안의 모든 문자열을 채택한다. 짧은 UI 문자열과 고유명사가 여기서 들어온다.
              구분자가 16바이트 이상 연속되면 영역이 끝난 것으로 본다.

★밀도(유효문자 비율)로 대사 블록을 가리려던 시도는 실패한다.
  4비트 텍스처 데이터가 ASCII 범위라 밀도 1.00 으로 잡힌다 (`DDDUDEDDES4...`).
  공백·어절 구조가 진짜 판별자다.

★`0xBF` 는 보편적인 메시지 마커가 아니다 (코퍼스 전체에서 12곳뿐).
  따라서 말풍선 단위 경계는 정적으로 확정할 수 없다.
  **대신 자막마다 「원문 자기 폭 이하」를 지키면 어떤 묶음이든 최대폭이 늘지 않는다.**
  이게 경계를 몰라도 성립하는 안전한 예산 규칙이다 (docs/bubble-width.md).
"""
import json
import os
import re
import io
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import blocks as blockmod

PUNCT = set(b"&:,$\"=!.>#{([<-%+?})];/~'") | {0x5C, 0x5E}
LOWER = set(range(0x61, 0x7B))
UPPER = set(range(0x41, 0x5B))
DIGIT = set(range(0x30, 0x3A))
# ★버튼 아이콘·욕설 검열 기호 (0xA1~0xBF). 이걸 텍스트로 안 치면 그게 든 자막과
#   그 뒤가 통째로 잘려 나간다 — 실기에서 `press ©` 가 미번역으로 남아 발각됐다.
#   0xBD 는 자막 분리자, 0xBF 는 블록 시작 마커라 뺀다.
ICON = set(range(0xA1, 0xC0)) - {0xBD, 0xBF}
VALID = LOWER | UPPER | DIGIT | {0x20, 0x0A} | PUNCT | ICON
SEP = {0x00, 0xBD}
VOWEL = set(b'aeiouyAEIOUY')
GAP = 16                      # 구분자가 이만큼 연속되면 텍스트 영역이 끝난 것으로 본다

_word = re.compile(rb"[A-Za-z']+")


def seedlike(s):
    """사전 없이 「영어 문장」인지 판정한다."""
    if len(s) < 10 or b' ' not in s:
        return False
    if not any(c in LOWER for c in s):
        return False
    toks = _word.findall(s)
    if len(toks) < 3 or any(len(t) > 14 for t in toks):
        return False
    v = sum(1 for t in toks if any(c in VOWEL for c in t))
    return v / len(toks) >= 0.7


def _runs(d, lo, hi):
    """[lo,hi) 안에서 구분자로 나뉜 문자열들 -> [(offset, bytes)]"""
    out = []
    p = lo
    while p < hi:
        if d[p] in SEP:
            p += 1
            continue
        q = p
        while q < hi and d[q] in VALID:
            q += 1
        if q > p:
            out.append((p, d[p:q]))
        p = max(q, p + 1)
    return out


def text_region(d, at):
    """씨앗 위치에서 좌우로 텍스트 영역을 넓힌다."""
    n = len(d)
    lo = at
    while lo > 0:
        j = lo - 1
        gap = 0
        while j >= 0 and d[j] in SEP:
            gap += 1
            j -= 1
        if gap >= GAP:
            break
        if j < 0 or d[j] not in VALID:
            lo = lo - gap
            break
        k = j
        while k >= 0 and d[k] in VALID:
            k -= 1
        lo = k + 1
    hi = at
    while hi < n:
        j = hi
        gap = 0
        while j < n and d[j] in SEP:
            gap += 1
            j += 1
        if gap >= GAP:
            break
        if j >= n or d[j] not in VALID:
            hi = hi + gap
            break
        k = j
        while k < n and d[k] in VALID:
            k += 1
        hi = k
    return lo, hi


def extract(verbose=True):
    blks = json.load(open(os.path.join(project.ROOT, 'extract', 'blocks.json')))
    raw = open(os.path.join(project.ROOT, 'extract', 'raw.bin'), 'rb').read()
    starts = blockmod.blob_offsets(blks)

    seeds = {}
    for k, (rom, cs, rs) in enumerate(blks):
        s0 = starts[k]
        d = raw[s0:s0 + rs]
        p = 0
        while p < rs:
            if d[p] in VALID:
                q = p
                while q < rs and d[q] in VALID:
                    q += 1
                bounded = (p == 0 or d[p - 1] in SEP) and (q >= rs or d[q] in SEP)
                if bounded and seedlike(d[p:q]):
                    seeds.setdefault(k, []).append(p)
                p = q
            else:
                p += 1
    n_seed = sum(len(v) for v in seeds.values())

    strings = []
    for k, offs in seeds.items():
        rom, cs, rs = blks[k]
        d = raw[starts[k]:starts[k] + rs]
        regions = []
        for at in offs:
            lo, hi = text_region(d, at)
            if regions and lo <= regions[-1][1]:
                regions[-1] = (regions[-1][0], max(regions[-1][1], hi))
            else:
                regions.append((lo, hi))
        for lo, hi in regions:
            for off, s in _runs(d, lo, hi):
                if not any(c in LOWER or c in UPPER for c in s):
                    continue
                strings.append({'block': k, 'rom': rom, 'off': off,
                                'text': s.decode('latin-1')})
    strings.sort(key=lambda r: (r['block'], r['off']))

    if verbose:
        uniq = set(r['text'] for r in strings)
        nb = sum(len(r['text']) for r in strings)
        print('씨앗 %d개 / %d블록' % (n_seed, len(seeds)))
        print('확장 후 문자열 %d개, 고유 %d개, %d바이트' % (len(strings), len(uniq), nb))
        print('  (씨앗만: %d개 -> 확장으로 %+d개)' % (n_seed, len(strings) - n_seed))
    return strings


LEDGER = os.path.join(project.ROOT, 'extract', 'ids.json')


def assign_ids(strings):
    """★id 는 **대장(extract/ids.json)** 에서 가져온다. 순서로 매기면 안 된다.

    추출기를 고쳐 문자열이 하나라도 늘면 그 뒤 id 가 전부 밀려서, 이미 번역한
    파일들이 통째로 엉뚱한 자리에 매핑된다 (실제로 48개가 추가되면서 2,968개가 밀 뻔했다).
    대장은 `"블록:오프셋" -> id` 이고, 새 문자열은 **뒤에 이어 붙인다**.
    """
    led = {}
    if os.path.exists(LEDGER):
        led = json.load(open(LEDGER, encoding='utf-8'))
    nxt = (max(led.values()) + 1) if led else 0
    added = 0
    for r in strings:
        k = '%d:%d' % (r['block'], r['off'])
        if k not in led:
            led[k] = nxt
            nxt += 1
            added += 1
        r['id'] = led[k]
    if added:
        with io.open(LEDGER, 'w', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps(led, indent=0))
    return strings, added


def add_budgets(strings, rom=None):
    """문자열마다 바이트·폭 예산을 붙인다.

    폭 예산 = **그 자막 자신의 원문 최대 줄 폭**.
    말풍선은 메시지 단위 최대폭으로 정해지는데(docs/bubble-width.md) 메시지 경계를
    정적으로 확정할 수 없으므로, 자막마다 자기 폭을 지키는 보수적 규칙을 쓴다.
    이러면 어떤 묶음이든 최대폭이 원문보다 커질 수 없다.
    """
    import bubble
    m = bubble.Metrics.from_rom(rom)
    for r in strings:
        b = r['text'].encode('latin-1')
        w, h, lines = bubble.measure(b, m)
        r['bytes'] = len(b)
        r['width'] = w
        r['lines'] = lines
    return strings


def group_messages(strings):
    """말풍선(메시지) 단위로 묶는다.

    ★자막 사이 간격이 **정확히 1바이트**(구분자 0x00 또는 0xBD 하나)면 같은 메시지,
      2바이트 이상 벌어지면 새 메시지다.
      실기로 확인된 두 메시지를 정확히 재현한다 — Berri 자동응답기 5개(Wmax 154),
      "hi, berri !" 5개(Wmax 94). 둘 다 구조체 +0x38 실측과 일치한다.
      전체 코퍼스에서 간격 1 이 2,232곳, 2~8 이 약 750곳으로 분포도 두 갈래로 갈린다.
    """
    msgs = []
    cur = []
    prev = None
    for r in strings:
        if prev is not None and r['block'] == prev['block'] \
                and r['off'] == prev['off'] + prev['bytes'] + 1:
            cur.append(r)
        else:
            if cur:
                msgs.append(cur)
            cur = [r]
        prev = r
    if cur:
        msgs.append(cur)
    for i, m in enumerate(msgs):
        wmax = max(r['width'] for r in m)
        for r in m:
            r['msg'] = i
            r['msg_wmax'] = wmax
    return msgs


def report(strings):
    import collections
    nb = sum(r['bytes'] for r in strings)
    print()
    print('=== 번역 예산 ===')
    print('문자열 %d개 / 고유 %d개 / %d바이트'
          % (len(strings), len(set(r['text'] for r in strings)), nb))
    # 한글 환산: 음절당 평균 2.5바이트(받침 유무), 진행폭 13
    print('바이트 예산 -> 한글 약 %d음절 분' % (nb // 2.5))
    per_line = [max(1, w // 13) for r in strings for w in r['lines'] if w > 0]
    if per_line:
        h = collections.Counter(min(v, 12) for v in per_line)
        print('줄당 한글 수용량 분포 (폭/13):')
        for k in sorted(h):
            print('   %2d음절%s : %4d줄' % (k, '+' if k == 12 else ' ', h[k]))
    tight = [r for r in strings if r['width'] < 39]        # 3음절 미만
    print('폭 39 미만(3음절도 안 들어가는) 문자열 %d개' % len(tight))


def report_messages(msgs):
    import collections
    print()
    print('=== 말풍선(메시지) 단위 ===')
    n = collections.Counter(len(m) for m in msgs)
    print('메시지 %d개, 자막 %d개' % (len(msgs), sum(len(m) for m in msgs)))
    print('메시지당 자막 수:', dict(sorted(n.items())[:10]), '...' if len(n) > 10 else '')
    gain = sum(m[0]['msg_wmax'] - r['width'] for m in msgs for r in m)
    print('메시지 규칙으로 얻는 여유: 총 %d px (자막당 평균 %.1f px)'
          % (gain, gain / max(1, sum(len(m) for m in msgs))))


def selftest(msgs):
    """실기로 확인된 두 메시지를 재현하는지 대조한다."""
    want = [("Hi, you've reached,", 5, 154), ('hi, berri !', 5, 94)]
    ok = True
    for head, count, wmax in want:
        hit = [m for m in msgs if m[0]['text'].startswith(head)]
        good = len(hit) == 1 and len(hit[0]) == count and hit[0][0]['msg_wmax'] == wmax
        ok &= good
        if hit:
            print('  %-22r 자막 %d (기대 %d)  Wmax %d (기대 %d)  %s'
                  % (head, len(hit[0]), count, hit[0][0]['msg_wmax'], wmax,
                     'OK' if good else '불일치'))
        else:
            print('  %-22r 찾지 못함' % head)
            ok = False
    return ok


def main():
    strings = extract()
    add_budgets(strings)
    report(strings)
    msgs = group_messages(strings)
    report_messages(msgs)
    print()
    print('실기 대조 (구조체 +0x38 로 확인된 메시지):')
    if not selftest(msgs):
        raise SystemExit('메시지 그룹핑이 실기 결과와 다르다')
    out = os.path.join(project.ROOT, 'extract', 'strings.json')
    json.dump(strings, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print()
    print('-> %s' % os.path.relpath(out, project.ROOT))


if __name__ == '__main__':
    main()
