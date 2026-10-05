import json, re
from playwright.sync_api import sync_playwright
B = 'http://127.0.0.1:8802'
errors, posts = [], []
tok = open('/tmp/ocl-e2e/token').read().strip()
def attach(page, tag):
    page.on('console', lambda m: m.type == 'error' and errors.append((tag, m.text)))
    page.on('pageerror', lambda e: errors.append((tag, str(e))))
with sync_playwright() as p:
    br = p.chromium.launch()
    # ---- anonymous desktop: practice mode end to end
    ctx = br.new_context(viewport={'width': 1280, 'height': 900})
    pg = ctx.new_page(); attach(pg, 'anon')
    pg.goto(B + '/quiz/'); assert pg.locator('ul.qcards li').count() == 4
    pg.click('text=Private Pilot Airplane'); pg.wait_for_url('**/quiz/private-pilot/')
    data = json.loads(pg.locator('#qdata').text_content()); ans = {q['stem']: q['a'] for q in data['q']}
    pg.click('button[data-size="10"]')
    wrong_target = 0
    for i in range(10):
        stem = pg.locator('#qapp .qstem').text_content()
        a = ans[stem]
        pick = a if i % 2 == 0 else {'A': 'B', 'B': 'C', 'C': 'A'}[a]   # alternate right / wrong
        wrong_target += pick != a
        pg.click(f'#qapp .qbtn[data-l="{pick}"]')
        assert pg.locator('#qapp .qexp').is_visible()
        assert pg.locator('#qapp .qbtn.right').count() == 1
        if i == 1: pg.screenshot(path='/tmp/agent-quiz-work/shots/practice-desktop.png', full_page=False)
        pg.click('#qapp button.cta')
    score = pg.locator('#qapp .qscore').text_content(); print('score', score)
    assert score.startswith(f'{10 - wrong_target} / 10'), score
    assert pg.locator('#qapp .qrev').count() == wrong_target
    pg.screenshot(path='/tmp/agent-quiz-work/shots/results-desktop.png', full_page=True)
    store = pg.evaluate("localStorage.getItem('ocl:quiz:par')"); print('localStorage entries', len(json.loads(store)))
    print('progress:', pg.locator('#qprog').text_content())
    pg.click('text=Retry these'); assert 'Retrying misses' in pg.locator('#qapp .qmeta').first.text_content()
    assert pg.locator('#qmissed').is_visible(); print('missed button:', pg.locator('#qmissed').text_content())
    # ---- question page with figure
    pg.goto(B + '/quiz/private-pilot/')
    pg.click('ol.qlist a >> nth=11'); pg.wait_for_load_state('load')
    print('qpage title:', pg.title())
    assert pg.locator('details.ans p.ok').count() == 1   # answer present in HTML
    nat = pg.evaluate("Array.from(document.images).filter(i=>i.closest('figure')).map(i=>i.naturalWidth)"); print('fig widths', nat)
    assert nat and all(nat)
    a = pg.get_attribute('#qone', 'data-ans'); wrong = {'A': 'B', 'B': 'C', 'C': 'A'}[a]
    pg.click(f'#qone .qbtn[data-l="{wrong}"]')
    assert pg.locator('#qone .qbtn.wrong').count() == 1 and pg.locator('#qone .qbtn.right').count() == 1
    assert pg.evaluate("document.getElementById('qans').open")
    pg.click('text=Question 13 →'); assert '/q/13-' in pg.url
    pg.click('text=← Question 12'); assert '/q/12-' in pg.url
    ld = json.loads(pg.locator('script[type="application/ld+json"]').text_content()); assert ld['@type'] == 'Quiz'
    # every page type renders (one per test)
    for slug in ['sport-pilot', 'part-107', 'part-103-ultralight']:
        pg.goto(f'{B}/quiz/{slug}/'); n = pg.locator('ol.qlist li').count()
        pg.click('ol.qlist a >> nth=0'); pg.wait_for_load_state('load'); print(slug, n, 'questions;', pg.title())
    ctx.close()
    # ---- signed in: correct answers POST /api/me/quiz
    ctx = br.new_context(viewport={'width': 1280, 'height': 900})
    ctx.add_init_script(f"sessionStorage.setItem('ocl:token', {json.dumps(tok)})")
    def handle(route):
        r = route.request
        if r.method == 'POST' and r.url.endswith('/api/me/quiz'):
            posts.append(r.post_data_json); route.fulfill(status=200, content_type='application/json', body='{"ok":true}')
        else:
            route.fulfill(status=200, content_type='application/json', body='{}')
    ctx.route('https://app.openchecklists.net/**', handle)
    pg = ctx.new_page(); attach(pg, 'signedin')
    pg.goto(B + '/quiz/part-107/#practice-10')
    data = json.loads(pg.locator('#qdata').text_content()); ans = {q['stem']: q['a'] for q in data['q']}
    for i in range(3):
        pg.click(f'#qapp .qbtn[data-l="{ans[pg.locator("#qapp .qstem").text_content()]}"]'); pg.click('#qapp button.cta')
    pg.wait_for_timeout(500); print('POST /api/me/quiz bodies:', posts)
    assert len(posts) == 3
    ctx.close()
    # ---- mobile layout
    ctx = br.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    pg = ctx.new_page(); attach(pg, 'mobile')
    for url, shot in [('/quiz/', 'm-index'), ('/quiz/private-pilot/#practice-20', 'm-practice'),
                      ('/quiz/sport-pilot/q/16-' , None)]:
        if shot is None:
            pg.goto(B + '/quiz/sport-pilot/'); pg.click('ol.qlist a >> nth=15'); pg.wait_for_load_state('load'); shot = 'm-question-fig'
        else:
            pg.goto(B + url)
        over = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        print(shot, 'horizontal overflow px:', over); assert over <= 1, over
        pg.screenshot(path=f'/tmp/agent-quiz-work/shots/{shot}.png', full_page=False)
    ctx.close(); br.close()
print('console errors:', errors)
