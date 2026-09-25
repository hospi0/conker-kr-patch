"""번역 파일의 en / bytes / width 를 코퍼스 현재 값으로 갱신한다. ko 는 건드리지 않는다.

    python tools/trans_resync.py

추출기를 고치면 문자열의 범위가 달라진다 — 실제로 버튼 아이콘·검열 기호를 텍스트로
인정하자 **기존 문자열 30개가 더 길어졌다**(`'press '` -> `'press ©'`).
그러면 파일의 en·bytes·width 가 낡아 검사 결과가 어긋난다.

★id 는 대장(extract/ids.json)에 고정돼 있으므로 이 갱신으로 번역이 어긋나지 않는다.
  다만 **원문이 길어진 항목은 번역도 다시 손봐야 한다** — 뒤에 붙은 원문이 그대로
  영문으로 남으면 그 부분이 자모 글리프로 깨져 보인다.
"""
import glob
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project
import corpus


def main():
    strings = corpus.extract(verbose=False)
    corpus.add_budgets(strings)
    corpus.assign_ids(strings)
    byid = {r['id']: r for r in strings}
    limits = {}
    for m in corpus.group_messages(strings):
        for r in m:
            limits[r['id']] = r['msg_wmax']

    paths = sorted(set(glob.glob(os.path.join(project.ROOT, 'trans', 'conker_kr_*.json'))
                       + glob.glob(os.path.join(project.ROOT, 'trans', '번역완',
                                                'conker_kr_*.json'))))
    changed = []
    dead = []
    for p in paths:
        doc = json.load(io.open(p, encoding='utf-8'))
        dirty = False
        for msg in doc['messages']:
            # ★코퍼스에서 사라진 id 는 지운다.
            #   문자열이 길어지면서 **뒤 문자열을 흡수**하면 그 id 가 없어진다
            #   (아이콘 포함으로 34개가 앞 문자열에 먹혔다). 남겨두면 「부분번역」으로 오인된다.
            gone = [s for s in msg['subs'] if s['id'] not in byid]
            if gone:
                msg['subs'] = [s for s in msg['subs'] if s['id'] in byid]
                dead.extend((os.path.basename(p), s['id'], s.get('ko', '')) for s in gone)
                dirty = True
            ws = []
            for s in msg['subs']:
                r = byid.get(s['id'])
                if r is None:
                    continue
                if s['en'] != r['text'] or s['bytes'] != r['bytes']:
                    if s.get('ko'):
                        changed.append((os.path.basename(p), s['id'],
                                        s['bytes'], r['bytes']))
                    s['en'] = r['text']
                    s['bytes'] = r['bytes']
                    dirty = True
                ws.append(limits.get(s['id'], msg['width']))
            if ws and msg['width'] != min(ws):
                msg['width'] = min(ws)
                dirty = True
        if dirty:
            with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
                f.write(json.dumps(doc, ensure_ascii=False, indent=1))
            print('갱신 %s' % os.path.relpath(p, project.ROOT))
    if dead:
        print()
        print('흡수되어 사라진 항목 %d개 제거 (앞 문자열 번역이 그 내용을 포함해야 한다):' % len(dead))
        for f, i, k in dead[:10]:
            print('   [%s] id=%-5d ko=%r' % (f, i, k[:24]))
        if len(dead) > 10:
            print('   ... 외 %d개' % (len(dead) - 10))
    if changed:
        print()
        print('★원문이 바뀐 **번역 완료** 항목 %d개 — 번역을 다시 볼 것:' % len(changed))
        for f, i, a, b in changed:
            print('   [%s] id=%-5d %d B -> %d B' % (f, i, a, b))


if __name__ == '__main__':
    main()
