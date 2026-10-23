"""Fetch official page bodies through configured topics or explicitly supplied URLs."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
from app.utils.ingestion import ingest_topic


def load_topics(path):
    topics = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(topics, list) or not topics:
        raise ValueError("topics.json must contain a nonempty list")
    result = []
    for item in topics:
        if isinstance(item, str) and item.strip():
            result.append({"topic": item, "urls": None})
        elif isinstance(item, dict) and isinstance(item.get("topic"), str) and item["topic"].strip():
            urls = item.get("urls")
            if urls is not None and (not isinstance(urls, list) or not urls or
                                     not all(isinstance(u, str) and u.strip() for u in urls)):
                raise ValueError("urls must be a nonempty list of URLs")
            result.append({"topic": item["topic"], "urls": urls})
        else:
            raise ValueError("Invalid topic entry")
    return result


async def run(args):
    domains = json.loads(args.domains.read_text(encoding="utf-8"))
    if not isinstance(domains, list) or not domains or not all(isinstance(d, str) and d and
            "/" not in d and ":" not in d for d in domains):
        raise ValueError("official_domains.json must be a list of hostname suffixes")
    topics = ([{"topic": args.topic or "공식 정책 원문", "urls": args.url}] if args.url else
              [{"topic": args.topic, "urls": None}] if args.topic else load_topics(args.config))
    failures = 0
    for item in topics:
        try:
            _, result = await ingest_topic(**item, dry_run=args.dry_run, domains=domains,
                                           limit=args.limit, output_dir=args.output_dir)
            print(json.dumps({"topic": item["topic"], **result}, ensure_ascii=False), flush=True)
            if result["collected"] == 0:
                failures += 1
        except Exception as exc:
            failures += 1
            print(json.dumps({"topic": item["topic"], "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
    return 1 if failures else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=BASE_DIR / "config" / "topics.json")
    parser.add_argument("--domains", type=Path, default=BASE_DIR / "config" / "official_domains.json")
    parser.add_argument("--topic")
    parser.add_argument("--url", action="append", help="Fetch official URL directly; repeatable, no Naver key needed")
    parser.add_argument("--dry-run", action="store_true", help="Fetch/parse/save only, without embeddings")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
