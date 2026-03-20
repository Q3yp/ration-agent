"""Scrape Feedipedia and store feed composition data in a SQLite database.

Usage:
    uv run python scripts/scrape_feedipedia.py              # full crawl
    uv run python scripts/scrape_feedipedia.py --resume     # resume interrupted crawl
    uv run python scripts/scrape_feedipedia.py --stats      # show DB stats

Respects robots.txt:
  - 10-second crawl delay between requests
  - Skips disallowed paths

Data is licensed CC-BY-4.0 by INRA, CIRAD, AFZ, and FAO.

The resulting SQLite file (data/feedipedia.db) is portable and can be moved
between machines without any further setup.
"""

from __future__ import annotations

import argparse
import logging
import re
import signal
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://www.feedipedia.org"
CRAWL_DELAY = 10  # seconds, per robots.txt
DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DB_DIR / "feedipedia.db"
REQUEST_TIMEOUT = 30  # seconds

# Retry policy for transient network errors
RETRY_STRATEGY = Retry(
    total=5,
    backoff_factor=2,  # 2, 4, 8, 16, 32 seconds
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=("GET",),
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Graceful shutdown flag
_shutdown_requested = False


def _handle_signal(signum: int, frame: Any) -> None:
    global _shutdown_requested
    _shutdown_requested = True
    logger.warning("Shutdown requested (signal %d). Finishing current page...", signum)


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------


def init_db(db_path: Path) -> sqlite3.Connection:
    """Create (or open) the SQLite database and ensure schema exists."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")  # better for concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS feeds (
            node_id         INTEGER PRIMARY KEY,
            name            TEXT NOT NULL,
            scientific_name TEXT,
            family          TEXT,
            description     TEXT,
            categories      TEXT,       -- JSON array
            url             TEXT NOT NULL,
            crawled_at      TEXT,       -- ISO-8601 UTC
            status          TEXT DEFAULT 'pending'   -- pending | done | error
        );

        CREATE TABLE IF NOT EXISTS sub_feeds (
            sub_node_id     INTEGER PRIMARY KEY,
            parent_node_id  INTEGER NOT NULL REFERENCES feeds(node_id),
            name            TEXT NOT NULL,
            url             TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS nutrients (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sub_node_id     INTEGER NOT NULL REFERENCES sub_feeds(sub_node_id),
            section         TEXT NOT NULL,   -- e.g. Main analysis, Minerals, Amino acids, ...
            nutrient_name   TEXT NOT NULL,
            unit            TEXT,
            avg             REAL,
            sd              REAL,
            min_val         REAL,
            max_val         REAL,
            nb_samples      INTEGER,
            is_estimated    INTEGER DEFAULT 0,  -- 1 if marked with asterisk
            UNIQUE(sub_node_id, nutrient_name)
        );

        -- Full-text search index for feed names
        CREATE VIRTUAL TABLE IF NOT EXISTS feeds_fts USING fts5(
            name, scientific_name, categories,
            content='feeds',
            content_rowid='node_id'
        );

        -- Triggers to keep FTS in sync
        CREATE TRIGGER IF NOT EXISTS feeds_ai AFTER INSERT ON feeds BEGIN
            INSERT INTO feeds_fts(rowid, name, scientific_name, categories)
            VALUES (new.node_id, new.name, new.scientific_name, new.categories);
        END;

        CREATE TRIGGER IF NOT EXISTS feeds_au AFTER UPDATE ON feeds BEGIN
            INSERT INTO feeds_fts(feeds_fts, rowid, name, scientific_name, categories)
            VALUES ('delete', old.node_id, old.name, old.scientific_name, old.categories);
            INSERT INTO feeds_fts(rowid, name, scientific_name, categories)
            VALUES (new.node_id, new.name, new.scientific_name, new.categories);
        END;

        CREATE TRIGGER IF NOT EXISTS feeds_ad AFTER DELETE ON feeds BEGIN
            INSERT INTO feeds_fts(feeds_fts, rowid, name, scientific_name, categories)
            VALUES ('delete', old.node_id, old.name, old.scientific_name, old.categories);
        END;

        -- Metadata table
        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def make_session() -> requests.Session:
    """Build a requests.Session with retry logic."""
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=RETRY_STRATEGY)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": (
                "RationAgent-Scraper/1.0 "
                "(research feed formulation tool; "
                "respects robots.txt crawl-delay; "
                "contact: feedipedia data under CC-BY-4.0)"
            ),
        }
    )
    return session


def fetch_page(session: requests.Session, url: str) -> Optional[BeautifulSoup]:
    """Fetch a page and return parsed soup. Returns None on permanent failure."""
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            logger.warning("404 Not Found: %s", url)
            return None
        logger.error("HTTP error for %s: %s", url, exc)
        raise
    except requests.exceptions.ConnectionError as exc:
        logger.error("Connection error for %s: %s", url, exc)
        raise
    except requests.exceptions.Timeout:
        logger.error("Timeout fetching %s", url)
        raise


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _extract_node_id(href: str) -> Optional[int]:
    """Extract the numeric node ID from a Feedipedia href like /node/556."""
    m = re.search(r"/node/(\d+)", href)
    return int(m.group(1)) if m else None


def _parse_float(s: str) -> Optional[float]:
    """Try parsing a string as float, return None on failure."""
    s = s.strip().replace("*", "")
    if not s or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_int(s: str) -> Optional[int]:
    """Try parsing a string as int, return None on failure."""
    s = s.strip().replace("*", "")
    if not s or s == "-":
        return None
    try:
        return int(s)
    except ValueError:
        return None


def discover_feeds(session: requests.Session) -> List[Tuple[int, str]]:
    """Fetch the master feed list and return (node_id, name) pairs."""
    url = f"{BASE_URL}/content/feeds?category=All"
    soup = fetch_page(session, url)
    if not soup:
        raise RuntimeError("Failed to load feed list page")

    content = soup.find("div", id="content") or soup
    feeds = []
    seen = set()
    for a in content.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        node_id = _extract_node_id(href)
        if node_id and text and len(text) > 2 and node_id not in seen:
            seen.add(node_id)
            feeds.append((node_id, text))

    logger.info("Discovered %d feeds from master list", len(feeds))
    return feeds


def parse_feed_page(soup: BeautifulSoup, node_id: int) -> Dict[str, Any]:
    """Parse a main feed page and extract metadata + sub-feed nutrient tables."""

    result: Dict[str, Any] = {
        "node_id": node_id,
        "name": "",
        "scientific_name": None,
        "family": None,
        "description": None,
        "categories": [],
        "sub_feeds": [],
    }

    # Page title
    h1 = soup.find("h1")
    if h1:
        result["name"] = h1.get_text(strip=True)

    # Scientific name & family
    species_div = soup.find(
        "div", class_="field-name-field-datasheet-species"
    )
    if species_div:
        # The species link looks like: /content/feeds?species=13554 -> "Zea maysL."
        species_link = species_div.find("a", href=lambda h: h and "species=" in h)
        if species_link:
            result["scientific_name"] = species_link.get_text(" ", strip=True)
        # The family link looks like: /content/species?family=6005 -> "Poaceae"
        family_link = species_div.find("a", href=lambda h: h and "family=" in h)
        if family_link:
            result["family"] = family_link.get_text(strip=True)

    # Categories
    cat_div = soup.find("div", class_="field-name-field-category-list")
    if cat_div:
        result["categories"] = [a.get_text(strip=True) for a in cat_div.find_all("a")]

    # Description (first paragraph)
    desc_fieldset = soup.find("fieldset", id="description")
    if desc_fieldset:
        first_p = desc_fieldset.find("p")
        if first_p:
            result["description"] = first_p.get_text(strip=True)

    # Sub-feeds with nutrient tables
    views_rows = soup.find_all("div", class_=re.compile(r"views-row"))
    for row in views_rows:
        sub_feed = _parse_views_row(row)
        if sub_feed:
            result["sub_feeds"].append(sub_feed)

    return result


def _parse_views_row(row: Tag) -> Optional[Dict[str, Any]]:
    """Parse one views-row div containing a sub-feed title + nutrient table."""
    # Find the title link (first <a> in the row pointing to /node/)
    title_link = None
    for a in row.find_all("a", href=True):
        if _extract_node_id(a["href"]):
            title_text = a.get_text(strip=True)
            if title_text and len(title_text) > 2:
                title_link = a
                break

    if not title_link:
        return None

    sub_node_id = _extract_node_id(title_link["href"])
    if not sub_node_id:
        return None

    table = row.find("table")
    nutrients = _parse_nutrient_table(table) if table else []

    return {
        "sub_node_id": sub_node_id,
        "name": title_link.get_text(strip=True),
        "url": f"{BASE_URL}{title_link['href']}",
        "nutrients": nutrients,
    }


def _parse_nutrient_table(table: Tag) -> List[Dict[str, Any]]:
    """Parse a Feedipedia nutrient table into a list of nutrient dicts."""
    nutrients = []
    current_section = "Main analysis"

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all(["th", "td"])
        texts = [c.get_text(strip=True) for c in cells]

        if not texts or len(texts) < 2:
            continue

        # Section header rows have format: ['Section Name', 'Unit', 'Avg', ...]
        # They are distinguished by having a known section name as first cell
        first = texts[0]
        if not first:
            # Empty first cell = section separator
            continue

        # Check if this is a section header row
        known_sections = {
            "Main analysis",
            "Minerals",
            "Amino acids",
            "Ruminant nutritive values",
            "Pig nutritive values",
            "Poultry nutritive values",
            "Rabbit nutritive values",
            "Horse nutritive values",
            "Secondary metabolites",
        }
        if first in known_sections:
            current_section = first
            continue

        # Data row: [Name, Unit, Avg, SD, Min, Max, Nb, (asterisk)]
        if len(texts) < 7:
            continue

        name = texts[0]
        unit = texts[1]
        avg = _parse_float(texts[2])
        sd = _parse_float(texts[3])
        min_val = _parse_float(texts[4])
        max_val = _parse_float(texts[5])
        nb = _parse_int(texts[6])
        is_estimated = 1 if len(texts) > 7 and "*" in texts[7] else 0

        if avg is None and min_val is None and max_val is None:
            continue  # skip empty data rows

        nutrients.append(
            {
                "section": current_section,
                "nutrient_name": name,
                "unit": unit,
                "avg": avg,
                "sd": sd,
                "min_val": min_val,
                "max_val": max_val,
                "nb_samples": nb,
                "is_estimated": is_estimated,
            }
        )

    return nutrients


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------


def seed_feed_list(conn: sqlite3.Connection, feeds: List[Tuple[int, str]]) -> int:
    """Insert discovered feeds into DB, skipping those already present.
    Returns the number of new feeds inserted."""
    new_count = 0
    for node_id, name in feeds:
        try:
            conn.execute(
                """INSERT INTO feeds (node_id, name, url, status)
                   VALUES (?, ?, ?, 'pending')""",
                (node_id, name, f"{BASE_URL}/node/{node_id}"),
            )
            new_count += 1
        except sqlite3.IntegrityError:
            pass  # already exists
    conn.commit()
    return new_count


def get_pending_feeds(conn: sqlite3.Connection) -> List[Tuple[int, str]]:
    """Return (node_id, url) for all feeds not yet successfully crawled."""
    cursor = conn.execute(
        "SELECT node_id, url FROM feeds WHERE status != 'done' ORDER BY node_id"
    )
    return cursor.fetchall()


def save_feed_data(conn: sqlite3.Connection, data: Dict[str, Any]) -> None:
    """Persist parsed feed data (metadata + sub-feeds + nutrients)."""
    import json

    node_id = data["node_id"]

    conn.execute(
        """UPDATE feeds SET
            name = ?,
            scientific_name = ?,
            family = ?,
            description = ?,
            categories = ?,
            crawled_at = ?,
            status = 'done'
           WHERE node_id = ?""",
        (
            data["name"],
            data["scientific_name"],
            data["family"],
            data["description"],
            json.dumps(data["categories"]),
            datetime.now(timezone.utc).isoformat(),
            node_id,
        ),
    )

    for sf in data["sub_feeds"]:
        # Upsert sub-feed
        conn.execute(
            """INSERT INTO sub_feeds (sub_node_id, parent_node_id, name, url)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(sub_node_id) DO UPDATE SET
                 name = excluded.name,
                 url = excluded.url""",
            (sf["sub_node_id"], node_id, sf["name"], sf["url"]),
        )

        # Delete old nutrients for this sub-feed, then re-insert
        conn.execute(
            "DELETE FROM nutrients WHERE sub_node_id = ?", (sf["sub_node_id"],)
        )
        for n in sf["nutrients"]:
            conn.execute(
                """INSERT INTO nutrients
                   (sub_node_id, section, nutrient_name, unit,
                    avg, sd, min_val, max_val, nb_samples, is_estimated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sf["sub_node_id"],
                    n["section"],
                    n["nutrient_name"],
                    n["unit"],
                    n["avg"],
                    n["sd"],
                    n["min_val"],
                    n["max_val"],
                    n["nb_samples"],
                    n["is_estimated"],
                ),
            )

    conn.commit()


