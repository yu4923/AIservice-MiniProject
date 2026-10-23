"""Disposable CI database only. No tokens or response bodies are printed."""
import http.cookiejar
import json
import time
import urllib.error
import urllib.request
import uuid

base = 'http://127.0.0.1:8080'
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def request(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data,
        headers={'Content-Type': 'application/json', 'Origin': 'http://localhost:5174'})
    try:
        response = client.open(req, timeout=5)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, json.loads(response.read())


for attempt in range(60):
    try:
        if request('/health')[0] == 200:
            break
    except (OSError, ValueError):
        pass
    time.sleep(1)
else:
    raise SystemExit('Auth did not become ready against the CI database')
credentials = {'id': 'ci_' + uuid.uuid4().hex[:16], 'password': 'ci-fixture-user-password'}
assert request('/api/signup', credentials)[0] == 201
assert request('/api/signup', credentials)[0] == 409
assert request('/api/login', credentials)[0] == 200
status, identity = request('/api/auth/check')
assert status == 200 and identity['id'] == credentials['id'] and identity['via'] == 'jwt'
assert request('/api/logout', {})[0] == 200
assert request('/api/auth/check')[0] == 401
print('PASS: MariaDB-backed signup, duplicate signup, login, JWT check, logout')
