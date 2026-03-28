#!/usr/bin/env python3
"""
echo — Steam store page management.

Handles the entire Steam presence autonomously:
- Coming Soon page setup and management
- Wishlists tracking
- Marketing campaign (timed announcements)
- Early access launch sequence
- halo-ai owners get direct early access link
- Community hub moderation (via shield)

echo manages all public-facing Steam content.
The user never touches the Steam backend.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("echo.steam")


@dataclass
class SteamPageConfig:
    """Steam store page configuration — echo manages this."""
    app_id: str = "0000000"  # Placeholder until registered
    app_name: str = "Voxel Extraction"
    developer: str = "halo-ai studios"
    publisher: str = "halo-ai studios"

    # Store page text
    short_description: str = (
        "A voxel PvE extraction dungeon crawler powered by AI. "
        "Every run is different — an AI game master controls enemies, "
        "generates worlds, and adapts to how you play. "
        "40-minute dungeon raids. Loot. Fight. Extract — or lose everything."
    )

    detailed_description: str = """
<h2>Every Run Is Different</h2>
A local AI game master (dealer) lives inside the game. It watches how you play
and reacts in real time — changing enemy tactics, triggering dynamic events,
placing loot that tempts you to stay too long. No two runs are the same.

<h2>Voxel Art, Photorealistic Shaders</h2>
Blocky geometry meets photorealistic materials. PBR shaders with SDFGI,
volumetric fog, caustic water, procedural stone and metal. The contrast
between voxel geometry and realistic surfaces IS the visual identity.
No raytracing needed — it runs on everything.

<h2>40-Minute Dungeon Raids</h2>
Drop into procedurally generated dungeons with 18-35 rooms. Clear enemies,
find loot, discover secrets. But the clock is ticking — extract before
time runs out or lose everything you found.

<h2>Dungeon Packs</h2>
The base game includes The Undercroft. New dungeon packs add unique themes,
enemies, bosses, and loot. Community creators can build their own packs.

<h2>Built By AI Agents</h2>
This game is developed, tested, deployed, and supported by an autonomous
team of 17 AI agents running on local hardware. No cloud. No monthly costs.
Just a machine and its agents.

