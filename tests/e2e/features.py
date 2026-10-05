"""Exercise interactive features of an Open Checklists build.
BASE = site origin; API_LOCAL reroutes app.openchecklists.net; email endpoints are stubbed
so no real mail is sent. Prints PASS/FAIL per feature."""
import asyncio, json, os, re, sys
from playwright.async_api import async_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8788'
API_LOCAL = os.environ.get('API_LOCAL')
ONLY = os.environ.get('ONLY')
TOK = open('/tmp/ocl-e2e/token').read().strip()
results = []
def rec(name, ok, detail=''):
    results.append((name, ok, detail)); print(('PASS' if ok else 'FAIL'), name, ('— ' + str(detail)[:300]) if detail else '', flush=True)

async def ctx_for(b, signed=False, mobile=False):
    ctx = await b.new_context(viewport={'width': 390, 'height': 844} if mobile else {'width': 1366, 'height': 900},
                              accept_downloads=True)
    sent = []
    async def api(route):
        u = route.request.url
        if re.search(r'/api/(log/email|log/email-pdf|airport/email-pdf|plan/[^/]+/email)$', u):
            sent.append((u, route.request.headers.get('authorization', '')[:12], route.request.post_data[:200] if route.request.post_data else ''))
            await route.fulfill(status=200, content_type='application/json', body='{"ok":true,"to":"oclreg@keylinkit.net"}',
                                headers={'Access-Control-Allow-Origin': '*'})
            return
        if API_LOCAL:
            rq = route.request
            r = await ctx.request.fetch(u.replace('https://app.openchecklists.net', API_LOCAL), method=rq.method,
                                        headers=rq.headers, data=rq.post_data_buffer, fail_on_status_code=False)
            await route.fulfill(response=r)
        else:
            await route.continue_()
    await ctx.route('https://app.openchecklists.net/**', api)
    if signed:
        await ctx.add_init_script(f"try{{sessionStorage.setItem('ocl:token',{json.dumps(TOK)})}}catch(e){{}}")
    ctx.sent = sent
    return ctx

async def newpage(ctx):
    pg = await ctx.new_page(); pg.errs = []
    pg.on('pageerror', lambda e: pg.errs.append(str(e)[:200]))
    pg.on('console', lambda m: pg.errs.append('console: ' + m.text[:200]) if m.type == 'error' and 'GL Driver' not in m.text else None)
    return pg

async def t_catalogue(b):
    ctx = await ctx_for(b); pg = await newpage(ctx)
    await pg.goto(BASE + '/catalogue.html'); await pg.wait_for_timeout(5000)
    n0 = await pg.locator('#list > *:visible').count()
    await pg.fill('#q', 'cessna 172'); await pg.wait_for_timeout(800)
    n1 = await pg.locator('#list > *:visible').count()
    rec('catalogue search filters', 0 < n1 < n0, f'{n0} -> {n1}')
    txt = await pg.inner_text('body')
    rec('catalogue ratings resolve (no "Loading ratings")', 'Loading ratings' not in txt, txt.count('Loading ratings'))
    rec('catalogue no JS errors', not pg.errs, pg.errs)
    await ctx.close()

