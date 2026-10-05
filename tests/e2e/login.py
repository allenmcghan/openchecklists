"""Log in to openchecklists.net (or BASE) as the OCL Tester; save storage state + token claims."""
import os, re, sys, asyncio, json, base64, subprocess
from playwright.async_api import async_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else 'https://openchecklists.net'
U = 'oclreg@keylinkit.net'
P = subprocess.check_output(['bw', 'get', 'password', '7205bfb7']).decode().strip()
def dec(s): s += '=' * (-len(s) % 4); return json.loads(base64.urlsafe_b64decode(s))
async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(); pg = await ctx.new_page()
        await pg.goto(BASE + '/profile.html', wait_until='networkidle')
        await pg.get_by_text('Sign in →').click()
        await pg.wait_for_url(re.compile('auth.keylinkit.net'), timeout=20000)
        await pg.locator('input:visible').first.fill(U); await pg.keyboard.press('Enter')
        await pg.locator('input[type=password]').wait_for(timeout=15000)
        await pg.locator('input[type=password]').fill(P); await pg.keyboard.press('Enter')
        await pg.wait_for_timeout(3000)
        if 'Second factor' in (await pg.inner_text('body')) or 'second factor' in (await pg.inner_text('body')):
            opt = pg.get_by_text('Authenticator App')
            if await opt.count(): await opt.first.click(); await pg.wait_for_timeout(2000)
            code = subprocess.check_output(['lab-totp', '7205bfb7']).decode().strip().split()[-1]
            await pg.locator('input:visible').first.fill(code); await pg.keyboard.press('Enter')
        for _ in range(30):
            await pg.wait_for_timeout(1000)
            if 'auth.keylinkit.net' not in pg.url and 'callback' not in pg.url: break
        await pg.wait_for_timeout(3000)
        print('landed', pg.url)
        if 'auth.keylinkit.net' in pg.url:
            print((await pg.inner_text('body'))[:400].replace('\n', ' | ')); pass
        tok = await pg.evaluate("sessionStorage.getItem('ocl:token')")
        if tok:
            os.makedirs('/tmp/ocl-e2e', exist_ok=True); open('/tmp/ocl-e2e/token', 'w').write(tok); os.chmod('/tmp/ocl-e2e/token', 0o600)
            h, c = dec(tok.split('.')[0]), dec(tok.split('.')[1])
            print('alg', h.get('alg'), 'kid?', bool(h.get('kid')))
            print(json.dumps({k: c.get(k) for k in ('iss', 'aud', 'azp', 'client_id', 'exp', 'nbf', 'iat', 'email', 'preferred_username', 'sub')}))
        else:
            print('no token')
        pass
        await b.close()
asyncio.run(main())
