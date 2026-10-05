import json, re, os, sys, shutil
import pymupdf
sys.path.insert(0, '/tmp/agent-quiz-work')
REPO = '/workspace/openchecklists/openchecklists'
OUT = REPO + '/quiz'
os.makedirs(OUT + '/figures', exist_ok=True)
raw = json.load(open('/tmp/agent-quiz-work/raw.json'))
BASE = 'https://www.faa.gov/sites/faa.gov/files/training_testing/testing/test_questions/'
SUPP_URL = 'https://www.faa.gov/sites/faa.gov/files/training_testing/testing/supplements/sport_rec_private_akts.pdf'
TESTS = {
 'par': dict(slug='private-pilot', code='PAR', title='Private Pilot Airplane', short='FAA Private Pilot',
   source='Private Pilot-Airplane (PAR) Sample Questions', url=BASE + 'par_questions.pdf'),
 'spa': dict(slug='sport-pilot', code='SPA', title='Sport Pilot Airplane', short='FAA Sport Pilot',
   source='Sport Pilot Airplane (SPA) Sample Questions', url=BASE + 'spa_questions.pdf'),
 'uag': dict(slug='part-107', code='UAG', title='Remote Pilot (Part 107)', short='FAA Part 107 Remote Pilot',
   source='Unmanned Aircraft General (UAG) Sample Questions', url=BASE + 'uag_questions.pdf'),
}
PHAK_CH = {1:'Introduction to Flying',2:'Aeronautical Decision-Making',3:'Aircraft Construction',4:'Principles of Flight',
 5:'Aerodynamics of Flight',6:'Flight Controls',7:'Aircraft Systems',8:'Flight Instruments',9:'Flight Manuals and Other Documents',
 10:'Weight and Balance',11:'Aircraft Performance',12:'Weather Theory',13:'Aviation Weather Services',14:'Airport Operations',
 15:'Airspace',16:'Navigation',17:'Aeromedical Factors'}
AFH_CH = {3:'Basic Flight Maneuvers',9:'Approaches and Landings',18:'Emergency Procedures'}

def cite(c):
    k = c[0]
    if k == 'cfr':
        return {'label': f'14 CFR § {c[1]}', 'url': f'https://www.ecfr.gov/current/title-14/section-{c[1]}'}
    if k == 'aim':
        p = c[1].split('-')
        return {'label': f'AIM {c[1]}', 'url': f'https://www.faa.gov/air_traffic/publications/atpubs/aim_html/chap{p[0]}_section_{p[1]}.html'}
    if k == 'phak':
        ch = int(c[1].split('-')[0])
        where = f'p. {c[1]}' if '-' in c[1] else f'ch. {ch}'
        return {'label': f"Pilot's Handbook of Aeronautical Knowledge (FAA-H-8083-25C), {where}, {PHAK_CH[ch]}",
                'doc': 'faa-phak', 'q': c[2]}
    if k == 'rmh':
        return {'label': f'Risk Management Handbook (FAA-H-8083-2A), p. {c[1]}', 'doc': 'faa-rmh', 'q': c[2]}
    if k == 'afh':
        ch = int(c[1])
        return {'label': f'Airplane Flying Handbook (FAA-H-8083-3C), ch. {ch}, {AFH_CH[ch]}',
                'url': 'https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/airplane_handbook'}
    raise ValueError(c)

def slugify(stem):
    s = re.sub(r'^\(Refer to [^)]*\)\s*', '', stem)
    s = re.sub(r"[`'’]", '', s.lower())
    words = re.findall(r'[a-z0-9]+', s)
    stop = {'the','a','an','of','to','is','are','be','in','on','at','and','or','for','with','your','you','what','which','that','this','by','it','its'}
    keep = [w for w in words if w not in stop][:7]
    return '-'.join(keep) or 'question'

# --- figures: render from the public-domain FAA-CT-8080-2H supplement
supp = pymupdf.open('/tmp/agent-quiz-src/sport_rec_private_akts.pdf')
fig_pages, fig_titles = {}, {}
for i in range(34, supp.page_count):
    t = supp[i].get_text(); m = re.search(r'Figure\s+(\d+)\.\s+([^\n]+)', t)
    if m and int(m.group(1)) not in fig_pages:
        fig_pages[int(m.group(1))] = i; fig_titles[int(m.group(1))] = m.group(2).strip()
