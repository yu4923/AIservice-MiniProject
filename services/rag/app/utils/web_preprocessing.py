"""Search discovers URLs; only fetched, allowlisted official HTML becomes evidence."""
from __future__ import annotations

import asyncio
import ipaddress
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, urlunsplit

from app.utils.policy_preprocessing import VERSION, digest, normalize

DEFAULT_DOMAINS = ["go.kr", "lh.or.kr", "i-sh.co.kr", "kosaf.go.kr", "kised.or.kr"]


def official_url(url, domains=None):
    p = urlsplit(url)
    host = (p.hostname or "").lower().rstrip(".")
    try:
        port = p.port
    except ValueError:
        return False
    allowed = DEFAULT_DOMAINS if domains is None else domains
    return (p.scheme == "https" and not p.username and not p.password and port in (None, 443)
            and any(host == d or host.endswith("." + d) for d in allowed))


def canonical_url(url):
    p = urlsplit(url)
    # Preserve query identifiers: nttNo/articleNo distinguish official notices.
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", p.query, ""))


def parse_html(html, url):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    title = normalize(soup.title.get_text(" ") if soup.title else url)
    published = soup.select_one('meta[property="article:published_time"], meta[name="date"]')
    published = published.get("content") if published else None
    main = next((soup.select_one(s) for s in
                 ["article", "main", "#content", "#contents", ".board-view", ".view-cont"]
                 if soup.select_one(s)), soup.body or soup)
    headings = [normalize(h.get_text(" ")) for h in main.find_all(["h1", "h2", "h3", "h4"])]
    def title_score(value):
        return 2 * bool(re.search(r"20\d{2}", value)) + bool(re.search(r"모집|공고|청년|지원", value))
    if headings:
        candidate = max(headings, key=title_score)
        if title_score(candidate):
            title = candidate
    attachments, tables = [], []
    for link in main.find_all("a", href=True):
        href, label = urljoin(url, link["href"]), normalize(link.get_text(" "))
        if re.search(r"\.pdf(?:$|[?#])|download|fileDown", href, re.I) or ".pdf" in label.lower():
            attachments.append({"url": href, "label": label, "official": official_url(href),
                                "status": "not_fetched"})
    for table in main.find_all("table"):
        rows = [[normalize(c.get_text(" ", strip=True)) for c in tr.find_all(["th", "td"], recursive=False)]
                for tr in table.find_all("tr")]
        tables.append(rows)
        table.replace_with(soup.new_string(f"\n__POLICY_TABLE_{len(tables)-1}__\n"))
    for element in main.select("script,style,nav,header,footer,form,noscript,iframe"):
        element.decompose()
    blocks = []
    for line in normalize(main.get_text("\n", strip=True)).splitlines():
        marker = re.fullmatch(r"__POLICY_TABLE_(\d+)__", line)
        if marker:
            rows = tables[int(marker[1])]
            blocks.append({"kind": "table", "text": "\n".join(" | ".join(row) for row in rows), "rows": rows})
        else:
            blocks.append({"kind": "text", "text": line})
    text = "\n".join(b["text"] for b in blocks)
    if not published:
        match = re.search(r"(?:등록일|게시일|작성일)\s*[:：]?\s*(20\d{2}[-./]\d{1,2}[-./]\d{1,2})", text)
        published = match[1] if match else None
    return {"title": title, "text": text, "blocks": blocks,
            "published_at": published, "attachments": attachments, "tables": tables}


async def _fetch(session, url, domains, max_bytes=4_000_000):
    import aiohttp
    current = canonical_url(url)
    for _ in range(6):
        if not official_url(current, domains):
            raise ValueError("URL or redirect is outside the official-domain allowlist")
        for attempt in range(3):
            try:
                async with session.get(current, allow_redirects=False) as response:
                    if response.status in {301, 302, 303, 307, 308}:
                        location = response.headers.get("Location")
                        if not location:
                            raise ValueError("redirect without Location")
                        current = urljoin(current, location)
                        break
                    if response.status in {429, 500, 502, 503, 504}:
                        if attempt == 2:
                            response.raise_for_status()
                        await asyncio.sleep(2 ** attempt)
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("Content-Type", "").lower()
                    if not any(t in content_type for t in ("text/html", "application/xhtml+xml")):
                        raise ValueError("HTML required; ingest linked PDF with ingest_papers")
                    payload = bytearray()
                    async for block in response.content.iter_chunked(65536):
                        payload.extend(block)
                        if len(payload) > max_bytes:
                            raise ValueError("HTML exceeds size limit")
                    return current, bytes(payload).decode(response.charset or "utf-8", errors="replace")
            except (aiohttp.ClientError, asyncio.TimeoutError):
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
        else:
            raise RuntimeError("fetch attempts exhausted")
    raise ValueError("too many redirects")


