#!/usr/bin/env python3
"""
echo — DLC Design Questionnaire.

A carefully curated checkbox-based questionnaire that collects
structured feedback on what the next DLC should be. Not freeform
chaos — guided choices that we can compile into real data.

Players who get their ideas chosen get the DLC FREE FOREVER.
That's the incentive. Make the game better, get rewarded.

Flow:
1. Poll closes → questionnaire opens
2. Players fill out checkboxes + optional freeform
3. Results compiled automatically
4. Top choices become the DLC spec
5. Contributors whose ideas made it in → free DLC key
6. Agents build the pack
7. Ship it
"""

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger("echo.questionnaire")


# ── Curated Options ────────────────────────────────────────────
# These are the checkboxes. Carefully designed categories with
# real options that map directly to things forge can build.

THEME_OPTIONS = [
    {"id": "volcanic", "label": "Volcanic Forge", "desc": "Lava rivers, obsidian walls, heat mechanics"},
    {"id": "underwater", "label": "Drowned Depths", "desc": "Flooded ruins, water pressure, bioluminescence"},
    {"id": "frozen", "label": "Frozen Cathedral", "desc": "Ice caverns, blizzards, frozen enemies"},
    {"id": "fungal", "label": "Mycelium Hive", "desc": "Giant mushrooms, spore clouds, living walls"},
    {"id": "mechanical", "label": "Clockwork Foundry", "desc": "Gears, pistons, mechanical enemies, steam"},
    {"id": "void", "label": "The Void", "desc": "Floating islands, gravity shifts, cosmic horror"},
    {"id": "overgrown", "label": "Overgrown Citadel", "desc": "Ancient city reclaimed by nature, vine puzzles"},
    {"id": "crystal", "label": "Crystal Sanctum", "desc": "Refracting light puzzles, crystal golems, prisms"},
]

MOOD_OPTIONS = [
    {"id": "terrifying", "label": "Terrifying", "desc": "Horror elements, jump scares, dread"},
    {"id": "epic", "label": "Epic", "desc": "Grand scale, massive rooms, legendary encounters"},
    {"id": "mysterious", "label": "Mysterious", "desc": "Hidden lore, puzzles, secrets everywhere"},
    {"id": "chaotic", "label": "Chaotic", "desc": "Nonstop action, swarms, destruction"},
    {"id": "eerie", "label": "Eerie", "desc": "Unsettling atmosphere, things feel wrong"},
    {"id": "desperate", "label": "Desperate", "desc": "Survival pressure, scarce resources, tension"},
]

ENEMY_OPTIONS = [
    {"id": "swarm", "label": "Swarm Creatures", "desc": "Small, fast, overwhelming in numbers"},
    {"id": "golem", "label": "Golems", "desc": "Slow, massive, destructible armor"},
    {"id": "ghost", "label": "Spectral", "desc": "Phase through walls, can't always hit them"},
    {"id": "mimic", "label": "Mimics", "desc": "Disguised as loot or environment"},
    {"id": "ranged", "label": "Ranged Attackers", "desc": "Archers, spitters, things that shoot"},
    {"id": "elite", "label": "Elite Warriors", "desc": "Fewer but deadly, mini-boss tier"},
    {"id": "environmental", "label": "Environmental Hazards", "desc": "The dungeon itself attacks you"},
    {"id": "summoner", "label": "Summoners", "desc": "Spawn other enemies, priority targets"},
]

BOSS_OPTIONS = [
    {"id": "multi_phase", "label": "Multi-Phase Boss", "desc": "Changes form/tactics as health drops"},
    {"id": "arena", "label": "Arena Boss", "desc": "Destroys the environment during the fight"},
    {"id": "puzzle_boss", "label": "Puzzle Boss", "desc": "Can't just brute force — need strategy"},
    {"id": "duo", "label": "Dual Bosses", "desc": "Two bosses that work together"},
    {"id": "chase", "label": "Chase Boss", "desc": "Pursues you through multiple rooms"},
    {"id": "stealth", "label": "Stealth Boss", "desc": "Hunts you in the dark, you hunt it back"},
]