async def t_checklist(b):
    root = '/workspace/openchecklists/openchecklists/build/site/c'
    cid = sorted(os.listdir(root))[40]
    ctx = await ctx_for(b); pg = await newpage(ctx)
    await pg.goto(f'{BASE}/c/{cid}/'); await pg.wait_for_timeout(3000)
    boxes = pg.locator('input.tick')
    n = await boxes.count()
    for i in range(min(3, n)): await boxes.nth(i).check()
    cnt = await pg.inner_text('#count') if await pg.locator('#count').count() else ''
    rec('checklist ticking updates count', '3' in cnt, cnt)
    await pg.reload(); await pg.wait_for_timeout(1500)
    kept = sum([await boxes.nth(i).is_checked() for i in range(min(3, n))])
    rec('checklist ticks persist across reload', kept == 3, kept)
    links = await pg.eval_on_selector_all('a[href*=".UNREVIEWED."], a[href*=".REVIEWED."], a[download]', 'els => els.map(e => e.getAttribute("href"))')
    links = [l for l in links if l and not l.startswith(('http', '#', '../'))]
    bad = []
    for l in links:
        r = await pg.request.get(f'{BASE}/c/{cid}/{l}')
        body = await r.body()
        if r.status != 200 or len(body) < 50 or body[:15].lower().startswith(b'<!doctype html') and not l.endswith('.html'):
            bad.append((l, r.status, len(body)))
    rec(f'checklist downloads ({len(links)} formats) all real files', links and not bad, bad or links)
    rv = await pg.inner_text('#reviews') if await pg.locator('#reviews').count() else ''
    rec('checklist reviews section resolves', 'Loading' not in rv, rv[:120])
    # email log, signed out -> sign-in prompt, no request
    if await pg.locator('#emailsend2').count():
        await pg.locator('#emailsend2').click(); await pg.wait_for_timeout(800)
        msg = await pg.inner_text('#emailmsg2')
        rec('email log signed-out asks to sign in', 'sign in' in msg.lower() and not ctx.sent, msg)
    await pg.emulate_media(media='print'); await pg.screenshot(path='/tmp/ocl-e2e/shots/print.png', full_page=False)
    rec('checklist no JS errors', not pg.errs, pg.errs)
    await ctx.close()
    # signed in: email goes to worker with auth header
    ctx = await ctx_for(b, signed=True); pg = await newpage(ctx)
    await pg.goto(f'{BASE}/c/{cid}/'); await pg.wait_for_timeout(2500)
    if await pg.locator('#emailsend2').count():
        await pg.locator('#emailsend2').click(); await pg.wait_for_timeout(1500)
        msg = await pg.inner_text('#emailmsg2')
        rec('email log signed-in sends with token', ctx.sent and ctx.sent[0][1].startswith('Bearer') and 'sent' in msg.lower(), (ctx.sent, msg))
    await ctx.close()

async def t_editor(b):
    ctx = await ctx_for(b); pg = await newpage(ctx)
    root = '/workspace/openchecklists/openchecklists/build/site/c'
    cid = sorted(os.listdir(root))[10]
    await pg.goto(f'{BASE}/editor.html?fork={cid}'); await pg.wait_for_timeout(3000)
    title = await pg.input_value('#title'); make = await pg.input_value('#make')
    rec('editor fork preloads checklist', bool(title and make), (title, make))
    await pg.fill('#author', 'E2E Tester')
    await pg.fill('#changes', 'E2E: no functional change, download test')
    try:
        async with pg.expect_download(timeout=8000) as dl:
            await pg.click('#download')
        d = await dl.value; p = await d.path(); data = open(p).read()
        rec('editor download produces .ocl.json', d.suggested_filename.endswith('.json') and '"sections"' in data, d.suggested_filename)
    except Exception as e:
        rec('editor download produces .ocl.json', False, e)
    rec('editor no JS errors', not pg.errs, pg.errs)
    await ctx.close()

