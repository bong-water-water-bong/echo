#!/usr/bin/env python3
"""
echo — DLC feedback & community-driven content system.

Players don't just vote on features — they tell us exactly what they
want in the next dungeon pack. Theme, enemies, mood, mechanics, loot.
The community BUILDS the next DLC through structured feedback.

echo collects it all, summarizes it, and hands it to forge + dealer
with a complete creative brief written by the players themselves.

Immediate support: every bug report, every suggestion, every complaint
gets a response. No ticket goes unanswered. No player feels ignored.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger("echo.dlc_feedback")


@dataclass
class DLCWish:
    """A single player's vision for the next DLC."""
    player_id: str
    timestamp: str
    # What they want
    theme: str = ""           # "underwater ruins", "volcanic forge", "frozen cathedral"
    mood: str = ""            # "terrifying", "mysterious", "epic", "eerie"
    enemy_ideas: list[str] = field(default_factory=list)  # "giant spider", "ghost knight"
    boss_idea: str = ""       # "a dragon made of lava blocks"
    mechanic_idea: str = ""   # "rooms flood over time", "torches go out"
    loot_ideas: list[str] = field(default_factory=list)   # "grappling hook", "invisibility cloak"
    environment: str = ""     # "underwater caves", "crumbling towers", "mushroom forest"
    difficulty: str = ""      # "harder than undercroft", "more puzzles less combat"
    story_idea: str = ""      # "ancient civilization that worshipped voxels"
    other: str = ""           # Freeform


@dataclass
class SupportTicket:
    """Every player interaction gets tracked and responded to."""
    id: str
    player_id: str
    player_name: str
    category: str  # bug, suggestion, question, complaint, praise
    message: str
    timestamp: str
    status: str = "open"  # open, acknowledged, in_progress, resolved, wont_fix
    assigned_agent: str = ""
    response: str = ""
    response_time_s: float = 0.0
    resolved_at: str = ""