ROTATE = {24, 25, 35, 38, 72}   # printed sideways in the supplement
figures = {}
def figure(n):
    key = f'fig{n}'
    if key in figures: return key
    p = supp[fig_pages[n]]
    r = pymupdf.Rect()
    for b in p.get_text('blocks'):
        if re.fullmatch(r'\s*(\d+-\d+|Appendix \d)\s*', b[4]): continue
        if re.search(r'Figure \d+\.|not to scale', b[4]): continue
        r |= pymupdf.Rect(b[:4])
    for im in p.get_images(full=True):
        for rr in p.get_image_rects(im[0]): r |= rr
    for dr in p.get_drawings(): r |= dr['rect']
    r = (r + (-4, -4, 4, 4)) & p.rect
    mat = pymupdf.Matrix(200/72, 200/72).prerotate(90 if n in ROTATE else 0)
    pix = p.get_pixmap(matrix=mat, clip=r)
    open(f'{OUT}/figures/{key}.jpg', 'wb').write(pix.tobytes('jpeg', jpg_quality=70))
    figures[key] = {'file': f'{key}.jpg', 'w': pix.width, 'h': pix.height,
                    'caption': f'FAA-CT-8080-2H, Figure {n}. {fig_titles[n].rstrip(".")}.',
                    'source': SUPP_URL}
    return key
def inline_fig(test, n):
    # par 48/49 use small images embedded in the FAA sample-question PDF itself
    key = f'{test}{n}'
    d = pymupdf.open(f'/tmp/agent-quiz-src/{test}_questions.pdf'); p = d[11]
    ims = p.get_images(full=True); idx = {48: 0, 49: 1}[n]
    x = d.extract_image(ims[idx][0])
    open(f'{OUT}/figures/{key}.jpg', 'wb').write(x['image'])
    figures[key] = {'file': f'{key}.jpg', 'w': x['width'], 'h': x['height'],
                    'caption': f'Image from the FAA {test.upper()} sample questions, question {n}.', 'source': TESTS[test]['url']}
    return key

summary = {}
for test, meta in TESTS.items():
    A = __import__(f'answers_{test}')
    qs, skipped = [], []
    for q in raw[test]:
        n = q['n']
        if n in A.SKIP or n not in A.P:
            skipped.append({'n': n, 'stem': q['stem'], 'reason': A.SKIP.get(n, 'No grounded answer authored.')}); continue
        ans, expl, cites = A.P[n]
        choices = A.FIX.get(n, q['choices'])
        assert set(choices) == {'A','B','C'} and all(choices.values()), (test, n)
        figs = []
        f = A.FIG.get(n)
        if f:
            if f.startswith(test): figs.append(inline_fig(test, int(f[len(test):])))
            else: figs += [figure(int(x)) for x in f.split(',')]
        elif re.search(r'figure', q['stem'], re.I): raise SystemExit(f'figure missing {test}{n}')
        qs.append({'n': n, 'slug': slugify(q['stem']), 'stem': q['stem'], 'choices': choices, 'answer': ans,
                   'explanation': expl, 'cites': [cite(c) for c in cites], 'figures': figs, 'code': q.get('acs')})
    out = {'id': test, **meta, 'rights': 'public_domain', 'basis': 'us_government_work',
           'note': 'Questions and choices are reproduced from the FAA sample-question document (a U.S. Government work). '
                   'The FAA document has no answer key: answers and explanations are written by OpenChecklists and cite FAA sources.',
           'questions': qs, 'skipped': skipped}
    json.dump(out, open(f'{OUT}/{test}.json', 'w'), indent=1, ensure_ascii=False)
    summary[test] = (len(qs), len(skipped))

# Part 103 primer: original questions; rotate the correct choice so it is not always A
from answers_p103 import Q
qs = []
for i, (stem, ch, ans, expl, cites, q) in enumerate(Q):
    vals = [ch['A'], ch['B'], ch['C']]; correct = ch[ans]
    k = i % 3; vals = vals[-k:] + vals[:-k] if k else vals
    letters = dict(zip('ABC', vals))
    qs.append({'n': i + 1, 'slug': slugify(stem), 'stem': stem, 'choices': letters,
               'answer': next(l for l, v in letters.items() if v == correct), 'explanation': expl,
               'cites': [cite(c) for c in cites], 'figures': [], 'code': None})
json.dump({'id': 'p103', 'slug': 'part-103-ultralight', 'code': '103', 'title': 'Part 103 Ultralight Primer',
           'short': 'Part 103 ultralight', 'source': '14 CFR Part 103 — Ultralight Vehicles',
           'url': 'https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-103',
           'rights': 'original', 'note': 'Original OpenChecklists questions written from the text of 14 CFR Part 103. '
           'Not an FAA test: Part 103 requires no knowledge test.', 'questions': qs, 'skipped': []},
          open(f'{OUT}/p103.json', 'w'), indent=1, ensure_ascii=False)
summary['p103'] = (len(qs), 0)
json.dump(figures, open(f'{OUT}/figures.json', 'w'), indent=1, ensure_ascii=False)
print(summary, len(figures), 'figures')