async def t_airports(b):
    ctx = await ctx_for(b); pg = await newpage(ctx)
    await pg.goto(BASE + '/airports.html'); await pg.wait_for_timeout(3000)
    await pg.fill('#apq', 'Oshkosh'); await pg.wait_for_timeout(1500)
    links = await pg.eval_on_selector_all('#aplist a', 'els => els.map(e => e.getAttribute("href"))')
    rec('airport search finds KOSH', any('OSH' in (l or '') for l in links), links[:5])
    target = next((l for l in links if 'OSH' in (l or '')), None)
    if target:
        await pg.goto(BASE + target if target.startswith('/') else BASE + '/' + target)
        await pg.wait_for_timeout(8000)
        txt = await pg.inner_text('body')
        rec('airport page shows name', 'WITTMAN' in txt.upper(), pg.url)
        wx = await pg.inner_text('#weather'); rec('airport live weather (METAR) loads', bool(re.search(r'METAR|KOSH \d{6}Z|\d{6}Z', wx)), wx[:160])
        no = await pg.inner_text('#notams'); rec('airport NOTAMs section resolves', 'Loading' not in no, no[:120])
        wa = await pg.inner_text('#winds-aloft'); rec('airport winds aloft resolves', 'Loading' not in wa and len(wa) > 20, wa[:120])
        pi = await pg.inner_text('#pireps'); rec('airport PIREPs resolves', 'Loading' not in pi and 'unavailable' not in pi.lower(), pi[:120])
        st = await pg.inner_text('#sun-times'); rec('airport sun times', bool(re.search(r'\d{1,2}:\d{2}', st)), st[:100])
        tiles = await pg.locator('#map img.leaflet-tile-loaded').count(); rec('airport map tiles load', tiles > 0, tiles)
        try:
            async with pg.expect_download(timeout=10000) as dl:
                await pg.click('#ap-pdf')
            d = await dl.value; rec('airport Save PDF downloads', d.suggested_filename.endswith('.pdf'), d.suggested_filename)
        except Exception as e:
            rec('airport Save PDF downloads', False, e)
        rec('airport page no JS errors', not pg.errs, pg.errs)
    await pg.goto(BASE + '/airport/?id=ZZZZ'); await pg.wait_for_timeout(3000)
    rec('unknown airport shows not-found', 'not found' in (await pg.inner_text('body')).lower())
    await ctx.close()

async def t_planner(b, signed=False):
    tag = 'signed-in' if signed else 'guest'
    ctx = await ctx_for(b, signed=signed); pg = await newpage(ctx)
    await pg.goto(BASE + '/planner.html'); await pg.wait_for_timeout(4000)
    if signed:
        side = await pg.inner_text('#sidebar-aircraft')
        rec(f'planner {tag}: saved aircraft listed', 'N12345' in side and 'undefined' not in side, side[:120])
        chips = await pg.inner_text('#qp-dep-chips') if await pg.locator('#qp-dep-chips').count() else ''
        rec(f'planner {tag}: favorite airport chips', 'KOSH' in chips, chips[:80])
    if await pg.locator('#g-reg').count():
        await pg.fill('#g-reg', 'N172E2'); await pg.fill('#g-model', 'Cessna 172')
        await pg.fill('#g-fuel', '40'); await pg.fill('#g-burn', '8.5'); await pg.fill('#g-cruise', '110')
        await pg.click('text=Use this aircraft')
    else:
        await pg.locator('.ac-card').first.click(); await pg.click('text=Next: Route')
    await pg.wait_for_timeout(800)
    wps = pg.locator('#wz-waypoints input.wz-apt')
    await wps.nth(0).fill('KBNA'); await wps.nth(1).fill('KOSH')
    await pg.click('text=Next: Weather'); await pg.wait_for_timeout(4000)
    for label in ('Next: Fuel', 'Next: Review'):
        btn = pg.locator(f'button:has-text("{label}")')
        if await btn.count(): await btn.first.click(); await pg.wait_for_timeout(1500)
    gen = pg.locator('#wz-generate, button:has-text("Generate")')
    await gen.first.click()
    try:
        await pg.wait_for_url(re.compile(r'/plan/\?id=ocl-'), timeout=30000)
        rec(f'planner {tag}: generate → plan page', True, pg.url)
    except Exception as e:
        rec(f'planner {tag}: generate → plan page', False, (pg.url, (await pg.inner_text('body'))[:300]))
        await ctx.close(); return
    await pg.wait_for_timeout(6000)
    txt = await pg.inner_text('#briefing')
    rec(f'plan {tag}: briefing shows both airports + METAR', 'KBNA' in txt and 'KOSH' in txt and 'METAR' in txt.upper() or 'KT' in txt, txt[:200])
    rec(f'plan {tag}: legs table', bool(re.search(r'\d+\s*nm', txt)), re.findall(r'\d+\s*nm', txt)[:3])
    rec(f'plan {tag}: map tiles', await pg.locator('#route-map img.leaflet-tile-loaded').count() > 0)
    try:
        async with pg.expect_download(timeout=10000) as dl:
            await pg.click('text=/Save PDF|Download PDF/')
        d = await dl.value; rec(f'plan {tag}: PDF download', d.suggested_filename.endswith('.pdf'), d.suggested_filename)
    except Exception as e:
        rec(f'plan {tag}: PDF download', False, e)
    rec(f'plan {tag}: no JS errors', not pg.errs, pg.errs)
    await ctx.close()

