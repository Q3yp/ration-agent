#!/usr/bin/env python3
"""
Generate embeddings ONLY for new feeds that don't already have embeddings.

Loads existing feed_embeddings.json, finds feeds in nasem_feedbase_enriched.json
that are missing embeddings, generates only those, and merges the result.

Usage:
    python scripts/generate_new_embeddings.py [--dry-run] [--batch-size 6]
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = Path(__file__).parent
ENRICHED_PATH = SCRIPT_DIR / "nasem_feedbase_enriched.json"
EMBEDDINGS_PATH = SCRIPT_DIR / "feed_embeddings.json"


def create_feed_text(feed_name: str, feed_data: dict) -> str:
    """Create searchable text from feed data for embedding.
    
    Matches the format used in extract_nasem_feeds.py so existing
    embeddings remain compatible.
    """
    parts = []
    nasem_name = feed_data.get("nasem_name", "")
    if nasem_name:
        parts.append(nasem_name)
    category = feed_data.get("category", "")
    if category:
        parts.append(category)
    feed_type = feed_data.get("type", "")
    if feed_type:
        parts.append(feed_type)
    parts.append(feed_name.replace("_", " "))
    return " - ".join(parts)


async def generate_embeddings_batch(
    texts: list[str], client: httpx.AsyncClient
) -> list[list[float]]:
    """Generate embeddings for a batch of texts via API."""
    model = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
    endpoint = os.getenv("EMBEDDING_ENDPOINT", "https://openrouter.ai/api/v1")
    api_key = os.getenv("EMBEDDING_API_KEY")

    if not api_key:
        raise ValueError("EMBEDDING_API_KEY not set in environment")

    url = f"{endpoint}/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "input": texts}

    response = await client.post(url, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()

    embeddings_data = sorted(data["data"], key=lambda x: x["index"])
    return [item["embedding"] for item in embeddings_data]


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate embeddings for new enriched feeds"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without calling the API",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=6,
        help="Number of texts per API call (default: 6)",
    )
    args = parser.parse_args()

    # --- Load enriched feedbase ---
    if not ENRICHED_PATH.exists():
        print(f"❌ Enriched feedbase not found: {ENRICHED_PATH}")
        sys.exit(1)

    with open(ENRICHED_PATH, "r", encoding="utf-8") as f:
        enriched = json.load(f)
    all_feeds = enriched["default_dairy_cow_nasem"]["feeds"]
    print(f"📚 Enriched feedbase: {len(all_feeds)} feeds")

    # --- Load existing embeddings ---
    existing = {"model": "", "dimension": 1536, "feed_texts": {}, "embeddings": {}}
    if EMBEDDINGS_PATH.exists():
        with open(EMBEDDINGS_PATH, "r") as f:
            existing = json.load(f)
        print(f"📦 Existing embeddings: {len(existing.get('embeddings', {}))} feeds")

    existing_keys = set(existing.get("embeddings", {}).keys())

    # --- Find feeds that need new embeddings ---
    new_keys = [k for k in all_feeds if k not in existing_keys]
    print(f"🆕 New feeds needing embeddings: {len(new_keys)}")

    if not new_keys:
        print("✅ All feeds already have embeddings. Nothing to do.")
        return

    if args.dry_run:
        print("\n--- Dry run: would generate embeddings for ---")
        for i, key in enumerate(new_keys[:20]):
            text = create_feed_text(key, all_feeds[key])
            print(f"  {i+1}. {text}")
        if len(new_keys) > 20:
            print(f"  ... and {len(new_keys) - 20} more")
        return

    # --- Prepare texts ---
    feed_texts = {}
    texts_to_embed = []
    keys_to_embed = []
    for key in new_keys:
        text = create_feed_text(key, all_feeds[key])
        feed_texts[key] = text
        texts_to_embed.append(text)
        keys_to_embed.append(key)

    # --- Generate embeddings in batches ---
    model = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
    batch_size = args.batch_size
    total_batches = (len(texts_to_embed) + batch_size - 1) // batch_size
    print(
        f"\n🔄 Generating {len(texts_to_embed)} embeddings "
        f"(model: {model}, batches: {total_batches}, batch_size: {batch_size})"
    )

    new_embeddings = {}
    failed_batches = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        for i in range(0, len(texts_to_embed), batch_size):
            batch_texts = texts_to_embed[i : i + batch_size]
            batch_keys = keys_to_embed[i : i + batch_size]
            batch_num = (i // batch_size) + 1

            try:
                batch_embeddings = await generate_embeddings_batch(batch_texts, client)
                for key, embedding in zip(batch_keys, batch_embeddings):
                    new_embeddings[key] = embedding

                if batch_num % 20 == 0 or batch_num == total_batches:
                    print(
                        f"  ✅ Batch {batch_num}/{total_batches} "
                        f"(total: {len(new_embeddings)}/{len(texts_to_embed)})"
                    )
            except Exception as e:
                print(f"  ❌ Batch {batch_num}/{total_batches} failed: {e}")
                failed_batches.append((i, batch_keys))
                # Brief pause before retry
                await asyncio.sleep(2)
                try:
                    batch_embeddings = await generate_embeddings_batch(
                        batch_texts, client
                    )
                    for key, embedding in zip(batch_keys, batch_embeddings):
                        new_embeddings[key] = embedding
                    print(f"  ✅ Batch {batch_num} retry succeeded")
                    failed_batches.pop()
                except Exception as e2:
                    print(f"  ❌ Batch {batch_num} retry also failed: {e2}")

    # --- Merge with existing ---
    result = {
        "model": model,
        "dimension": existing.get("dimension", 1536),
        "feed_texts": {**existing.get("feed_texts", {}), **feed_texts},
        "embeddings": {**existing.get("embeddings", {}), **new_embeddings},
    }

    print(f"\n📊 Final result:")
    print(f"  Existing embeddings kept: {len(existing.get('embeddings', {}))}")
    print(f"  New embeddings generated: {len(new_embeddings)}")
    print(f"  Total embeddings: {len(result['embeddings'])}")

    if failed_batches:
        failed_count = sum(len(keys) for _, keys in failed_batches)
        print(f"  ⚠️  Failed feeds: {failed_count}")

    # --- Save ---
    # Backup existing
    backup_path = EMBEDDINGS_PATH.with_suffix(".json.bak")
    if EMBEDDINGS_PATH.exists():
        import shutil
        shutil.copy2(EMBEDDINGS_PATH, backup_path)
        print(f"\n💾 Backed up existing embeddings to {backup_path.name}")

    with open(EMBEDDINGS_PATH, "w") as f:
        json.dump(result, f)

    file_size = EMBEDDINGS_PATH.stat().st_size / 1024 / 1024
    print(f"✅ Saved merged embeddings to {EMBEDDINGS_PATH.name} ({file_size:.1f} MB)")


if __name__ == "__main__":
    asyncio.run(main())
