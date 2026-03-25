"""
Echo platform agent — Discord (via discord.py).

This agent uses Discord's HTTP API directly for non-gateway operations
(posting announcements, reading recent messages) so it works without
running a persistent bot process.

For real-time listening, Echo would need to run the bot gateway in the
background — that is handled separately. This agent covers the REST
operations Echo needs.

Environment variables:
    DISCORD_BOT_TOKEN
    ECHO_DISCORD_GUILD_ID        (server to monitor)
    ECHO_DISCORD_CHANNEL_ID      (default channel for announcements)
    ECHO_DISCORD_LISTEN_CHANNELS (comma-separated channel IDs to monitor)
"""

from __future__ import annotations

import datetime
import json
import urllib.request
import warnings
from typing import Any

from agents.base import PlatformAgent

DISCORD_API = "https://discord.com/api/v10"


class DiscordAgent(PlatformAgent):
    platform_name = "discord"

    def _setup(self) -> None:
        self._token: str | None = None
        self._guild_id: str | None = None
        self._announce_channel: str | None = None
        self._listen_channels: list[str] = []

        token = self._env("DISCORD_BOT_TOKEN")
        if not token:
            warnings.warn("[echo/discord] DISCORD_BOT_TOKEN not set — agent disabled")
            return

        self._token = token
        self._guild_id = self._env("ECHO_DISCORD_GUILD_ID")
        self._announce_channel = self._env("ECHO_DISCORD_CHANNEL_ID")
        self._listen_channels = [
            c.strip()
            for c in self._env("ECHO_DISCORD_LISTEN_CHANNELS", "").split(",")
            if c.strip()
        ]

        self.available = True

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        url = f"{DISCORD_API}{path}"
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bot {self._token}")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "echo/halo-ai (https://halo-ai.dev, v1)")

        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}

    # ------------------------------------------------------------------

    def listen(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not self._token:
            return results

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
                    # Skip messages from our own bot
                    author = msg.get("author", {})
                    if author.get("bot"):
                        continue

                    results.append({
                        "platform": self.platform_name,
                        "type": "message",
                        "text": msg.get("content", "")[:500],
                        "author": f"{author.get('username', '')}#{author.get('discriminator', '')}",
                        "url": f"https://discord.com/channels/{self._guild_id}/{ch_id}/{msg.get('id', '')}",
                        "ts": msg.get("timestamp", ""),
                        "meta": {
                            "channel_id": ch_id,
                            "attachments": len(msg.get("attachments", [])),
                            "mentions": [u.get("username") for u in msg.get("mentions", [])],
                        },
                    })
            except Exception:
                pass

        return results

    def post(self, message: str) -> dict[str, Any]:
        if not self._token:
            return {"ok": False, "error": "Discord bot token not set"}
        if not self._announce_channel:
            return {"ok": False, "error": "ECHO_DISCORD_CHANNEL_ID not set"}

        try:
            resp = self._request("POST", f"/channels/{self._announce_channel}/messages", {
                "content": message[:2000],
            })
            return {
                "platform": self.platform_name,
                "ok": True,
                "id": resp.get("id", ""),
                "url": f"https://discord.com/channels/{self._guild_id}/{self._announce_channel}/{resp.get('id', '')}",
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def engage(self, target_id: str, action: str = "react") -> dict[str, Any]:
        """React to a message. target_id format: channel_id/message_id"""
        if not self._token:
            return {"ok": False, "error": "Discord bot token not set"}

        parts = target_id.split("/")
        if len(parts) != 2:
            return {"ok": False, "error": "target_id should be 'channel_id/message_id'"}

        channel_id, message_id = parts

        if action in ("react", "like"):
            emoji = "%F0%9F%91%8D"  # thumbs up, URL-encoded
            try:
                self._request(
                    "PUT",
                    f"/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me",
                )
                return {"ok": True, "action": "react", "target": target_id}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        return {"ok": False, "error": f"Unknown action: {action}"}

    def metrics(self) -> dict[str, Any]:
        if not self._token or not self._guild_id:
            return {"note": "Guild ID not set — cannot fetch metrics"}

        try:
            guild = self._request("GET", f"/guilds/{self._guild_id}?with_counts=true")
            return {
                "guild": guild.get("name", ""),
                "member_count": guild.get("approximate_member_count", 0),
                "online": guild.get("approximate_presence_count", 0),
            }
        except Exception as exc:
            return {"error": str(exc)}
