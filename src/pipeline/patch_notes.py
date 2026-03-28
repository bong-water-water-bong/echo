#!/usr/bin/env python3
"""
echo — Patch note generator.

Takes git commit logs and diffs, generates readable,
player-friendly patch notes. Uses local LLM when available,
falls back to commit message parsing.
"""

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from typing import Optional

import httpx

log = logging.getLogger("echo.patchnotes")


@dataclass
class PatchNote:
    version: str
    date: str
    sections: dict[str, list[str]]  # category -> changes
    summary: str = ""
    breaking_changes: list[str] = None

    def to_markdown(self) -> str:
        md = f"# {self.version} — {self.date}\n\n"
        if self.summary:
            md += f"{self.summary}\n\n"
        if self.breaking_changes:
            md += "## ⚠️ Breaking Changes\n"
            for bc in self.breaking_changes:
                md += f"- {bc}\n"
            md += "\n"
        for category, changes in self.sections.items():
            md += f"## {category}\n"
            for change in changes:
                md += f"- {change}\n"
            md += "\n"
        md += "*— echo, on behalf of halo-ai studios*\n"
        return md

    def to_discord(self) -> str:
        """Shorter format for Discord."""
        lines = []
        if self.summary:
            lines.append(self.summary)
            lines.append("")
        for category, changes in self.sections.items():
            lines.append(f"**{category}**")
            for change in changes[:5]:
                lines.append(f"• {change}")
            if len(changes) > 5:
                lines.append(f"  *...and {len(changes) - 5} more*")
            lines.append("")
        return "\n".join(lines)


class PatchNoteGenerator:
    """Generates patch notes from git history."""

    # Commit prefix -> friendly category
    CATEGORY_MAP = {
        "feat": "✨ New Features",
        "fix": "🐛 Bug Fixes",
        "perf": "⚡ Performance",
        "refactor": "🔨 Improvements",
        "docs": "📚 Documentation",
        "style": "🎨 Visual",
        "test": "🧪 Testing",
        "chore": "🔧 Maintenance",
        "build": "📦 Build",
        "ci": "🔄 CI/CD",
    }

    def __init__(self, repo_path: str, llm_url: str = "http://127.0.0.1:8080"):
        self.repo_path = repo_path
        self.llm_url = llm_url

    def generate(
        self, from_tag: str = "", to_tag: str = "HEAD", version: str = "",
    ) -> PatchNote:
        """Generate patch notes from git log between tags."""
        commits = self._get_commits(from_tag, to_tag)
        if not commits:
            return PatchNote(version=version, date="", sections={})

        # Parse commits into categories
        sections: dict[str, list[str]] = {}
        breaking = []

        for commit in commits:
            msg = commit["message"]
            category, clean_msg = self._categorize(msg)

            if category not in sections:
                sections[category] = []
            sections[category].append(clean_msg)

            # Detect breaking changes
            if "BREAKING" in msg.upper() or "breaking:" in msg.lower():
                breaking.append(clean_msg)

        # Get date
        date = commits[0]["date"] if commits else ""

        patch = PatchNote(
            version=version or self._detect_version(),
            date=date,
            sections=sections,
            breaking_changes=breaking if breaking else None,
        )

        # Try LLM summary
        summary = self._generate_summary(patch)
        if summary:
            patch.summary = summary

        return patch

    def _get_commits(self, from_ref: str, to_ref: str) -> list[dict]:
        """Get commits between two refs."""
        range_spec = f"{from_ref}..{to_ref}" if from_ref else to_ref
        try:
            result = subprocess.run(
                ["git", "-C", self.repo_path, "log", range_spec,
                 "--pretty=format:%H|||%s|||%ai|||%an", "--no-merges"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                return []

            commits = []
            for line in result.stdout.strip().split("\n"):
                if "|||" not in line:
                    continue
                parts = line.split("|||")
                if len(parts) >= 4:
                    commits.append({
                        "sha": parts[0],
                        "message": parts[1],
                        "date": parts[2].split()[0],
                        "author": parts[3],
                    })
            return commits
        except Exception:
            return []

    def _categorize(self, message: str) -> tuple[str, str]:
        """Categorize a commit message."""
        # Try conventional commit format: type(scope): message
        match = re.match(r"^(\w+)(?:\(.+?\))?:\s*(.+)", message)
        if match:
            prefix = match.group(1).lower()
            msg = match.group(2)
            category = self.CATEGORY_MAP.get(prefix, "🔧 Maintenance")
            return category, msg

        # Keyword detection
        lower = message.lower()
        if any(w in lower for w in ["add", "new", "feature", "implement"]):
            return "✨ New Features", message
        elif any(w in lower for w in ["fix", "bug", "crash", "issue"]):
            return "🐛 Bug Fixes", message
        elif any(w in lower for w in ["perf", "optim", "fast", "speed"]):
            return "⚡ Performance", message
        elif any(w in lower for w in ["shader", "visual", "ui", "texture"]):
            return "🎨 Visual", message
        elif any(w in lower for w in ["audio", "sound", "music"]):
            return "🔊 Audio", message

        return "🔧 Maintenance", message

    def _detect_version(self) -> str:
        """Try to detect version from git tags."""
        try:
            result = subprocess.run(
                ["git", "-C", self.repo_path, "describe", "--tags", "--abbrev=0"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip() if result.returncode == 0 else "dev"
        except Exception:
            return "dev"

    def _generate_summary(self, patch: PatchNote) -> str:
        """Use LLM to write a player-friendly summary."""
        total_changes = sum(len(v) for v in patch.sections.values())
        categories = list(patch.sections.keys())

        # Quick summary without LLM
        parts = []
        if "✨ New Features" in patch.sections:
            count = len(patch.sections["✨ New Features"])
            parts.append(f"{count} new feature{'s' if count > 1 else ''}")
        if "🐛 Bug Fixes" in patch.sections:
            count = len(patch.sections["🐛 Bug Fixes"])
            parts.append(f"{count} bug fix{'es' if count > 1 else ''}")
        if "⚡ Performance" in patch.sections:
            parts.append("performance improvements")

        if parts:
            return f"This update brings {', '.join(parts)}."
        return f"This update includes {total_changes} changes."
