"""
Echo platform agent — X / Twitter (via tweepy).

Environment variables:
    TWITTER_API_KEY
    TWITTER_API_SECRET
    TWITTER_ACCESS_TOKEN
    TWITTER_ACCESS_SECRET
    TWITTER_BEARER_TOKEN      (optional, for v2 read-only)
    ECHO_TWITTER_HASHTAGS     (comma-separated, default: "haloai,halo_ai")
"""

from __future__ import annotations

import datetime
import warnings
from typing import Any

from agents.base import PlatformAgent


class TwitterAgent(PlatformAgent):
    platform_name = "twitter"

    def _setup(self) -> None:
        self._api = None  # tweepy v1.1 API
        self._client = None  # tweepy v2 Client
        self._hashtags: list[str] = []

        try:
            creds = self._require_env(
                "TWITTER_API_KEY",
                "TWITTER_API_SECRET",
                "TWITTER_ACCESS_TOKEN",
                "TWITTER_ACCESS_SECRET",
            )
        except EnvironmentError as exc:
            warnings.warn(f"[echo/twitter] {exc} — agent disabled")
            return

        try:
            import tweepy  # type: ignore
        except ImportError:
            warnings.warn("[echo/twitter] tweepy not installed — agent disabled")
            return

        bearer = self._env("TWITTER_BEARER_TOKEN")

        # v1.1 API (for posting, liking, retweeting)
        auth = tweepy.OAuth1UserHandler(
            creds["TWITTER_API_KEY"],
            creds["TWITTER_API_SECRET"],
            creds["TWITTER_ACCESS_TOKEN"],
            creds["TWITTER_ACCESS_SECRET"],
        )
        self._api = tweepy.API(auth, wait_on_rate_limit=True)

        # v2 Client (for search, mentions)
        self._client = tweepy.Client(
            bearer_token=bearer,
            consumer_key=creds["TWITTER_API_KEY"],
            consumer_secret=creds["TWITTER_API_SECRET"],
            access_token=creds["TWITTER_ACCESS_TOKEN"],
            access_token_secret=creds["TWITTER_ACCESS_SECRET"],
            wait_on_rate_limit=True,
        )

        self._hashtags = [
            h.strip()
            for h in self._env("ECHO_TWITTER_HASHTAGS", "haloai,halo_ai").split(",")
            if h.strip()
        ]

        self.available = True

    # ------------------------------------------------------------------

    def listen(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not self._client:
            return results

        # Mentions timeline
        try:
            me = self._client.get_me()
            if me and me.data:
                mentions = self._client.get_users_mentions(
                    me.data.id,
                    max_results=25,
                    tweet_fields=["created_at", "author_id", "text"],
                )
                if mentions and mentions.data:
                    for tweet in mentions.data:
                        results.append({
                            "platform": self.platform_name,
                            "type": "mention",
                            "text": tweet.text,
                            "author": str(tweet.author_id),
                            "url": f"https://x.com/i/status/{tweet.id}",
                            "ts": tweet.created_at.isoformat() if tweet.created_at else "",
                            "meta": {"tweet_id": str(tweet.id)},
                        })
        except Exception:
            pass

        # Hashtag search
        for tag in self._hashtags:
            try:
                resp = self._client.search_recent_tweets(
                    query=f"#{tag}",
                    max_results=10,
                    tweet_fields=["created_at", "author_id", "text", "public_metrics"],
                )
                if resp and resp.data:
                    for tweet in resp.data:
                        results.append({
                            "platform": self.platform_name,
                            "type": "hashtag",
                            "text": tweet.text,
                            "author": str(tweet.author_id),
                            "url": f"https://x.com/i/status/{tweet.id}",
                            "ts": tweet.created_at.isoformat() if tweet.created_at else "",
                            "meta": {
                                "hashtag": tag,
                                "metrics": tweet.public_metrics if hasattr(tweet, "public_metrics") else {},
                            },
                        })
            except Exception:
                pass

        return results

    def post(self, message: str) -> dict[str, Any]:
        if not self._client:
            return {"ok": False, "error": "Twitter client not initialised"}

        resp = self._client.create_tweet(text=message[:280])
        tweet_id = resp.data["id"] if resp and resp.data else None

        return {
            "platform": self.platform_name,
            "ok": True,
            "id": str(tweet_id),
            "url": f"https://x.com/i/status/{tweet_id}" if tweet_id else "",
        }

    def engage(self, target_id: str, action: str = "like") -> dict[str, Any]:
        if not self._client:
            return {"ok": False, "error": "Twitter client not initialised"}

        me = self._client.get_me()
        user_id = me.data.id if me and me.data else None
        if not user_id:
            return {"ok": False, "error": "Could not resolve own user ID"}

        if action == "like":
            self._client.like(tweet_id=target_id)
        elif action == "retweet":
            self._client.retweet(tweet_id=target_id)
        elif action == "bookmark":
            self._client.bookmark(tweet_id=target_id)
        else:
            return {"ok": False, "error": f"Unknown action: {action}"}

        return {"ok": True, "action": action, "target": target_id}

    def metrics(self) -> dict[str, Any]:
        if not self._client:
            return {}
        me = self._client.get_me(user_fields=["public_metrics", "created_at"])
        if not me or not me.data:
            return {}
        pm = me.data.public_metrics or {}
        return {
            "username": me.data.username,
            "followers": pm.get("followers_count", 0),
            "following": pm.get("following_count", 0),
            "tweets": pm.get("tweet_count", 0),
        }