MECHANIC_OPTIONS = [
    {"id": "flooding", "label": "Rising Water", "desc": "Rooms slowly flood — get out or drown"},
    {"id": "darkness", "label": "Lights Out", "desc": "Torches die, limited visibility, audio matters"},
    {"id": "gravity", "label": "Gravity Shifts", "desc": "Walk on walls/ceiling, disorienting"},
    {"id": "corruption", "label": "Corruption Spread", "desc": "Voxels decay over time, paths close"},
    {"id": "time_loop", "label": "Time Pressure Rooms", "desc": "Room resets if not cleared fast enough"},
    {"id": "stealth_zones", "label": "Stealth Sections", "desc": "Avoid detection or trigger swarms"},
    {"id": "destructible", "label": "Full Destruction", "desc": "Blow open any wall, make your own path"},
    {"id": "weather", "label": "Weather Inside", "desc": "Rain, fog, wind inside the dungeon"},
]

LOOT_OPTIONS = [
    {"id": "weapons", "label": "New Weapons", "desc": "More tools of destruction"},
    {"id": "armor", "label": "Armor Sets", "desc": "Set bonuses, visual customization"},
    {"id": "consumables", "label": "New Consumables", "desc": "Potions, grenades, buffs"},
    {"id": "tools", "label": "Utility Tools", "desc": "Grappling hook, torch, scanner"},
    {"id": "cosmetics", "label": "Cosmetics", "desc": "Skins, effects, visual flair"},
    {"id": "materials", "label": "Crafting Materials", "desc": "Build and upgrade gear"},
    {"id": "relics", "label": "Unique Relics", "desc": "One-of-a-kind items with special powers"},
]

DIFFICULTY_OPTIONS = [
    {"id": "harder", "label": "Harder Than Undercroft", "desc": "More enemies, smarter AI, less time"},
    {"id": "same", "label": "Same Difficulty", "desc": "Similar challenge, new content"},
    {"id": "easier", "label": "More Accessible", "desc": "Good for newer players"},
    {"id": "scaling", "label": "Scaling Difficulty", "desc": "Gets harder the deeper you go"},
    {"id": "more_puzzles", "label": "More Puzzles", "desc": "Less combat, more brain teasers"},
    {"id": "more_combat", "label": "More Combat", "desc": "Less puzzles, more fighting"},
]


@dataclass
class QuestionnaireResponse:
    """A player's completed questionnaire."""
    player_id: str
    player_name: str
    timestamp: str = ""
    # Checkbox selections (lists of option IDs)
    themes: list[str] = field(default_factory=list)       # Pick up to 3
    moods: list[str] = field(default_factory=list)         # Pick up to 2
    enemies: list[str] = field(default_factory=list)       # Pick up to 4
    boss_type: list[str] = field(default_factory=list)     # Pick up to 2
    mechanics: list[str] = field(default_factory=list)     # Pick up to 3
    loot: list[str] = field(default_factory=list)          # Pick up to 3
    difficulty: list[str] = field(default_factory=list)     # Pick 1
    # Optional freeform
    custom_idea: str = ""       # One original idea (max 280 chars)
    pack_name_idea: str = ""    # Suggest a name


@dataclass
class QuestionnaireResults:
    """Compiled results from all responses."""
    total_responses: int = 0
    top_themes: list[dict] = field(default_factory=list)
    top_moods: list[dict] = field(default_factory=list)
    top_enemies: list[dict] = field(default_factory=list)
    top_boss: list[dict] = field(default_factory=list)
    top_mechanics: list[dict] = field(default_factory=list)
    top_loot: list[dict] = field(default_factory=list)
    top_difficulty: list[dict] = field(default_factory=list)
    best_custom_ideas: list[dict] = field(default_factory=list)
    best_names: list[dict] = field(default_factory=list)
    # Players whose ideas made it in — get FREE DLC
    contributors_rewarded: list[dict] = field(default_factory=list)