def web_chunks(record, source, topic, collected_at, max_chars=2200):
    groups, batch, size = [], [], 0
    for block in record.get("blocks", [{"text": record["text"]}]):
        line = block["text"]
        if batch and size + len(line) > max_chars:
            groups.append("\n".join(batch)); batch, size = [], 0
        batch.append(line); size += len(line) + 1
    if batch:
        groups.append("\n".join(batch))
    chunks = []
    for i, text in enumerate(groups):
        content = (f"제목: {record['title']}\n출처: {source}\n수집일: {collected_at}\n"
                   "주의: 원문 내 적용연도·모집기간·정정 여부를 확인하세요.\n" + text)
        chunks.append({"id": digest(f"{source}|{VERSION}|{i}|{text}"), "page_content": content,
                       "metadata": {"source": source, "source_key": digest(source)[:24], "topic": topic,
                                    "title": record["title"], "collected_at": collected_at,
                                    "published_at": record["published_at"], "chunk_index": i,
                                    "authority": "official_html", "application_status": "unverified",
                                    "preprocessing_version": VERSION}})
    return chunks


async def collect_topic(topic, *, client_id=None, client_secret=None, urls=None, domains=None, limit=20):
    import aiohttp
    from aiohttp.resolver import DefaultResolver

    class PublicResolver(DefaultResolver):
        async def resolve(self, host, port=0, family=0):
            results = await super().resolve(host, port, family)
            if not results or any(not ipaddress.ip_address(x["host"]).is_global for x in results):
                raise OSError("non-public destination refused")
            return results

    connector = aiohttp.TCPConnector(resolver=PublicResolver(), limit_per_host=2)
    candidates, records, chunks, failures = [], [], [], []
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45), connector=connector,
                                    headers={"User-Agent": "YouthPolicyResearch/1.0"}) as session:
        if urls is not None:
            candidates = list(dict.fromkeys(urls))[:limit]
        else:
            if not client_id or not client_secret:
                raise ValueError("NAVER_CLIENT_ID and NAVER_CLIENT_SECRET are required for search")
            # Web search, not news snippets. Search descriptions are NEVER indexed.
            async with session.get("https://openapi.naver.com/v1/search/webkr.json",
                                   headers={"X-Naver-Client-Id": client_id,
                                            "X-Naver-Client-Secret": client_secret},
                                   params={"query": topic, "display": min(100, max(10, limit * 3)),
                                           "start": 1}) as response:
                response.raise_for_status()
                data = await response.json()
            candidates = list(dict.fromkeys(it.get("link", "") for it in data.get("items", [])))
        seen = set()
        for candidate in candidates:
            if len(records) >= limit:
                break
            if not official_url(candidate, domains):
                failures.append({"url": candidate, "reason": "not_allowlisted"}); continue
            try:
                source, html = await _fetch(session, candidate, domains)
                if source in seen:
                    continue
                record = parse_html(html, source)
                if len(record["text"]) < 100:
                    raise ValueError("empty/JavaScript-only page; no reliable body extracted")
                seen.add(source)
                now = datetime.now(timezone.utc).isoformat()
                record.update({"source": source, "source_key": digest(source)[:24], "raw_html": html,
                               "collected_at": now, "topic": topic, "content_hash": digest(html)})
                records.append(record)
                chunks.extend(web_chunks(record, source, topic, now))
            except Exception as exc:
                failures.append({"url": candidate, "reason": str(exc)})
            await asyncio.sleep(.5)
    return {"records": records, "chunks": chunks, "failures": failures,
            "searched_candidates": len(candidates)}
