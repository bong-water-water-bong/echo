"""
Base class for Echo platform agents.

Every platform agent must subclass PlatformAgent and implement the
abstract methods. Credentials are pulled from environment variables;
if missing the agent marks itself as unavailable rather than crashing.
"""

from __future__ import annotations

import abc
import os
from typing import Any


class PlatformAgent(abc.ABC):
    """
    Abstract base for a social-media platform agent.

    Subclasses must set `platform_name` and implement the four core methods.
    """

    platform_name: str = "unknown"

    def __init__(self) -> None:
        self.available: bool = False
        self._setup()

    # ------------------------------------------------------------------
    # Credential helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _env(key: str, default: str | None = None) -> str | None:
        """Fetch an environment variable, returning *default* if unset."""
        return os.environ.get(key, default)

    @staticmethod
    def _require_env(*keys: str) -> dict[str, str]:
        """
        Return a dict of env values for *keys*.

        Raises ``EnvironmentError`` if any key is missing or empty.
        """
        values = {}
        missing = []
        for k in keys:
            v = os.environ.get(k)
            if not v:
                missing.append(k)
            else:
                values[k] = v
        if missing:
            raise EnvironmentError(
                f"Missing environment variable(s): {', '.join(missing)}"
            )
        return values

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _setup(self) -> None:
        """
        Called during __init__. Subclasses should override this to
        load credentials and initialise their API client.  Set
        ``self.available = True`` on success.
        """

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def listen(self) -> list[dict[str, Any]]:
        """
        Poll the platform for new mentions / relevant activity.

        Returns a list of standardised dicts::

            {
                "platform": "<name>",
                "type": "mention" | "comment" | "story" | …,
                "text": "…",
                "author": "…",
                "url": "…",
                "ts": "<ISO-8601>",
                "meta": { … }
            }
        """
        ...

    @abc.abstractmethod
    def post(self, message: str) -> dict[str, Any]:
        """
        Publish *message* on the platform.

        Returns a standardised result dict::

            {
                "platform": "<name>",
                "url": "…",
                "id": "…",
                "ok": True
            }
        """
        ...

    @abc.abstractmethod
    def engage(self, target_id: str, action: str = "like") -> dict[str, Any]:
        """
        Engage with a piece of content (like, retweet, upvote, etc.).

        Returns a result dict with at least ``{"ok": True/False}``.
        """
        ...

    @abc.abstractmethod
    def metrics(self) -> dict[str, Any]:
        """
        Return current account / channel metrics.

        Returns a dict of key-value pairs, e.g.::

            {"followers": 1234, "posts_today": 5}
        """
        ...
