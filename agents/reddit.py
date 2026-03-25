"""
Echo platform agent — Reddit (via PRAW).

Environment variables:
    REDDIT_CLIENT_ID
    REDDIT_CLIENT_SECRET
    REDDIT_USERNAME
    REDDIT_PASSWORD
    REDDIT_USER_AGENT        (optional, has a sensible default)
    ECHO_REDDIT_SUBREDDITS   (comma-separated, default: "haloai,artificialintelligence")
    ECHO_REDDIT_KEYWORDS     (comma-separated, default: "halo-ai,halo ai")
"""

from __future__ import annotations

import datetime
import warnings
from typing import Any

from agents.base import PlatformAgent


class RedditAgent(PlatformAgent):
    platform_name = "reddit"

    def _setup(self) -> None:
        self._reddit = None
        self._subreddits: list[str] = []
        self._keywords: list[str] = []

        try:
            creds = self._require_env(
                "REDDIT_CLIENT_ID",
                "REDDIT_CLIENT_SECRET",
                "REDDIT_USERNAME",
                "REDDIT_PASSWORD",
            )
        except EnvironmentError as exc:
            warnings.warn(f"[echo/reddit] {exc} — agent disabled")
            return

        try:
            import praw  # type: ignore
        except ImportError:
            warnings.warn("[echo/reddit] praw not installed — agent disabled")
            return

        user_agent = self._env(
            "REDDIT_USER_AGENT", f"echo:halo-ai:v1 (by /u/{creds['REDDIT_USERNAME']})"
        )

        self._reddit = praw.Reddit(
            client_id=creds["REDDIT_CLIENT_ID"],
            client_secret=creds["REDDIT_CLIENT_SECRET"],
            username=creds["REDDIT_USERNAME"],
            password=creds["REDDIT_PASSWORD"],
            user_agent=user_agent,
        )

        self._subreddits = [
            s.strip()
            for s in self._env(
                "ECHO_REDDIT_SUBREDDITS", "haloai,artificialintelligence"
            ).split(",")
            if s.strip()
        ]
        self._keywords = [
            k.strip()
            for k in self._env("ECHO_REDDIT_KEYWORDS", "halo-ai,halo ai").split(",")
            if k.strip()
        ]

        self.available = True

    # ------------------------------------------------------------------

    def listen(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not self._reddit:
            return results

        # Check inbox (mentions & replies)
        try:
            for item in self._reddit.inbox.unread(limit=25):
                results.append({
                    "platform": self.platform_name,
                    "type": "mention" if item.subject == "username mention" else "reply",
                    "text": item.body[:500],
                    "author": str(item.author),
                    "url": f"https://reddit.com{item.context}" if hasattr(item, "context") else "",
                    "ts": datetime.datetime.utcfromtimestamp(item.created_utc).isoformat(),
                    "meta": {"subject": item.subject},
                })
        except Exception:
            pass

        # Keyword search across monitored subreddits
        for sub_name in self._subreddits:
            try:
                subreddit = self._reddit.subreddit(sub_name)
                for kw in self._keywords:
                    for submission in subreddit.search(kw, sort="new", time_filter="day", limit=10):
                        results.append({
                            "platform": self.platform_name,
                            "type": "story",
                            "text": submission.title,
                            "author": str(submission.author),
                            "url": submission.url,
                            "ts": datetime.datetime.utcfromtimestamp(submission.created_utc).isoformat(),
                            "meta": {
                                "subreddit": sub_name,
                                "score": submission.score,
                                "num_comments": submission.num_comments,
                            },
                        })
            except Exception:
                pass

        return results

    def post(self, message: str) -> dict[str, Any]:
        if not self._reddit:
            return {"ok": False, "error": "Reddit client not initialised"}

        # Post to the first configured subreddit
        target = self._subreddits[0] if self._subreddits else "test"
        # Use first line as title, rest as body
        lines = message.strip().split("\n", 1)
        title = lines[0][:300]
        body = lines[1] if len(lines) > 1 else ""

        subreddit = self._reddit.subreddit(target)
        submission = subreddit.submit(title=title, selftext=body)

        return {
            "platform": self.platform_name,
            "ok": True,
            "id": submission.id,
            "url": submission.url,
        }

    def engage(self, target_id: str, action: str = "upvote") -> dict[str, Any]:
        if not self._reddit:
            return {"ok": False, "error": "Reddit client not initialised"}

        submission = self._reddit.submission(id=target_id)
        if action == "upvote":
            submission.upvote()
        elif action == "downvote":
            submission.downvote()
        elif action == "save":
            submission.save()
        else:
            return {"ok": False, "error": f"Unknown action: {action}"}

        return {"ok": True, "action": action, "target": target_id}

    def metrics(self) -> dict[str, Any]:
        if not self._reddit:
            return {}
        me = self._reddit.user.me()
        return {
            "username": str(me),
            "link_karma": me.link_karma,
            "comment_karma": me.comment_karma,
            "created_utc": datetime.datetime.utcfromtimestamp(me.created_utc).isoformat(),
        }
