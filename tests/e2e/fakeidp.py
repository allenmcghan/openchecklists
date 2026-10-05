import json, base64, time, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
pub = key.public_key().public_numbers()
b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b'=').decode()
i2b = lambda i: i.to_bytes((i.bit_length() + 7) // 8, 'big')
ISS = 'http://127.0.0.1:9911'
JWKS = {'keys': [{'kty': 'RSA', 'kid': 'k1', 'alg': 'RS256', 'use': 'sig', 'n': b64(i2b(pub.n)), 'e': b64(i2b(pub.e))}]}
def tok(claims, alg='RS256', kid='k1'):
    h = b64(json.dumps({'alg': alg, 'kid': kid, 'typ': 'JWT'}).encode()); p = b64(json.dumps(claims).encode())
    sig = key.sign(f'{h}.{p}'.encode(), padding.PKCS1v15(), hashes.SHA256())
    return f'{h}.{p}.{b64(sig)}'
now = int(time.time())
good = {'iss': ISS, 'aud': ['385717620558594052'], 'sub': 'u-fake', 'exp': now + 600, 'iat': now}
cases = {
  'good': tok(good),
  'wrong_aud': tok({**good, 'aud': ['999999999']}),
  'no_exp': tok({k: v for k, v in good.items() if k != 'exp'}),
  'expired': tok({**good, 'exp': now - 10}),
  'wrong_iss': tok({**good, 'iss': 'https://evil.example'}),
  'future_nbf': tok({**good, 'nbf': now + 3600}),
  'alg_none': b64(json.dumps({'alg': 'none', 'kid': 'k1'}).encode()) + '.' + b64(json.dumps(good).encode()) + '.',
  'unknown_kid': tok(good, kid='nope'),
}
json.dump(cases, open('/tmp/ocl-e2e/fake_tokens.json', 'w'))
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        body = {'/.well-known/openid-configuration': {'issuer': ISS, 'jwks_uri': ISS + '/keys'}, '/keys': JWKS}.get(self.path)
        self.send_response(200 if body else 404); self.send_header('Content-Type', 'application/json'); self.end_headers()
        self.wfile.write(json.dumps(body or {}).encode())
HTTPServer(('127.0.0.1', 9911), H).serve_forever()