def mark_feed_error(conn: sqlite3.Connection, node_id: int, error: str) -> None:
    """Mark a feed as having errored during crawl."""
    conn.execute(
        "UPDATE feeds SET status = 'error', crawled_at = ? WHERE node_id = ?",
        (datetime.now(timezone.utc).isoformat(), node_id),
    )
    conn.commit()
    logger.error("Feed %d marked as error: %s", node_id, error)


# ---------------------------------------------------------------------------
# Main crawl loop
# ---------------------------------------------------------------------------


def crawl(conn: sqlite3.Connection, session: requests.Session) -> None:
    """Run the main crawl loop with crawl-delay and resume support."""
    pending = get_pending_feeds(conn)
    total = len(pending)
    logger.info("Starting crawl: %d feeds pending", total)

    for i, (node_id, url) in enumerate(pending, 1):
        if _shutdown_requested:
            logger.info("Shutdown requested. Exiting crawl loop.")
            break

        logger.info("[%d/%d] Crawling feed %d: %s", i, total, node_id, url)

        try:
            soup = fetch_page(session, url)
            if soup is None:
                mark_feed_error(conn, node_id, "Page not found (404)")
                time.sleep(CRAWL_DELAY)
                continue

            data = parse_feed_page(soup, node_id)

            # If the page had no sub-feeds with tables, it might be a
            # sub-feed page itself (direct node with a nutrient table).
            # Fallback: parse the page as a standalone sub-feed.
            if not data["sub_feeds"]:
                tables = soup.find_all("table")
                # Find the data table (skip the survey table)
                for table in tables:
                    table_rows = table.find_all("tr")
                    if len(table_rows) > 5:
                        first_row_cells = [
                            c.get_text(strip=True) for c in table_rows[0].find_all(["th", "td"])
                        ]
                        if "Avg" in first_row_cells:
                            nutrients = _parse_nutrient_table(table)
                            if nutrients:
                                data["sub_feeds"].append(
                                    {
                                        "sub_node_id": node_id,
                                        "name": data["name"],
                                        "url": url,
                                        "nutrients": nutrients,
                                    }
                                )
                            break

            save_feed_data(conn, data)

            sub_count = len(data["sub_feeds"])
            nutrient_count = sum(len(sf["nutrients"]) for sf in data["sub_feeds"])
            logger.info(
                "  -> %s: %d sub-feeds, %d nutrient values",
                data["name"],
                sub_count,
                nutrient_count,
            )

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            mark_feed_error(conn, node_id, str(exc))
            logger.warning("Network error, will retry on next run. Waiting before continuing...")
            time.sleep(CRAWL_DELAY * 3)  # extra wait on network errors

        except Exception as exc:
            mark_feed_error(conn, node_id, str(exc))
            logger.exception("Unexpected error crawling feed %d", node_id)

        # Respect crawl delay between page fetches
        if not _shutdown_requested:
            time.sleep(CRAWL_DELAY)

    # Save overall crawl metadata
    import json

    conn.execute(
        """INSERT OR REPLACE INTO meta (key, value) VALUES ('last_crawl', ?)""",
        (json.dumps({
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "shutdown_requested": _shutdown_requested,
        }),),
    )
    conn.commit()


