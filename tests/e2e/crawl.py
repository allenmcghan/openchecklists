"""Crawl every page type of a build at BASE on desktop+mobile; report console/page errors,
failed requests, horizontal overflow, stuck loaders, and SPA-fallback pages."""
import asyncio, json, os, re, sys
from playwright.async_api import async_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8788'
API_LOCAL = os.environ.get('API_LOCAL')  # e.g. http://127.0.0.1:8787 → reroute app.openchecklists.net
SIGNED = os.environ.get('SIGNED') == '1'
root = '/workspace/openchecklists/openchecklists/build/site'
cs = sorted(os.listdir(root + '/c'))
pages = ['/', '/catalogue.html', '/airports.html', '/planner.html', '/training.html', '/search.html',
         '/charts.html', '/projects.html', '/editor.html', '/contribute.html', '/about.html', '/terms.html',
         '/privacy.html', '/takedown.html', '/contact.html', '/profile.html',
         '/airport/?id=KJFK', '/airport/?id=KOSH', '/airport/?id=00C', '/airport/?id=ZZZZ', '/airport/?id=OSH',
         '/checklist/?id=doesnotexist', '/plan/?id=ocl-doesnotexist', '/catalogue.html?q=cessna',
         '/search.html?q=density+altitude', '/editor.html?fork=' + cs[0],
         '/about-us.html', '/quiz/', '/quiz/private-pilot/', '/quiz/part-107/', '/quiz/part-103-ultralight/',
         '/aircraft/', '/aircraft/cessna-172/', '/us-airports/', '/us-airports/wi/', '/airports-near/oshkosh-wi/',
         '/airport/KOSH', '/airport/00A', '/airport/W52'] + \
        ['/quiz/private-pilot/q/' + d + '/' for d in sorted(os.listdir(root + '/quiz/private-pilot/q'))[:3]] + \
        ['/f/' + f + '/' for f in sorted(os.listdir(root + '/f'))] + ['/c/' + c + '/' for c in cs[::18]]
LOADING = re.compile(r'Loading[^.\n]{0,40}…|Loading\.\.\.|Fetching', re.I)
async def run():
    out = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        for vp, size in (('D', (1366, 900)), ('M', (390, 844))):
            ctx = await b.new_context(viewport={'width': size[0], 'height': size[1]}, is_mobile=vp == 'M')
            await ctx.add_init_script("try{localStorage.setItem('umami.disabled','1')}catch(e){}")  # keep test runs out of analytics
            if API_LOCAL:
                async def reroute(route, request=None, ctx=ctx):
                    rq = route.request
                    r = await ctx.request.fetch(rq.url.replace('https://app.openchecklists.net', API_LOCAL),
                                                method=rq.method, headers=rq.headers, data=rq.post_data_buffer,
                                                fail_on_status_code=False)
                    await route.fulfill(response=r)
                await ctx.route('https://app.openchecklists.net/**', reroute)
            if SIGNED:
                tok = open('/tmp/ocl-e2e/token').read().strip()
                await ctx.add_init_script(f"try{{sessionStorage.setItem('ocl:token',{json.dumps(tok)})}}catch(e){{}}")
            for u in pages:
                pg = await ctx.new_page(); cons, perr, fails = [], [], []
                pg.on('console', lambda m: cons.append(f'{m.type}: {m.text[:200]}') if m.type in ('error', 'warning') and 'GL Driver' not in m.text and 'GPU stall' not in m.text else None)
                pg.on('pageerror', lambda e: perr.append(str(e)[:200]))
                pg.on('requestfailed', lambda r: fails.append(f'{r.url[:120]} {r.failure}'))
                pg.on('response', lambda r: fails.append(f'HTTP {r.status} {r.url[:120]}') if r.status >= 400 else None)
                try:
                    resp = await pg.goto(BASE + u, wait_until='domcontentloaded', timeout=30000)
                    await pg.wait_for_timeout(6000)
                    title = await pg.title()
                    txt = await pg.inner_text('body')
                    sw, iw = await pg.evaluate('[document.documentElement.scrollWidth, innerWidth]')
                    stuck = sorted(set(LOADING.findall(txt)))
                    if vp == 'D' and u.startswith(('/airport/?id=KJFK', '/c/')) or u == '/':
                        await pg.screenshot(path=f'/tmp/ocl-e2e/shots/{vp}{re.sub(r"[^a-zA-Z0-9]+", "_", u)[:60]}.png', full_page=False)
                    out.append({'vp': vp, 'u': u, 'status': resp.status if resp else None, 'title': title[:80],
                                'overflow': sw - iw if sw > iw + 2 else 0, 'stuck': stuck, 'cons': cons, 'perr': perr, 'fails': fails})
                except Exception as e:
                    out.append({'vp': vp, 'u': u, 'exc': str(e)[:200]})
                await pg.close()
            await ctx.close()
        await b.close()
    json.dump(out, open('/tmp/ocl-e2e/crawl.json', 'w'), indent=1)
    for r in out:
        bad = {k: r[k] for k in ('exc', 'overflow', 'stuck', 'cons', 'perr', 'fails') if r.get(k)}
        if bad: print(r['vp'], r['u'], '|', r.get('title', ''), '|', json.dumps(bad)[:600])
    print('pages checked:', len(out))
asyncio.run(run())