class DLCQuestionnaire:
    """
    The DLC design questionnaire. Curated checkboxes.
    Compiles results. Rewards contributors.
    """

    DATA_DIR = Path("/var/lib/halo-ai/questionnaire")

    def __init__(self, bus_url: str = "http://127.0.0.1:8100"):
        self.bus_url = bus_url
        self.responses: list[QuestionnaireResponse] = []
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._load_responses()

    def _load_responses(self) -> None:
        path = self.DATA_DIR / "responses.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self.responses = [QuestionnaireResponse(**r) for r in data]
            except Exception:
                pass

    def _save_responses(self) -> None:
        path = self.DATA_DIR / "responses.json"
        data = [r.__dict__ for r in self.responses]
        path.write_text(json.dumps(data, indent=2))

    def submit(self, response: QuestionnaireResponse) -> dict:
        """Player submits their questionnaire."""
        # Validate limits
        response.themes = response.themes[:3]
        response.moods = response.moods[:2]
        response.enemies = response.enemies[:4]
        response.boss_type = response.boss_type[:2]
        response.mechanics = response.mechanics[:3]
        response.loot = response.loot[:3]
        response.difficulty = response.difficulty[:1]
        response.custom_idea = response.custom_idea[:280]
        response.pack_name_idea = response.pack_name_idea[:50]
        response.timestamp = datetime.now(timezone.utc).isoformat()

        # Check for duplicate
        existing = [r for r in self.responses if r.player_id == response.player_id]
        if existing:
            # Update their response (they can change their mind)
            self.responses = [r for r in self.responses if r.player_id != response.player_id]

        self.responses.append(response)
        self._save_responses()

        log.info("Questionnaire from %s: themes=%s", response.player_name, response.themes)
        return {
            "status": "submitted",
            "message": f"Thanks {response.player_name}! Your vote is in. "
                       f"If your ideas make it into the DLC, you get it FREE.",
        }

    def compile_results(self) -> QuestionnaireResults:
        """Compile all responses into actionable results."""
        if not self.responses:
            return QuestionnaireResults()

        results = QuestionnaireResults(total_responses=len(self.responses))

        # Count votes per category
        results.top_themes = self._tally("themes", THEME_OPTIONS)
        results.top_moods = self._tally("moods", MOOD_OPTIONS)
        results.top_enemies = self._tally("enemies", ENEMY_OPTIONS)
        results.top_boss = self._tally("boss_type", BOSS_OPTIONS)
        results.top_mechanics = self._tally("mechanics", MECHANIC_OPTIONS)
        results.top_loot = self._tally("loot", LOOT_OPTIONS)
        results.top_difficulty = self._tally("difficulty", DIFFICULTY_OPTIONS)

        # Collect custom ideas (non-empty)
        custom_ideas = [
            {"player": r.player_name, "player_id": r.player_id, "idea": r.custom_idea}
            for r in self.responses if r.custom_idea.strip()
        ]
        results.best_custom_ideas = custom_ideas

        # Collect name suggestions
        name_ideas = [
            {"player": r.player_name, "name": r.pack_name_idea}
            for r in self.responses if r.pack_name_idea.strip()
        ]
        # Count name frequency
        name_counter = Counter(n["name"].lower().strip() for n in name_ideas)
        results.best_names = [
            {"name": name, "votes": count}
            for name, count in name_counter.most_common(5)
        ]

        # Determine who gets rewarded
        results.contributors_rewarded = self._determine_rewards(results)

        # Save results
        results_path = self.DATA_DIR / f"results_{datetime.now().strftime('%Y%m')}.json"
        results_path.write_text(json.dumps(results.__dict__, indent=2))

        log.info("Compiled %d responses. %d contributors rewarded.",
                 results.total_responses, len(results.contributors_rewarded))

        return results

    def _tally(self, field_name: str, options: list[dict]) -> list[dict]:
        """Count votes for each option in a category."""
        counter = Counter()
        for response in self.responses:
            selections = getattr(response, field_name, [])
            for sel in selections:
                counter[sel] += 1

        # Map back to option details with vote counts
        results = []
        for option in options:
            votes = counter.get(option["id"], 0)
            results.append({
                "id": option["id"],
                "label": option["label"],
                "desc": option["desc"],
                "votes": votes,
                "pct": round(votes / max(len(self.responses), 1) * 100, 1),
            })

        # Sort by votes descending
        results.sort(key=lambda x: x["votes"], reverse=True)
        return results

    def _determine_rewards(self, results: QuestionnaireResults) -> list[dict]:
        """
        Determine which players get free DLC.

        Rewarded if:
        - Their theme pick is #1
        - Their custom idea is selected for implementation
        - Their pack name is chosen
        - They voted for 3+ winning options across categories
        """
        # Get winning IDs (top pick in each category)
        winners = set()
        for category in [results.top_themes, results.top_moods, results.top_enemies,
                         results.top_boss, results.top_mechanics, results.top_loot]:
            if category:
                winners.add(category[0]["id"])

        rewarded = []
        for response in self.responses:
            score = 0
            reasons = []

            # Check how many winning options they picked
            all_picks = (response.themes + response.moods + response.enemies +
                         response.boss_type + response.mechanics + response.loot)
            matching = [p for p in all_picks if p in winners]
            score = len(matching)

            if score >= 3:
                reasons.append(f"Picked {score} winning options")

            # Custom idea bonus (all custom ideas reviewed, best ones selected later)
            if response.custom_idea.strip():
                reasons.append("Submitted custom idea")
                score += 1

            # Pack name bonus
            if results.best_names and response.pack_name_idea.lower().strip() == results.best_names[0]["name"]:
                reasons.append("Winning pack name!")
                score += 3

            if score >= 3:
                rewarded.append({
                    "player_id": response.player_id,
                    "player_name": response.player_name,
                    "score": score,
                    "reasons": reasons,
                    "reward": "FREE_DLC_LIFETIME",
                })

        # Sort by score, top contributors first
        rewarded.sort(key=lambda x: x["score"], reverse=True)
        return rewarded

    def generate_pack_spec(self, results: QuestionnaireResults) -> dict:
        """
        Generate a DLC pack specification from compiled results.
        This is what forge receives to build the actual pack.
        """
        def top_id(category_results, n=1):
            return [r["id"] for r in category_results[:n]]

        def top_label(category_results, n=1):
            return [r["label"] for r in category_results[:n]]

        spec = {
            "pack_type": "dlc",
            "generated_from": "community_questionnaire",
            "total_votes": results.total_responses,
            "contributors_rewarded": len(results.contributors_rewarded),

            "theme": top_id(results.top_themes, 1)[0] if results.top_themes else "volcanic",
            "theme_name": top_label(results.top_themes, 1)[0] if results.top_themes else "Volcanic Forge",
            "secondary_theme": top_id(results.top_themes, 2)[-1] if len(results.top_themes) > 1 else "",

            "mood": top_id(results.top_moods, 1)[0] if results.top_moods else "epic",
            "secondary_mood": top_id(results.top_moods, 2)[-1] if len(results.top_moods) > 1 else "",

            "enemy_types": top_id(results.top_enemies, 4),
            "boss_type": top_id(results.top_boss, 1)[0] if results.top_boss else "multi_phase",

            "mechanics": top_id(results.top_mechanics, 3),

            "loot_focus": top_id(results.top_loot, 3),

            "difficulty": top_id(results.top_difficulty, 1)[0] if results.top_difficulty else "scaling",

            "pack_name": results.best_names[0]["name"] if results.best_names else f"Community Pack — {top_label(results.top_themes, 1)[0]}",

            "custom_ideas_to_review": [
                i["idea"] for i in results.best_custom_ideas[:10]
            ],
        }

        # Save spec
        spec_path = self.DATA_DIR / f"pack_spec_{datetime.now().strftime('%Y%m')}.json"
        spec_path.write_text(json.dumps(spec, indent=2))

        return spec

    def get_results_announcement(self, results: QuestionnaireResults) -> str:
        """Discord announcement of questionnaire results."""
        lines = [
            "# 📊 DLC Questionnaire Results!",
            "",
            f"**{results.total_responses} players** filled out the questionnaire. Here's what you chose:",
            "",
        ]

        if results.top_themes:
            winner = results.top_themes[0]
            lines.append(f"🏔️ **Theme:** {winner['label']} ({winner['pct']}% of votes)")
        if results.top_moods:
            winner = results.top_moods[0]
            lines.append(f"🌙 **Mood:** {winner['label']} ({winner['pct']}%)")
        if results.top_enemies:
            top3 = results.top_enemies[:3]
            names = ", ".join(e["label"] for e in top3)
            lines.append(f"👹 **Enemies:** {names}")
        if results.top_boss:
            winner = results.top_boss[0]
            lines.append(f"🐉 **Boss Type:** {winner['label']} ({winner['pct']}%)")
        if results.top_mechanics:
            top3 = results.top_mechanics[:3]
            names = ", ".join(m["label"] for m in top3)
            lines.append(f"⚙️ **Mechanics:** {names}")
        if results.top_loot:
            top3 = results.top_loot[:3]
            names = ", ".join(l["label"] for l in top3)
            lines.append(f"💎 **Loot:** {names}")
        if results.top_difficulty:
            winner = results.top_difficulty[0]
            lines.append(f"💪 **Difficulty:** {winner['label']} ({winner['pct']}%)")

        if results.best_names:
            lines.append(f"\n📛 **Pack Name:** *{results.best_names[0]['name']}*")

        lines.append("")
        lines.append(f"🎁 **{len(results.contributors_rewarded)} players** are getting this DLC **FREE** for their contributions!")
        lines.append("")
        lines.append("Our AI agents are already building it. Updates coming soon in #dev-log.")
        lines.append("")
        lines.append("*Thank you for designing the next chapter of Voxel Extraction.*")
        lines.append("*— echo, on behalf of halo-ai studios*")

        return "\n".join(lines)

    def get_reward_dm(self, contributor: dict) -> str:
        """DM to send to rewarded players."""
        return (
            f"Hey {contributor['player_name']}! 🎉\n\n"
            f"Your ideas made it into the next DLC pack! "
            f"As a thank you, you're getting **the DLC for FREE — forever.**\n\n"
            f"**Why you were chosen:**\n"
            + "\n".join(f"• {r}" for r in contributor["reasons"]) +
            f"\n\nYour key will be sent when the pack launches. "
            f"Thank you for making the game better.\n\n"
            f"*— echo, halo-ai studios*"
        )

    def get_discord_form(self) -> str:
        """The questionnaire as a Discord message with instructions."""
        lines = [
            "# 🗺️ Design the Next DLC Pack!",
            "",
            "Fill out the questionnaire below. **If your ideas make it in, you get the DLC FREE forever.**",
            "",
            "Use: `!questionnaire`",
            "",
            "You'll pick from curated options in each category:",
            "",
            "🏔️ **Theme** (pick up to 3):",
        ]
        for opt in THEME_OPTIONS:
            lines.append(f"  `{opt['id']}` — **{opt['label']}**: {opt['desc']}")

        lines.append("\n🌙 **Mood** (pick up to 2):")
        for opt in MOOD_OPTIONS:
            lines.append(f"  `{opt['id']}` — **{opt['label']}**: {opt['desc']}")

        lines.append("\n👹 **Enemies** (pick up to 4):")
        for opt in ENEMY_OPTIONS:
            lines.append(f"  `{opt['id']}` — **{opt['label']}**: {opt['desc']}")

        lines.append("\n🐉 **Boss Type** (pick up to 2):")
        for opt in BOSS_OPTIONS:
            lines.append(f"  `{opt['id']}` — **{opt['label']}**: {opt['desc']}")

        lines.append("\n⚙️ **Mechanics** (pick up to 3):")
        for opt in MECHANIC_OPTIONS:
            lines.append(f"  `{opt['id']}` — **{opt['label']}**: {opt['desc']}")

        lines.append("\n💎 **Loot** (pick up to 3):")
        for opt in LOOT_OPTIONS:
            lines.append(f"  `{opt['id']}` — **{opt['label']}**: {opt['desc']}")

        lines.append("\n💪 **Difficulty** (pick 1):")
        for opt in DIFFICULTY_OPTIONS:
            lines.append(f"  `{opt['id']}` — **{opt['label']}**: {opt['desc']}")

        lines.append("\n✏️ **Custom Idea** (optional, 280 chars max)")
        lines.append("📛 **Pack Name Suggestion** (optional)")
        lines.append("")
        lines.append("*One response per player. You can update your picks until the deadline.*")
        lines.append("*Results compiled. Winners announced. DLC built by AI agents. You get credit.*")

        return "\n".join(lines)
