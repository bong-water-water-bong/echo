"""
Echo platform agent — Discord.

Supports TWO modes:
  1. Webhook mode (default) — zero dependencies, just a URL. Posts announcements.
     Set DISCORD_WEBHOOK_URL and you're done.

  2. Bot mode — full monitoring, reactions, metrics. Needs a bot token.
     Set DISCORD_BOT_TOKEN + channel/guild IDs.

Webhook mode is the recommended default. It requires no bot application,
no OAuth, no permissions — just create a webhook in Discord server settings
and paste the URL.

Environment variables:
    # Webhook mode (recommended)
    DISCORD_WEBHOOK_URL          — Discord webhook URL for announcements
    DISCORD_WEBHOOK_NAME         — Display name (default: Halo AI)

    # Bot mode (optional, for monitoring)
    DISCORD_BOT_TOKEN
    ECHO_DISCORD_GUILD_ID        — Server to monitor
    ECHO_DISCORD_CHANNEL_ID      — Default channel for announcements
    ECHO_DISCORD_LISTEN_CHANNELS — Comma-separated channel IDs to monitor
"""

from __future__ import annotations

import datetime
import json
import urllib.request
import urllib.error
import warnings
from typing import Any

from agents.base import PlatformAgent

DISCORD_API = "https://discord.com/api/v10"


class DiscordAgent(PlatformAgent):
    platform_name = "discord"

    def _setup(self) -> None:
        self._webhook_url: str | None = None
        self._webhook_name: str = "Halo AI"
        self._token: str | None = None
        self._guild_id: str | None = None
        self._announce_channel: str | None = None
        self._listen_channels: list[str] = []
        self._mode: str = "none"

        # Webhook mode — simplest, recommended
        webhook = self._env("DISCORD_WEBHOOK_URL")
        if webhook:
            self._webhook_url = webhook
            self._webhook_name = self._env("DISCORD_WEBHOOK_NAME", "Halo AI")
            self._mode = "webhook"
            self.available = True

        # Bot mode — full features
        token = self._env("DISCORD_BOT_TOKEN")
        if token:
            self._token = token
            self._guild_id = self._env("ECHO_DISCORD_GUILD_ID")
            self._announce_channel = self._env("ECHO_DISCORD_CHANNEL_ID")
            self._listen_channels = [
                c.strip()
                for c in self._env("ECHO_DISCORD_LISTEN_CHANNELS", "").split(",")
                if c.strip()
            ]
            self._mode = "bot" if not self._webhook_url else "both"
            self.available = True

        if not self.available:
            warnings.warn(
                "[echo/discord] Set DISCORD_WEBHOOK_URL (easy) or DISCORD_BOT_TOKEN (full) — agent disabled"
            )

    # ------------------------------------------------------------------
    # Webhook posting — zero dependencies
    # ------------------------------------------------------------------

    def _webhook_post(self, message: str) -> dict[str, Any]:
        """Post via webhook. No bot token needed."""
        payload = json.dumps({
            "username": self._webhook_name,
            "content": message[:2000],
        }).encode()

        req = urllib.request.Request(
            self._webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            resp = urllib.request.urlopen(req, timeout=10)
            return {
                "platform": self.platform_name,
                "mode": "webhook",
                "ok": resp.status == 204,
            }
        except urllib.error.HTTPError as e:
            return {"ok": False, "error": f"Discord {e.code}: {e.read().decode()[:200]}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Bot API helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        url = f"{DISCORD_API}{path}"
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bot {self._token}")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "echo/halo-ai (v1)")

        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}

    # ------------------------------------------------------------------
    # PlatformAgent interface
    # ------------------------------------------------------------------

    def listen(self) -> list[dict[str, Any]]:
        """Monitor channels for mentions. Requires bot mode."""
        if not self._token:
            return []

        results: list[dict[str, Any]] = []
        channels = self._listen_channels
        if not channels and self._announce_channel:
            channels = [self._announce_channel]

        for ch_id in channels:
            try:
                messages = self._request("GET", f"/channels/{ch_id}/messages?limit=25")
                cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).isoformat()

                for msg in messages:
                    if msg.get("timestamp", "") < cutoff:
                        continue
                    author = msg.get("author", {})
                    if author.get("bot"):
                        continue

                    results.append({
                        "platform": self.platform_name,
                        "type": "message",
                        "text": msg.get("content", "")[:500],
                        "author": author.get("username", ""),
                        "url": f"https://discord.com/channels/{self._guild_id}/{ch_id}/{msg.get('id', '')}",
                        "ts": msg.get("timestamp", ""),
                    })
            except Exception:
                pass

        return results

    def post(self, message: str) -> dict[str, Any]:
        """Post an announcement. Uses webhook if available, falls back to bot API."""
        # Prefer webhook — simpler, no permissions needed
        if self._webhook_url:
            return self._webhook_post(message)

        # Fall back to bot API
        if not self._token:
            return {"ok": False, "error": "No webhook URL or bot token configured"}
        if not self._announce_channel:
            return {"ok": False, "error": "ECHO_DISCORD_CHANNEL_ID not set"}

        try:
            resp = self._request("POST", f"/channels/{self._announce_channel}/messages", {
                "content": message[:2000],
            })
            return {
                "platform": self.platform_name,
                "mode": "bot",
                "ok": True,
                "id": resp.get("id", ""),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def engage(self, target_id: str, action: str = "react") -> dict[str, Any]:
        """React to a message. Requires bot mode. target_id: channel_id/message_id"""
        if not self._token:
            return {"ok": False, "error": "Bot token required for reactions"}

        parts = target_id.split("/")
        if len(parts) != 2:
            return {"ok": False, "error": "target_id should be 'channel_id/message_id'"}

        channel_id, message_id = parts
        emoji = "%F0%9F%91%8D"  # thumbs up

        try:
            self._request(
                "PUT",
                f"/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me",
            )
            return {"ok": True, "action": "react", "target": target_id}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def metrics(self) -> dict[str, Any]:
        info: dict[str, Any] = {"mode": self._mode}

        if self._token and self._guild_id:
            try:
                guild = self._request("GET", f"/guilds/{self._guild_id}?with_counts=true")
                info.update({
                    "guild": guild.get("name", ""),
                    "members": guild.get("approximate_member_count", 0),
                    "online": guild.get("approximate_presence_count", 0),
                })
            except Exception as exc:
                info["error"] = str(exc)

        if self._webhook_url:
            info["webhook"] = "configured"

        return info
