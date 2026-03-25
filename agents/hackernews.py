"""
Echo platform agent — Hacker News (via Algolia API).

No credentials required (public API). Read-only — HN has no post API.

Environment variables:
    ECHO_HN_KEYWORDS   (comma-separated, default: "halo-ai,halo ai")
"""

from __future__ import annotations

import datetime
import json
import urllib.request
import warnings
from typing import Any

from agents.base import PlatformAgent

ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search_by_date"
ALGOLIA_ITEM = "https://hn.algolia.com/api/v1/items"
HN_FRONT_PAGE = "https://hacker-news.firebaseio.com/v0/topstories.json"


def _get_json(url: str, timeout: int = 15) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "echo/halo-ai"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


class HackerNewsAgent(PlatformAgent):
    platform_name = "hackernews"

    def _setup(self) -> None:
        self._keywords: list[str] = [
            k.strip()
            for k in self._env("ECHO_HN_KEYWORDS", "halo-ai,halo ai").split(",")
            if k.strip()
        ]
        # HN public API — always available
        self.available = True

    # ------------------------------------------------------------------

    def listen(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        for kw in self._keywords:
            try:
                data = _get_json(
                    f"{ALGOLIA_SEARCH}?query={urllib.request.quote(kw)}"
                    f"&tags=(story,comment)&numericFilters=created_at_i>"
                    f"{int((datetime.datetime.utcnow() - datetime.timedelta(days=1)).timestamp())}"
                )
                for hit in data.get("hits", []):
                    item_type = "story" if "story" in hit.get("_tags", []) else "comment"
                    results.append({
                        "platform": self.platform_name,
                        "type": item_type,
                        "text": hit.get("title") or hit.get("comment_text", "")[:500],
                        "author": hit.get("author", ""),
                        "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                        "ts": hit.get("created_at", ""),
                        "meta": {
                            "keyword": kw,
                            "points": hit.get("points"),
                            "num_comments": hit.get("num_comments"),
                            "story_id": hit.get("story_id") or hit.get("objectID"),
                        },
                    })
            except Exception:
                pass

        # Check if any keyword-matching story is on the front page
        try:
            top_ids = _get_json(HN_FRONT_PAGE)[:30]
            top_set = set(str(i) for i in top_ids)
            for r in results:
                sid = str(r["meta"].get("story_id", ""))
                if sid in top_set:
                    r["meta"]["front_page"] = True
        except Exception:
            pass

        return results

    def post(self, message: str) -> dict[str, Any]:
        return {
            "platform": self.platform_name,
            "ok": False,
            "error": "Hacker News does not support programmatic posting.",
        }

    def engage(self, target_id: str, action: str = "upvote") -> dict[str, Any]:
        return {
            "platform": self.platform_name,
            "ok": False,
            "error": "Hacker News voting requires browser authentication.",
        }

    def metrics(self) -> dict[str, Any]:
        return {
            "note": "HN public API — no account-level metrics available",
            "keywords_tracked": self._keywords,
        }
