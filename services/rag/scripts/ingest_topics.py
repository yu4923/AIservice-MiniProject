"""Run from any directory: python /path/to/scripts/ingest_topics.py"""
import asyncio
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
from app.utils.ingestion import ingest_topic


async def main():
    topics = json.loads((BASE_DIR / "config" / "topics.json").read_text(encoding="utf-8"))
    if not isinstance(topics, list) or not topics or not all(isinstance(t, str) and t.strip() for t in topics):
        raise ValueError("topics.json must contain a nonempty list of search terms")
    for topic in topics:
        _, result = await ingest_topic(topic)
        print(topic, json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