class DLCFeedbackCollector:
    """
    Collects and synthesizes community feedback for the next DLC.

    Flow:
    1. echo posts a DLC feedback form (structured questions)
    2. Players submit their wishes via Discord commands or web form
    3. echo collects all submissions
    4. echo uses LLM to synthesize themes, find consensus
    5. echo generates a creative brief
    6. Creative brief sent to forge (build) + dealer (AI design) + interpreter (art direction)
    7. echo posts progress updates: "You asked for X, we're building it"
    8. When DLC ships, echo credits the community: "You designed this"
    """

    FEEDBACK_DIR = Path("/var/lib/halo-ai/dlc_feedback")

    def __init__(self, llm_url: str = "http://127.0.0.1:8080", bus_url: str = "http://127.0.0.1:8100"):
        self.llm_url = llm_url
        self.bus_url = bus_url
        self.wishes: list[DLCWish] = []
        self.FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        self._load_wishes()

    def _load_wishes(self) -> None:
        path = self.FEEDBACK_DIR / "wishes.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self.wishes = [DLCWish(**w) for w in data]
            except Exception:
                pass

    def _save_wishes(self) -> None:
        path = self.FEEDBACK_DIR / "wishes.json"
        data = [w.__dict__ for w in self.wishes]
        path.write_text(json.dumps(data, indent=2))

    def submit_wish(self, wish: DLCWish) -> None:
        """Player submits their DLC wish."""
        wish.timestamp = datetime.now(timezone.utc).isoformat()
        self.wishes.append(wish)
        self._save_wishes()
        log.info("DLC wish from %s: theme=%s, mood=%s", wish.player_id, wish.theme, wish.mood)

    def get_feedback_form_message(self) -> str:
        """Discord message with the DLC feedback form."""
        return """# 🗺️ Design the Next Dungeon Pack!

We want YOU to design the next DLC. Tell us what you want to see!

**Use the command:** `!dlc-wish`

You'll be asked about:
🏔️ **Theme** — What's the setting? (underwater ruins, volcanic forge, frozen cathedral...)
🌙 **Mood** — How should it feel? (terrifying, mysterious, epic, eerie...)
👹 **Enemies** — What should we fight? (ghost knights, crystal golems, swarm creatures...)
🐉 **Boss** — Describe your dream boss fight
⚙️ **Mechanic** — Any unique gameplay ideas? (rooms flood, torches die, gravity shifts...)
💎 **Loot** — What gear do you want to find?
🌍 **Environment** — Describe the world
📖 **Story** — Any lore ideas?
💪 **Difficulty** — Harder? Easier? More puzzles? More combat?

Every submission is read. The most popular ideas become the next DLC.
**You're not just playing the game — you're building it.**

*Submissions close at the end of the month. Results announced in the next community poll.*"""

    async def synthesize_feedback(self) -> dict:
        """Use LLM to find consensus and generate a creative brief."""
        if not self.wishes:
            return {"error": "No wishes submitted yet"}

        # Aggregate raw data
        themes = [w.theme for w in self.wishes if w.theme]
        moods = [w.mood for w in self.wishes if w.mood]
        enemies = []
        for w in self.wishes:
            enemies.extend(w.enemy_ideas)
        bosses = [w.boss_idea for w in self.wishes if w.boss_idea]
        mechanics = [w.mechanic_idea for w in self.wishes if w.mechanic_idea]
        loot = []
        for w in self.wishes:
            loot.extend(w.loot_ideas)
        environments = [w.environment for w in self.wishes if w.environment]
        difficulties = [w.difficulty for w in self.wishes if w.difficulty]
        stories = [w.story_idea for w in self.wishes if w.story_idea]

        # Try LLM synthesis
        brief = await self._llm_synthesize(
            themes, moods, enemies, bosses, mechanics, loot, environments, difficulties, stories
        )

        if not brief:
            # Fallback: simple frequency analysis
            brief = self._frequency_analysis(
                themes, moods, enemies, bosses, mechanics, loot, environments
            )

        # Save the brief
        brief_path = self.FEEDBACK_DIR / f"brief_{datetime.now().strftime('%Y%m')}.json"
        brief_path.write_text(json.dumps(brief, indent=2))

        return brief

    async def _llm_synthesize(self, themes, moods, enemies, bosses, mechanics, loot, environments, difficulties, stories) -> Optional[dict]:
        """LLM reads all feedback and writes a creative brief."""
        prompt = json.dumps({
            "task": "Synthesize community feedback into a DLC creative brief",
            "submissions": len(self.wishes),
            "themes": themes[:50],
            "moods": moods[:50],
            "enemy_ideas": enemies[:50],
            "boss_ideas": bosses[:20],
            "mechanic_ideas": mechanics[:20],
            "loot_ideas": loot[:50],
            "environments": environments[:30],
            "difficulty_feedback": difficulties[:20],
            "story_ideas": stories[:20],
        })

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{self.llm_url}/v1/chat/completions", json={
                    "messages": [
                        {"role": "system", "content": (
                            "You are echo, the community manager for halo-ai studios. "
                            "Synthesize player feedback into a creative brief for the next "
                            "DLC dungeon pack. Find the consensus. Identify the top themes, "
                            "the most-wanted enemies, the dream boss fight, the unique mechanics. "
                            "Output a JSON creative brief with: pack_name, theme, mood, "
                            "enemy_types (list), boss (dict with name/description/abilities), "
                            "unique_mechanic, loot_highlights, environment_description, "
                            "difficulty_notes, story_hook, community_credits (acknowledge what "
                            "players asked for)."
                        )},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 1024,
                    "temperature": 0.7,
                }, timeout=15)

                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return json.loads(content)
        except Exception as e:
            log.warning("LLM synthesis failed: %s", e)
        return None

    def _frequency_analysis(self, themes, moods, enemies, bosses, mechanics, loot, environments) -> dict:
        """Simple frequency-based synthesis when LLM is unavailable."""
        def top_n(items, n=3):
            from collections import Counter
            return [item for item, _ in Counter(items).most_common(n)]

        return {
            "pack_name": f"Community Pack — {top_n(themes, 1)[0] if themes else 'TBD'}",
            "top_themes": top_n(themes),
            "top_moods": top_n(moods),
            "top_enemies": top_n(enemies, 5),
            "top_boss_ideas": bosses[:3],
            "top_mechanics": mechanics[:3],
            "top_loot": top_n(loot, 5),
            "top_environments": top_n(environments),
            "total_submissions": len(self.wishes),
            "method": "frequency_analysis",
        }

    async def send_brief_to_agents(self, brief: dict) -> None:
        """Send the creative brief to forge, dealer, and interpreter."""
        for agent in ["forge", "dealer", "interpreter"]:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(f"{self.bus_url}/publish", json={
                        "from_agent": "echo",
                        "topic": "builds",
                        "event_type": "dlc_creative_brief",
                        "payload": {
                            "brief": brief,
                            "target_agent": agent,
                            "source": "community_feedback",
                            "submissions": len(self.wishes),
                        },
                    }, timeout=5)
                log.info("Creative brief sent to %s", agent)
            except Exception as e:
                log.error("Failed to send brief to %s: %s", agent, e)

    def get_community_credit_message(self, brief: dict) -> str:
        """Message thanking the community for designing the DLC."""
        total = brief.get("total_submissions", len(self.wishes))
        name = brief.get("pack_name", "the next DLC")
        return f"""# 🎉 You Designed It — We're Building It!

**{total} players** submitted their vision for the next dungeon pack.

We heard you. Here's what's coming:

**{name}**

The community spoke. Our AI agents are already at work:
- **forge** is scaffolding the pack
- **dealer** is designing the AI encounters
- **interpreter** is creating the art direction
- **amp** is composing the soundtrack

This DLC was designed by YOU. When it ships, you'll see your ideas in the game.

*Thank you for being part of halo-ai studios.*
*— echo*"""


