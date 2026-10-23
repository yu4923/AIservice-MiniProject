"""고정 평가셋으로 실행 중인 Spring 인증 API와 전용 MariaDB를 검증한다."""
import argparse
import base64
import datetime
import hashlib
import hmac
import http.cookiejar
import json
from pathlib import Path
import secrets
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--base', default='http://localhost:8080')
parser.add_argument('--origin', default='http://localhost:5174')
args = parser.parse_args()
cases = json.loads((ROOT/'docs/auth-evaluation-cases.json').read_text())
results = []
jar = http.cookiejar.CookieJar()
browser = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
plain = urllib.request.build_opener()


def request(path, method='GET', body=None, opener=browser, headers=None):
    """실제 HTTP 호출 결과를 읽되 비밀번호와 쿠키는 출력하지 않는다."""
    actual_headers = {'Origin': args.origin, **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        actual_headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(args.base+path, method=method, data=data, headers=actual_headers)
    try:
        response = opener.open(req, timeout=15)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read().decode()
        return response.status, json.loads(raw) if raw else {}, response.headers


def record(status, condition=True, request_id=None):
    """평가셋의 기대 상태와 추가 조건을 실제 결과와 비교한다."""
    case = cases[len(results)]
    passed = status == case['expected_status'] and bool(condition)
    results.append({**case, 'actual_status': status, 'result': 'PASS' if passed else 'FAIL',
                    'request_id': request_id})
    print(case['id'], 'PASS' if passed else 'FAIL', case['name'])
    if not passed:
        raise AssertionError(case['id'] + ': unexpected result')


def signed_fixture(expiry, issuer='simple-auth-server'):
    """Java 검증기와 독립적으로 만료·발급자 오류용 HS256 토큰을 만든다."""
    secret = ''
    for line in (ROOT/'.env').read_text().splitlines():
        if line.startswith('JWT_SECRET='):
            secret = line.split('=', 1)[1].strip().strip("'\"")
    if not secret:
        raise RuntimeError('Local JWT_SECRET is required for evaluation')

    def encode(value):
        """JWT의 JSON 구간을 패딩 없는 URL-safe Base64로 인코딩한다."""
        return base64.urlsafe_b64encode(json.dumps(value, separators=(',', ':')).encode()).rstrip(b'=')

    header = encode({'alg': 'HS256', 'typ': 'JWT'})
    payload = encode({'iss': issuer, 'sub': '1', 'id': 'evaluation-fixture', 'exp': expiry})
    message = header+b'.'+payload
    signature = base64.urlsafe_b64encode(hmac.new(secret.encode(), message, hashlib.sha256).digest()).rstrip(b'=')
    return (message+b'.'+signature).decode()


def run():
    """가입·인증·거절·로그아웃을 전용 개발 DB에서 순서대로 검증한다."""
    credentials = {'id': 'eval_'+secrets.token_hex(6), 'password': secrets.token_urlsafe(24)}
    status, body, headers = request('/health')
    record(status, body.get('status') == 'UP')
    status, body, headers = request('/api/auth/check', opener=plain)
    record(status, body.get('error', {}).get('code') == 'UNAUTHORIZED')
    status, body, headers = request('/api/auth/signup', 'POST', credentials)
    record(status, body.get('id') == credentials['id'] and 'password' not in body)
    status, body, headers = request('/api/auth/signup', 'POST', credentials)
    record(status, body.get('error', {}).get('code') == 'ID_EXISTS')
    status, body, headers = request('/api/auth/login', 'POST', {**credentials, 'password': 'wrong-evaluation-value'})
    record(status, body.get('error', {}).get('code') == 'INVALID_CREDENTIALS' and not list(jar))
    status, body, headers = request('/api/auth/login', 'POST', {})
    record(status, body.get('error', {}).get('code') == 'VALIDATION_ERROR')
    status, body, headers = request('/api/auth/login', 'POST', credentials)
    cookies = headers.get_all('Set-Cookie') or []
    record(status, len(cookies) == 1 and cookies[0].startswith('ACCESS_TOKEN=')
           and all(flag in cookies[0] for flag in ['HttpOnly', 'SameSite=Lax', 'Path=/'])
           and 'Secure' not in cookies[0] and 'access_token' not in body
           and credentials['password'] not in json.dumps(body))
    status, body, headers = request('/api/auth/check')
    record(status, body.get('via') == 'jwt' and body.get('id') == credentials['id'])
    for cookie in ['SESSION_ID=legacy-fixture', 'APP_AUTH=1', 'ACCESS_TOKEN=invalid.jwt.fixture',
                   'ACCESS_TOKEN='+signed_fixture(int(time.time())-60),
                   'ACCESS_TOKEN='+signed_fixture(int(time.time())+60, 'other-issuer')]:
        status, body, headers = request('/api/auth/check', opener=plain, headers={'Cookie': cookie})
        record(status, body.get('request_id') == headers.get('X-Request-Id'), body.get('request_id'))
    status, body, headers = request('/api/auth/login', 'OPTIONS', opener=plain,
                                   headers={'Access-Control-Request-Method': 'POST',
                                            'Access-Control-Request-Headers': 'content-type'})
    record(status, headers.get('Access-Control-Allow-Origin') == args.origin
           and headers.get('Access-Control-Allow-Credentials') == 'true')
    status, body, headers = request('/api/auth/logout', 'POST', {}, opener=plain,
                                   headers={'Origin': 'http://untrusted.example'})
    record(status, body.get('error', {}).get('code') == 'ORIGIN_NOT_ALLOWED')
    status, body, headers = request('/api/auth/logout', 'POST', {})
    record(status, not list(jar))
    status, body, headers = request('/api/auth/check')
    record(status, body.get('error', {}).get('code') == 'UNAUTHORIZED')


try:
    run()
finally:
    report = {'contract': 'no-id-pw-v2', 'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'base_url': args.base, 'frontend_origin': args.origin,
              'database': 'project-local MariaDB', 'expected_case_count': len(cases),
              'executed_case_count': len(results), 'cases': results}
    (ROOT/'docs/auth-evaluation-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
