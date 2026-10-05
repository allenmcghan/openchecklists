import re, json, pymupdf
SRC = {
 'par': ('Private Pilot Airplane (PAR) Sample Questions', 'https://www.faa.gov/sites/faa.gov/files/training_testing/testing/test_questions/par_questions.pdf'),
 'spa': ('Sport Pilot Airplane (SPA) Sample Questions', 'https://www.faa.gov/sites/faa.gov/files/training_testing/testing/test_questions/spa_questions.pdf'),
 'uag': ('Unmanned Aircraft General (UAG) Sample Questions', 'https://www.faa.gov/sites/faa.gov/files/training_testing/testing/test_questions/uag_questions.pdf'),
}
out = {}
for k in SRC:
    d = pymupdf.open(f'/tmp/agent-quiz-src/{k}_questions.pdf')
    lines = []
    for pno, p in enumerate(d):
        for ln in p.get_text().splitlines():
            ln = ln.strip()
            if ln: lines.append((pno + 1, ln))
    qs = []; cur = None; mode = None
    for pno, ln in lines:
        m = re.match(r'^(\d+)\.(?:\s+(.*))?$', ln)
        if m and int(m.group(1)) == (qs[-1]['n'] + 1 if qs else 1):
            cur = {'n': int(m.group(1)), 'stem': m.group(2) or '', 'choices': {}, 'page': pno}
            qs.append(cur); mode = 'stem'; continue
        if cur is None: continue
        if re.fullmatch(r'[ABC]\.', ln):
            mode = ln[0]; cur['choices'][mode] = ''; continue
        if ln.startswith('Metadata:'):
            mm = re.search(r'(?:ACS|LSC)Code\s*:\s*(\S+)', ln); cur['acs'] = mm.group(1) if mm else None
            mode = 'meta'; continue
        if mode == 'stem': cur['stem'] += ' ' + ln
        elif mode in 'ABC' and mode: cur['choices'][mode] = (cur['choices'][mode] + ' ' + ln).strip()
        # page numbers / stray lines after meta ignored
    for q in qs:
        q['stem'] = re.sub(r'\s+', ' ', q['stem']).strip()
    out[k] = qs
    print(k, len(qs), sum(1 for q in qs if re.search(r'figure|FAA-CT', q['stem'], re.I)))
json.dump(out, open('/tmp/agent-quiz-work/raw.json', 'w'), indent=1)