def print_stats(conn: sqlite3.Connection, db_path: Path = DB_PATH) -> None:
    """Print statistics about the database."""
    total = conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0]
    done = conn.execute("SELECT COUNT(*) FROM feeds WHERE status='done'").fetchone()[0]
    error = conn.execute("SELECT COUNT(*) FROM feeds WHERE status='error'").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM feeds WHERE status='pending'").fetchone()[0]
    sub_feeds = conn.execute("SELECT COUNT(*) FROM sub_feeds").fetchone()[0]
    nutrients = conn.execute("SELECT COUNT(*) FROM nutrients").fetchone()[0]

    print(f"\n{'='*50}")
    print(f"  Feedipedia Database Statistics")
    print(f"  DB file: {db_path}")
    print(f"  DB size: {db_path.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"{'='*50}")
    print(f"  Feeds:     {total:>6}  (done={done}, pending={pending}, error={error})")
    print(f"  Sub-feeds: {sub_feeds:>6}")
    print(f"  Nutrients: {nutrients:>6}  (total data points)")
    print(f"{'='*50}")

    # Show some categories
    cursor = conn.execute(
        "SELECT categories, COUNT(*) FROM feeds WHERE status='done' GROUP BY categories ORDER BY COUNT(*) DESC LIMIT 10"
    )
    print("\n  Top categories:")
    for row in cursor:
        print(f"    {row[1]:>4}  {row[0]}")

    # Show recent errors
    cursor = conn.execute(
        "SELECT node_id, name FROM feeds WHERE status='error' ORDER BY node_id LIMIT 5"
    )
    errors = cursor.fetchall()
    if errors:
        print(f"\n  Recent errors ({error} total):")
        for node_id, name in errors:
            print(f"    node/{node_id}: {name}")

    # Last crawl info
    meta = conn.execute("SELECT value FROM meta WHERE key='last_crawl'").fetchone()
    if meta:
        print(f"\n  Last crawl: {meta[0]}")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Feedipedia feed composition data into SQLite."
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume a previous crawl (skip feed discovery if feeds already in DB)",
    )
    parser.add_argument(
        "--stats", action="store_true", help="Show database statistics and exit"
    )
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Reset errored feeds to pending so they are retried",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DB_PATH,
        help=f"Path to SQLite database (default: {DB_PATH})",
    )
    args = parser.parse_args()

    db_path = args.db

    conn = init_db(db_path)

    if args.stats:
        print_stats(conn, db_path)
        return

    if args.retry_errors:
        count = conn.execute(
            "UPDATE feeds SET status='pending' WHERE status='error'"
        ).rowcount
        conn.commit()
        logger.info("Reset %d errored feeds to pending", count)

    session = make_session()

    # Discover feeds (or skip if resuming and feeds exist)
    existing = conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0]
    if args.resume and existing > 0:
        logger.info("Resuming crawl with %d feeds already in DB", existing)
    else:
        logger.info("Discovering feeds from Feedipedia master list...")
        feeds = discover_feeds(session)
        new = seed_feed_list(conn, feeds)
        logger.info("Seeded %d new feeds (%d total in DB)", new, existing + new)
        time.sleep(CRAWL_DELAY)  # respect crawl delay after list fetch

    # Run the crawl
    crawl(conn, session)

    # Final stats
    print_stats(conn, db_path)

    conn.close()
    logger.info("Done.")


if __name__ == "__main__":
    main()
