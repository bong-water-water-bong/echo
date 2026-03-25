"""
Echo platform agent — YouTube (Data API v3).

Environment variables:
    YOUTUBE_API_KEY
    YOUTUBE_CHANNEL_ID       (your channel to monitor)
    ECHO_YT_KEYWORDS         (comma-separated, default: "halo-ai,halo ai")
"""

from __future__ import annotations

import datetime
import json
import urllib.request
import urllib.parse
import warnings
from typing import Any

from agents.base import PlatformAgent

YT_API = "https://www.googleapis.com/youtube/v3"


def _yt_get(endpoint: str, params: dict, api_key: str) -> dict:
    params["key"] = api_key
    url = f"{YT_API}/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "echo/halo-ai"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


class YouTubeAgent(PlatformAgent):
    platform_name = "youtube"

    def _setup(self) -> None:
        self._api_key: str | None = None
        self._channel_id: str | None = None
        self._keywords: list[str] = []

        api_key = self._env("YOUTUBE_API_KEY")
        if not api_key:
            warnings.warn("[echo/youtube] YOUTUBE_API_KEY not set — agent disabled")
            return

        self._api_key = api_key
        self._channel_id = self._env("YOUTUBE_CHANNEL_ID")
        self._keywords = [
            k.strip()
            for k in self._env("ECHO_YT_KEYWORDS", "halo-ai,halo ai").split(",")
            if k.strip()
        ]

        self.available = True

    # ------------------------------------------------------------------

    def listen(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not self._api_key:
            return results

        since = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        # Search for keyword mentions in videos
        for kw in self._keywords:
            try:
                data = _yt_get("search", {
                    "part": "snippet",
                    "q": kw,
                    "type": "video",
                    "order": "date",
                    "publishedAfter": since,
                    "maxResults": 10,
                }, self._api_key)

                for item in data.get("items", []):
                    snippet = item.get("snippet", {})
                    video_id = item.get("id", {}).get("videoId", "")
                    results.append({
                        "platform": self.platform_name,
                        "type": "video",
                        "text": snippet.get("title", ""),
                        "author": snippet.get("channelTitle", ""),
                        "url": f"https://youtube.com/watch?v={video_id}",
                        "ts": snippet.get("publishedAt", ""),
                        "meta": {
                            "keyword": kw,
                            "channel_id": snippet.get("channelId", ""),
                            "description": snippet.get("description", "")[:200],
                        },
                    })
            except Exception:
                pass

        # Monitor comments on our own channel's videos
        if self._channel_id:
            try:
                data = _yt_get("commentThreads", {
                    "part": "snippet",
                    "allThreadsRelatedToChannelId": self._channel_id,
                    "order": "time",
                    "maxResults": 25,
                }, self._api_key)

                for item in data.get("items", []):
                    comment = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                    results.append({
                        "platform": self.platform_name,
                        "type": "comment",
                        "text": comment.get("textDisplay", "")[:500],
                        "author": comment.get("authorDisplayName", ""),
                        "url": f"https://youtube.com/watch?v={comment.get('videoId', '')}",
                        "ts": comment.get("publishedAt", ""),
                        "meta": {
                            "video_id": comment.get("videoId", ""),
                            "like_count": comment.get("likeCount", 0),
                        },
                    })
            except Exception:
                pass

        return results

    def post(self, message: str) -> dict[str, Any]:
        # YouTube posting (uploading videos) requires OAuth2 and is non-trivial.
        # For now, Echo can only post comments via the API.
        return {
            "platform": self.platform_name,
            "ok": False,
            "error": "YouTube video upload requires OAuth2 flow. Use 'engage' to comment.",
        }

    def engage(self, target_id: str, action: str = "comment") -> dict[str, Any]:
        """Post a comment on a video. target_id = videoId, action text = comment body."""
        if not self._api_key:
            return {"ok": False, "error": "YouTube API key not set"}

        if action == "comment":
            return {
                "ok": False,
                "error": "Commenting requires OAuth2 credentials (not just API key).",
            }

        return {"ok": False, "error": f"Unknown action: {action}"}

    def metrics(self) -> dict[str, Any]:
        if not self._api_key or not self._channel_id:
            return {"note": "Channel ID not set — cannot fetch metrics"}

        try:
            data = _yt_get("channels", {
                "part": "statistics,snippet",
                "id": self._channel_id,
            }, self._api_key)

            items = data.get("items", [])
            if not items:
                return {"error": "Channel not found"}

            stats = items[0].get("statistics", {})
            snippet = items[0].get("snippet", {})
            return {
                "channel": snippet.get("title", ""),
                "subscribers": int(stats.get("subscriberCount", 0)),
                "views": int(stats.get("viewCount", 0)),
                "videos": int(stats.get("videoCount", 0)),
            }
        except Exception as exc:
            return {"error": str(exc)}
