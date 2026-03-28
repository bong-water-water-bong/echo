#!/usr/bin/env python3
"""
echo — Community polling system.

Runs monthly feature polls so the community drives the roadmap.
Agents pick up the winning features and work on them autonomously.

Fully hands-off: echo creates the poll, collects votes, announces
results, and assigns work to the appropriate agents.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger("echo.polls")


@dataclass
class PollOption:
    id: str
    title: str
    description: str
    agent_owner: str  # Which agent would implement this
    votes: int = 0
    emoji: str = ""


@dataclass
class Poll:
    id: str
    title: str
    description: str
    options: list[PollOption]
    created_at: str = ""
    closes_at: str = ""
    is_active: bool = True
    results_announced: bool = False

    def to_discord_message(self) -> str:
        lines = [
            f"# 🗳️ {self.title}",
            "",
            self.description,
            "",
            "**Vote by reacting with the corresponding emoji!**",
            "",
        ]
        for i, opt in enumerate(self.options):
            emoji = opt.emoji or f"{i + 1}️⃣"
            lines.append(f"{emoji} **{opt.title}** — {opt.description}")
        lines.append("")
        lines.append(f"*Poll closes: {self.closes_at}*")
        lines.append("*Results will be announced and winning features assigned to agents automatically.*")
        return "\n".join(lines)

    def results_message(self) -> str:
        sorted_opts = sorted(self.options, key=lambda o: o.votes, reverse=True)
        lines = [
            f"# 📊 Poll Results — {self.title}",
            "",
        ]
        for i, opt in enumerate(sorted_opts):
            bar_len = int((opt.votes / max(1, sorted_opts[0].votes)) * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "  "
            lines.append(f"{medal} **{opt.title}** — {opt.votes} votes")
            lines.append(f"    `{bar}`")
        lines.append("")
        winner = sorted_opts[0]
        lines.append(f"**Winner: {winner.title}** — assigned to **{winner.agent_owner}**")
        lines.append("*Work begins immediately. Updates in #dev-log.*")
        return "\n".join(lines)


class PollManager:
    """
    Manages community polls. Fully autonomous.

    Monthly cycle:
    1. echo generates poll from feature backlog + agent suggestions
    2. Poll posted to Discord
    3. Community votes for 7 days
    4. Results tallied and announced
    5. Winning feature assigned to responsible agent
    6. Agent begins work
    7. echo posts progress updates
    """

    POLLS_DIR = Path("/var/lib/halo-ai/polls")
    POLL_DURATION_DAYS = 7
    POLL_INTERVAL_DAYS = 30  # Monthly

    def __init__(self, webhook_poster=None, message_bus_url: str = "http://127.0.0.1:8100"):
        self.poster = webhook_poster
        self.bus_url = message_bus_url
        self.polls: dict[str, Poll] = {}
        self.feature_backlog: list[dict] = []

        self.POLLS_DIR.mkdir(parents=True, exist_ok=True)
        self._load_polls()

    def _load_polls(self) -> None:
        """Load existing polls from disk."""
        for f in self.POLLS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                options = [PollOption(**o) for o in data.get("options", [])]
                poll = Poll(
                    id=data["id"],
                    title=data["title"],
                    description=data["description"],
                    options=options,
                    created_at=data.get("created_at", ""),
                    closes_at=data.get("closes_at", ""),
                    is_active=data.get("is_active", False),
                    results_announced=data.get("results_announced", False),
                )
                self.polls[poll.id] = poll
            except Exception as e:
                log.error("Failed to load poll %s: %s", f, e)

    def _save_poll(self, poll: Poll) -> None:
        """Persist poll to disk."""
        data = {
            "id": poll.id,
            "title": poll.title,
            "description": poll.description,
            "options": [
                {"id": o.id, "title": o.title, "description": o.description,
                 "agent_owner": o.agent_owner, "votes": o.votes, "emoji": o.emoji}
                for o in poll.options
            ],
            "created_at": poll.created_at,
            "closes_at": poll.closes_at,
            "is_active": poll.is_active,
            "results_announced": poll.results_announced,
        }
        path = self.POLLS_DIR / f"{poll.id}.json"
        path.write_text(json.dumps(data, indent=2))

    def create_monthly_poll(self, options: list[dict] = None) -> Poll:
        """Create this month's feature poll."""
        now = datetime.now(timezone.utc)
        poll_id = f"poll-{now.strftime('%Y-%m')}"
        closes = now + timedelta(days=self.POLL_DURATION_DAYS)

        if not options:
            options = self._generate_default_options()

        poll_options = []
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]
        for i, opt in enumerate(options[:6]):
            poll_options.append(PollOption(
                id=opt.get("id", f"opt_{i}"),
                title=opt["title"],
                description=opt["description"],
                agent_owner=opt.get("agent", "forge"),
                emoji=emojis[i] if i < len(emojis) else "",
            ))

        poll = Poll(
            id=poll_id,
            title=f"What should we build next? — {now.strftime('%B %Y')}",
            description="Vote for the feature you want most! The winning feature gets built by our AI agents.",
            options=poll_options,
            created_at=now.isoformat(),
            closes_at=closes.isoformat(),
        )

        self.polls[poll.id] = poll
        self._save_poll(poll)
        log.info("Created poll: %s with %d options", poll.id, len(poll_options))
        return poll

    def _generate_default_options(self) -> list[dict]:
        """Default feature options when no backlog is provided."""
        return [
            {"id": "new_dungeon", "title": "New Dungeon Pack", "description": "A brand new themed dungeon with unique enemies and loot", "agent": "forge"},
            {"id": "new_enemies", "title": "New Enemy Types", "description": "More variety in combat encounters", "agent": "dealer"},
            {"id": "new_weapons", "title": "New Weapons & Gear", "description": "Expand the arsenal with new tools of destruction", "agent": "forge"},
            {"id": "coop", "title": "Co-op Multiplayer", "description": "Play with friends — PvE co-op extraction runs", "agent": "net"},
            {"id": "modding", "title": "Modding Support", "description": "Let the community create custom dungeons and content", "agent": "forge"},
            {"id": "story", "title": "Story Campaign", "description": "A narrative-driven campaign mode with lore and cutscenes", "agent": "dealer"},
        ]

    async def post_poll(self, poll: Poll) -> bool:
        """Post the poll to Discord."""
        if not self.poster:
            log.warning("No webhook poster configured")
            return False
        return await self.poster.post("community", poll.to_discord_message())

    async def close_poll(self, poll_id: str) -> Optional[Poll]:
        """Close a poll and announce results."""
        poll = self.polls.get(poll_id)
        if not poll:
            return None

        poll.is_active = False
        self._save_poll(poll)

        # Announce results
        if self.poster:
            await self.poster.post("announcements", poll.results_message())

        # Notify message bus — winning feature assigned
        winner = max(poll.options, key=lambda o: o.votes)
        await self._assign_feature(winner)

        poll.results_announced = True
        self._save_poll(poll)

        log.info("Poll %s closed. Winner: %s -> %s", poll_id, winner.title, winner.agent_owner)
        return poll

    async def _assign_feature(self, winner: PollOption) -> None:
        """Notify the responsible agent via message bus."""
        try:
            async with httpx.AsyncClient() as client:
                await client.post(f"{self.bus_url}/publish", json={
                    "from_agent": "echo",
                    "topic": "builds",
                    "event_type": "feature_assigned",
                    "payload": {
                        "feature_id": winner.id,
                        "title": winner.title,
                        "description": winner.description,
                        "assigned_to": winner.agent_owner,
                        "source": "community_poll",
                        "votes": winner.votes,
                    },
                }, timeout=5)
        except Exception as e:
            log.error("Failed to assign feature: %s", e)

    def add_to_backlog(self, feature: dict) -> None:
        """Add a feature suggestion to the backlog for future polls."""
        self.feature_backlog.append(feature)

    def get_active_poll(self) -> Optional[Poll]:
        for poll in self.polls.values():
            if poll.is_active:
                return poll
        return None