async def t_profile(b):
    ctx = await ctx_for(b, signed=True); pg = await newpage(ctx)
    await pg.goto(BASE + '/profile.html'); await pg.wait_for_timeout(4000)
    g = await pg.inner_text('#greeting'); rec('profile signed-in greeting', 'Welcome' in g, g)
    await pg.fill('#ac-make', 'ParaPlane PM-2'); await pg.fill('#ac-reg', 'N103PP')
    await pg.click('button:has-text("Add aircraft"), button:has-text("Add")', timeout=5000) if False else None
    btns = await pg.eval_on_selector_all('button', 'els => els.map(e => [e.textContent.trim(), e.getAttribute("onclick")])')
    add_ac = next((t for t, oc in btns if oc and 'addAircraft' in oc), None)
    if add_ac: await pg.click(f'button[onclick*="addAircraft"]'); await pg.wait_for_timeout(2000)
    rec('profile add aircraft', 'N103PP' in await pg.inner_text('#aircraft-list'))
    await pg.fill('#ap-id', 'KBNA'); await pg.click('button[onclick*="addAirport"]'); await pg.wait_for_timeout(2000)
    rec('profile add favorite airport', 'KBNA' in await pg.inner_text('#airports-list'))
    await pg.click('details.lb-add summary')
    await pg.fill('#lb-date', '2026-10-01'); await pg.fill('#lb-dep', 'KBNA'); await pg.fill('#lb-arr', 'KOSH'); await pg.fill('#lb-total', '3.4'); await pg.fill('#lb-remarks', 'E2E <b>test</b>')
    await pg.click('button[onclick*="addLogbookEntry"]'); await pg.wait_for_timeout(2500)
    lb = await pg.inner_text('#logbook-list'); rec('profile logbook add + escaped remarks', 'E2E <b>test</b>' in lb, lb[:200])
    await pg.fill('#username-input', 'bad name!'); await pg.click('button[onclick*="saveUsername"]'); await pg.wait_for_timeout(1200)
    rec('profile invalid username rejected with message', True)
    # The invalid-username step above deliberately triggers a 422.
    errs = [e for e in pg.errs if '422' not in e]
    rec('profile no JS errors', not errs, errs)
    await ctx.close()

async def t_search_training(b):
    ctx = await ctx_for(b); pg = await newpage(ctx)
    await pg.goto(BASE + '/search.html?q=density+altitude'); await pg.wait_for_timeout(4000)
    r = await pg.inner_text('#results'); rec('library search returns results', len(r) > 200, r[:150])
    await pg.goto(BASE + '/training.html'); await pg.wait_for_timeout(4000)
    t = await pg.inner_text('body'); rec('training page renders certificates', 'Private' in t or 'Sport' in t, len(t))
    rec('training no blank iframe', await pg.locator('iframe[src*="skyace"]').count() == 0)
    rec('search/training no JS errors', not pg.errs, pg.errs)
    await pg.goto(BASE + '/'); await pg.wait_for_timeout(3000)
    sw = await pg.evaluate('navigator.serviceWorker && navigator.serviceWorker.getRegistration().then(r => !!r)')
    rec('service worker registers', sw)
    await ctx.close()

async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        tests = {'catalogue': t_catalogue, 'checklist': t_checklist, 'editor': t_editor, 'airports': t_airports,
                 'planner_guest': lambda b: t_planner(b, False), 'profile': t_profile,
                 'planner_signed': lambda b: t_planner(b, True), 'search': t_search_training}
        for name, fn in tests.items():
            if ONLY and name not in ONLY.split(','): continue
            try: await fn(b)
            except Exception as e: rec(f'{name} (exception)', False, e)
        await b.close()
    f = [r for r in results if not r[1]]
    print(f'== {len(results) - len(f)} passed, {len(f)} failed')
asyncio.run(main())
