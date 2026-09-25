"""번역 파일 검증 — 넣기 전에 터질 것을 전부 잡는다.

    python tools/trans_check.py [파일...]        (생략하면 trans/*.json 전부)

검사 항목
    1) 인코딩   ko 의 모든 문자가 게임 코드로 바뀌는가
                (한글 음절 11,172자 전부 + 공백 + 줄바꿈 + `. , ! ? -`)
    2) 바이트   인코딩 결과가 그 자막의 바이트 한도 이하인가
                (rzip 블록을 키울 수 없어 원문 길이를 넘으면 안 된다)
    3) 폭       `\n` 으로 나뉜 각 줄이 **그 말풍선의** 폭 한도 이하인가
                말풍선은 메시지에 속한 자막 전체의 최대폭으로 정해진다 (docs/bubble-width.md)
    4) 원문     en 이 코퍼스와 일치하는가 (파일이 낡았거나 손상됐는지)

폰트 메트릭은 **빌드된 한글 ROM** 에서 읽는다 — 자모 진행폭이 원본과 다르므로
원본 ROM 으로 재면 안 된다.
"""
import glob
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import bubble

KR_ROM = os.path.join(project.ROOT, 'work', 'conker_kr.z64')
CODES = os.path.join(project.ROOT, 'work', 'kr_codes.json')


def load_encoder():
    import build_kr as B
    if not os.path.exists(CODES):
        raise SystemExit('work/kr_codes.json 이 없다. 먼저 tools/build_kr.py 를 돌릴 것.')
    kc = json.load(open(CODES))
    part_code = {int(k): v for k, v in kc['part_code'].items()}
    null_code = kc['null_code']
    H, W, parts, triples, sel, assign, used, kind_of, flat = B.build_parts()

    def enc(text, pad_to=None):
        return B.encode_kr(text, part_code, assign, triples,
                           null_code=null_code, pad_to=pad_to)
    return enc


def load_metrics():
    if not os.path.exists(KR_ROM):
        raise SystemExit('work/conker_kr.z64 가 없다. 먼저 tools/build_kr.py 를 돌릴 것.')
    return bubble.Metrics.from_rom(open(KR_ROM, 'rb').read())


def check(paths=None, verbose=True):
    # build_kr 과 같은 곳을 본다 (trans/ 와 trans/번역완/)
    paths = paths or sorted(set(
        glob.glob(os.path.join(project.ROOT, 'trans', 'conker_kr_*.json'))
        + glob.glob(os.path.join(project.ROOT, 'trans', '번역완', 'conker_kr_*.json'))))
    enc = load_encoder()
    m = load_metrics()

    # ★기준은 파일이 아니라 **코퍼스**다. 추출기를 고치면 파일의 en/bytes/width 가 낡는다
    #   (아이콘 포함으로 30개 문자열이 길어졌다). 빌더도 코퍼스 값으로 넣는다.
    import corpus
    strings = _corpus_index(corpus)
    orig = {r['id']: r for r in strings}
    limits = {}
    grp_of = {}                                    # id -> 같은 메시지의 자막 목록
    for grp in corpus.group_messages(strings):     # m 은 폰트 메트릭이므로 가리면 안 된다
        for r in grp:
            limits[r['id']] = r['msg_wmax']
            grp_of[r['id']] = grp

    n_sub = n_done = 0
    errs = []
    allko = {}                                     # 파일을 넘나드는 메시지가 있어 먼저 모은다
    for p in paths:
        doc = json.load(io.open(p, encoding='utf-8'))
        for msg in doc['messages']:
            for s in msg['subs']:
                if s.get('ko'):
                    allko[s['id']] = s['ko']
    for p in paths:
        doc = json.load(io.open(p, encoding='utf-8'))
        name = os.path.basename(p)
        for msg in doc['messages']:
            done = []
            filled = 0                     # ko 를 채운 자막 수 (인코딩 성패와 무관)
            for s in msg['subs']:
                n_sub += 1
                sid, ko = s['id'], s.get('ko', '')
                ref = orig.get(sid)
                if ref is None:
                    errs.append((name, sid, '미상', '코퍼스에 없는 id'))
                    continue
                limit = limits.get(sid, msg['width'])
                budget = ref['bytes']
                if ref['text'] != s['en']:
                    errs.append((name, sid, '낡은원문',
                                 'en/bytes 가 코퍼스와 다르다 — trans_resync.py 로 갱신할 것'))
                if not ko:
                    continue
                n_done += 1
                filled += 1
                try:
                    b = enc(ko)
                except ValueError as ex:
                    errs.append((name, sid, '인코딩', '%s  (%r)' % (ex, ko[:30])))
                    continue
                # ★바이트 한도는 자막이 아니라 **메시지 단위**다 (빌더가 재분배한다).
                #   같은 말풍선의 다른 자막이 짧으면 그 자리를 쓸 수 있다.
                if len(b) > budget:
                    grp = grp_of.get(sid, [ref])
                    tot = sum(x['bytes'] for x in grp)
                    used_b = 0
                    for x in grp:
                        k2 = allko.get(x['id'])
                        if k2 is None:
                            used_b = None
                            break
                        try:
                            used_b += len(enc(k2))
                        except ValueError:
                            used_b = None
                            break
                    if used_b is None or used_b > tot:
                        errs.append((name, sid, '바이트',
                                     '%d B > 한도 %d B (메시지 합계 %s/%d)  (%r)'
                                     % (len(b), budget,
                                        '미완' if used_b is None else used_b, tot, ko[:30])))
                w, h, lines = bubble.measure(b, m)
                if w > limit:
                    errs.append((name, sid, '폭',
                                 '줄폭 %s, 최대 %d > 한도 %d  (%r)'
                                 % (lines, w, limit, ko[:30])))
                done.append((sid, w))
            # 메시지 안에서 번역·미번역이 섞이면 미번역 영문이 자모 글리프로 측정돼
            # 그 말풍선 전체가 부푼다. 부분 번역 자체를 오류로 잡는다.
            # 파일을 넘나드는 메시지는 여기서 부분으로 보일 수 있다 -> 전체 ko 로 판정
            filled = sum(1 for s in msg['subs'] if allko.get(s['id']))
            if filled and filled != len(msg['subs']):
                errs.append((name, msg['id'], '부분번역',
                             '자막 %d개 중 %d개만 번역됨 — 말풍선이 깨진다'
                             % (len(msg['subs']), filled)))

    if verbose:
        print('자막 %d개 중 번역 %d개 (%.1f%%)' % (n_sub, n_done, n_done * 100.0 / max(1, n_sub)))
        if not errs:
            print('오류 없음')
        else:
            import collections
            c = collections.Counter(e[2] for e in errs)
            print('오류 %d건: %s' % (len(errs), dict(c)))
            for e in errs[:40]:
                print('  [%s] %-6s id=%-5s %s' % (e[0], e[2], e[1], e[3]))
            if len(errs) > 40:
                print('  ... 외 %d건' % (len(errs) - 40))
    return errs


def _corpus_index(corpus):
    """코퍼스를 id 순으로 매긴다 (trans_split 과 같은 순서)."""
    strings = corpus.extract(verbose=False)
    corpus.add_budgets(strings)
    corpus.assign_ids(strings)          # ★순서가 아니라 대장에서
    return strings


if __name__ == '__main__':
    args = sys.argv[1:]
    sys.exit(1 if check(args or None) else 0)