<h2>PvE Only</h2>
No PvP. No toxicity. Just you (or your friends in co-op) against the dungeon.
The only enemy is the AI — and it's smart.
"""

    # Tags
    tags: list[str] = field(default_factory=lambda: [
        "Voxel", "Dungeon Crawler", "PvE", "Extraction",
        "Procedural Generation", "AI", "Co-op", "Indie",
        "Atmospheric", "Dark", "Loot", "Single-player",
        "Early Access", "Action", "RPG",
    ])

    # System requirements
    min_requirements: dict = field(default_factory=lambda: {
        "os": "Windows 10 / Linux",
        "processor": "4-core CPU, 3.0 GHz",
        "memory": "8 GB RAM",
        "graphics": "Vulkan-capable GPU, 4GB VRAM",
        "storage": "4 GB",
        "additional": "For AI features: 4GB additional RAM for local LLM",
    })

    rec_requirements: dict = field(default_factory=lambda: {
        "os": "Windows 11 / Linux (Arch, Ubuntu 24.04+)",
        "processor": "8-core CPU, 3.5 GHz",
        "memory": "16 GB RAM",
        "graphics": "Vulkan-capable GPU, 8GB VRAM",
        "storage": "8 GB",
        "additional": "AMD GPU recommended. AI game master runs best with GPU inference.",
    })


@dataclass
class MarketingCampaign:
    """Automated marketing campaign — echo handles everything."""

    phases: list[dict] = field(default_factory=lambda: [
        {
            "name": "Coming Soon",
            "actions": [
                "Set up Steam Coming Soon page",
                "Post announcement on Discord",
                "Start wishlists tracking",
                "Create dev log channel",
                "Post first dev blog: 'Building a game with AI agents'",
            ],
            "duration_days": 30,
        },
        {
            "name": "Hype Building",
            "actions": [
                "Weekly dev logs with screenshots/videos",
                "Monthly community polls for features",
                "Teaser trailer (forge generates, amp scores)",
                "Press kit distribution",
                "Creator/streamer early access keys",
            ],
            "duration_days": 60,
        },
        {
            "name": "Early Access Announcement",
            "actions": [
                "Announce early access date",
                "halo-ai owners get direct early access link",
                "Generate and send early access keys to halo-ai installers",
                "Final trailer (gameplay footage)",
                "Steam page update with launch date",
            ],
            "duration_days": 14,
        },
        {
            "name": "Early Access Launch",
            "actions": [
                "Release on Steam Early Access",
                "Discord announcement + everyone ping",
                "Launch day dev stream (automated)",
                "Monitor crash reports (pulse)",
                "Hot patch if needed (forge → sentinel → deploy)",
                "Community feedback collection",
            ],
            "duration_days": 1,
        },
        {
            "name": "Post-Launch",
            "actions": [
                "Daily community monitoring (echo + shield)",
                "Weekly patch notes",
                "Monthly community polls",
                "DLC pack announcements",
                "Continuous improvement based on player data",
            ],
            "duration_days": -1,  # Ongoing forever
        },
    ])


class EarlyAccessManager:
    """
    Manages early access keys and halo-ai owner perks.

    halo-ai users who install the full stack get a direct link
    to the game's early access. They're the first community.
    """

    def __init__(self):
        self.keys_generated: list[dict] = []
        self.halo_ai_owners: list[str] = []  # Tracked by installation telemetry (opt-in)

    def generate_early_access_key(self, owner_id: str) -> str:
        """Generate a Steam early access key for a halo-ai owner."""
        import hashlib
        key_hash = hashlib.sha256(f"halo-ai-ea-{owner_id}-{datetime.now().isoformat()}".encode()).hexdigest()[:16]
        key = f"HALO-{key_hash[:4].upper()}-{key_hash[4:8].upper()}-{key_hash[8:12].upper()}-{key_hash[12:16].upper()}"

        self.keys_generated.append({
            "key": key,
            "owner_id": owner_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "redeemed": False,
        })

        log.info("Generated early access key for halo-ai owner: %s", owner_id)
        return key

    def get_early_access_link(self) -> str:
        """Get the direct Steam early access link."""
        return f"https://store.steampowered.com/app/{SteamPageConfig().app_id}"

    def get_stats(self) -> dict:
        return {
            "keys_generated": len(self.keys_generated),
            "keys_redeemed": sum(1 for k in self.keys_generated if k["redeemed"]),
            "halo_ai_owners": len(self.halo_ai_owners),
        }


class SteamPageManager:
    """
    Manages the full Steam presence. echo handles everything.

    Setup sequence:
    1. Register Steam app (manual — only thing the user does once)
    2. echo configures Coming Soon page
    3. echo runs marketing campaign on autopilot
    4. echo manages early access launch
    5. echo handles post-launch forever
    """

    def __init__(self):
        self.config = SteamPageConfig()
        self.campaign = MarketingCampaign()
        self.early_access = EarlyAccessManager()
        self.current_phase: int = 0
        self.wishlists: int = 0
        self.page_views: int = 0

    def get_current_phase(self) -> dict:
        if self.current_phase < len(self.campaign.phases):
            return self.campaign.phases[self.current_phase]
        return self.campaign.phases[-1]  # Post-launch

    def advance_phase(self) -> dict:
        if self.current_phase < len(self.campaign.phases) - 1:
            self.current_phase += 1
            phase = self.get_current_phase()
            log.info("Marketing phase: %s", phase["name"])
            return phase
        return self.get_current_phase()

    def status(self) -> dict:
        phase = self.get_current_phase()
        return {
            "app_id": self.config.app_id,
            "phase": phase["name"],
            "phase_actions": phase["actions"],
            "wishlists": self.wishlists,
            "page_views": self.page_views,
            "early_access_keys": self.early_access.get_stats(),
        }