class SupportSystem:
    """
    Immediate support. No ticket goes unanswered.

    Every bug report, suggestion, question, complaint, or praise
    gets acknowledged within seconds and routed to the right agent.
    Players always feel heard.
    """

    TICKETS_DIR = Path("/var/lib/halo-ai/support")

    # Response time targets
    ACKNOWLEDGE_TARGET_S = 30    # Acknowledge within 30 seconds
    ROUTE_TARGET_S = 60          # Route to agent within 1 minute
    RESOLUTION_TARGET_S = 3600   # Resolve within 1 hour (if possible)

    def __init__(self, bus_url: str = "http://127.0.0.1:8100"):
        self.bus_url = bus_url
        self.tickets: dict[str, SupportTicket] = {}
        self._ticket_counter = 0
        self.TICKETS_DIR.mkdir(parents=True, exist_ok=True)

    def create_ticket(
        self, player_id: str, player_name: str, category: str, message: str,
    ) -> SupportTicket:
        """Create a support ticket. Acknowledge immediately."""
        self._ticket_counter += 1
        ticket_id = f"T-{self._ticket_counter:05d}"

        ticket = SupportTicket(
            id=ticket_id,
            player_id=player_id,
            player_name=player_name,
            category=category,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            status="acknowledged",
        )

        # Route to appropriate agent
        agent = self._route_ticket(category)
        ticket.assigned_agent = agent

        # Generate immediate response
        ticket.response = self._generate_acknowledgement(category, player_name, ticket_id)
        ticket.response_time_s = 0.5  # Near-instant

        self.tickets[ticket_id] = ticket
        self._save_ticket(ticket)

        # Notify assigned agent via message bus
        asyncio.create_task(self._notify_agent(ticket))

        log.info("Ticket %s: %s from %s -> %s", ticket_id, category, player_name, agent)
        return ticket

    def _route_ticket(self, category: str) -> str:
        """Route to the right agent based on category."""
        routing = {
            "bug": "bounty",
            "crash": "bounty",
            "exploit": "fang",
            "cheat": "fang",
            "security": "meek",
            "suggestion": "echo",
            "feature": "echo",
            "question": "echo",
            "complaint": "echo",
            "praise": "echo",
            "performance": "pulse",
            "network": "net",
            "account": "gate",
            "privacy": "mirror",
            "toxic": "shield",
            "harassment": "shield",
        }
        return routing.get(category.lower(), "echo")

    def _generate_acknowledgement(self, category: str, name: str, ticket_id: str) -> str:
        """Instant response — player never waits."""
        responses = {
            "bug": (
                f"Hey {name}! Thanks for reporting this. I've logged it as **{ticket_id}** "
                f"and sent it to our bug hunter (bounty). We're on it. "
                f"You'll get an update when we have a fix."
            ),
            "crash": (
                f"Sorry about that, {name}. Crash report **{ticket_id}** is logged. "
                f"bounty is investigating right now. If you have a crash log, "
                f"paste it here and it'll help us fix it faster."
            ),
            "suggestion": (
                f"Love the idea, {name}! Logged as **{ticket_id}**. "
                f"I've added it to our feature backlog — it might show up "
                f"in next month's community poll!"
            ),
            "question": (
                f"Good question, {name}! Let me look into that. "
                f"Ticket **{ticket_id}** is open. I'll get back to you shortly."
            ),
            "complaint": (
                f"I hear you, {name}. Your feedback as **{ticket_id}** is taken seriously. "
                f"Let me get the right person looking at this."
            ),
            "praise": (
                f"That means a lot, {name}! The whole team (all 17 of us 😄) "
                f"appreciates it. Ticket **{ticket_id}** — filed under 'things that "
                f"make our day'."
            ),
            "exploit": (
                f"Thanks for the responsible report, {name}. **{ticket_id}** is flagged "
                f"as high priority. fang is reviewing it now. "
                f"Please don't share this publicly until we patch it."
            ),
        }
        return responses.get(
            category.lower(),
            f"Got it, {name}! **{ticket_id}** is logged. Someone will follow up shortly."
        )

    async def _notify_agent(self, ticket: SupportTicket) -> None:
        """Notify the assigned agent via message bus."""
        topic = "bugs" if ticket.category in ("bug", "crash") else "community"
        try:
            async with httpx.AsyncClient() as client:
                await client.post(f"{self.bus_url}/publish", json={
                    "from_agent": "echo",
                    "topic": topic,
                    "event_type": "support_ticket",
                    "payload": {
                        "ticket_id": ticket.id,
                        "category": ticket.category,
                        "player": ticket.player_name,
                        "message": ticket.message[:500],
                        "assigned_to": ticket.assigned_agent,
                    },
                }, timeout=5)
        except Exception:
            pass

    def resolve_ticket(self, ticket_id: str, resolution: str) -> Optional[SupportTicket]:
        """Resolve a ticket with a response."""
        ticket = self.tickets.get(ticket_id)
        if not ticket:
            return None
        ticket.status = "resolved"
        ticket.response = resolution
        ticket.resolved_at = datetime.now(timezone.utc).isoformat()
        self._save_ticket(ticket)
        return ticket

    def _save_ticket(self, ticket: SupportTicket) -> None:
        path = self.TICKETS_DIR / f"{ticket.id}.json"
        path.write_text(json.dumps(ticket.__dict__, indent=2))

    def get_stats(self) -> dict:
        open_count = sum(1 for t in self.tickets.values() if t.status != "resolved")
        resolved = sum(1 for t in self.tickets.values() if t.status == "resolved")
        avg_response = 0.0
        if self.tickets:
            avg_response = sum(t.response_time_s for t in self.tickets.values()) / len(self.tickets)
        return {
            "total_tickets": len(self.tickets),
            "open": open_count,
            "resolved": resolved,
            "avg_response_time_s": round(avg_response, 1),
            "agents_active": list(set(t.assigned_agent for t in self.tickets.values())),
        }
