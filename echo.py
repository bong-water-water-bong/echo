#!/usr/bin/env python3
"""
Echo — she listens so you don't have to.

Social media orchestrator for halo-ai. Echo monitors platforms,
aggregates mentions, and manages your social presence.
"""

import argparse
import importlib
import inspect
import json
import os
import sys
import datetime
import pathlib
import subprocess

# ---------------------------------------------------------------------------
# Optional deps — degrade gracefully
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
BASE_DIR = pathlib.Path(__file__).resolve().parent
DATA_DIR = pathlib.Path("/srv/ai/echo/data")
ENV_FILE = BASE_DIR / "configs" / "echo.env"
AGENTS_DIR = BASE_DIR / "agents"

VIOLET = "\033[38;2;206;147;216m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

BANNER = f"""{VIOLET}{BOLD}
  ███████╗ ██████╗██╗  ██╗ ██████╗
  ██╔════╝██╔════╝██║  ██║██╔═══██╗
  █████╗  ██║     ███████║██║   ██║
  ██╔══╝  ██║     ██╔══██║██║   ██║
  ███████╗╚██████╗██║  ██║╚██████╔╝
  ╚══════╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝
{RESET}{VIOLET}  she listens so you don't have to{RESET}
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log(msg: str, quiet: bool = False) -> None:
    if not quiet:
        print(f"{VIOLET}[echo]{RESET} {msg}")


def _err(msg: str) -> None:
    print(f"{VIOLET}[echo]{RESET} \033[31m{msg}\033[0m", file=sys.stderr)


def _notify(title: str, body: str) -> None:
    """Send a desktop notification (best-effort)."""
    try:
        subprocess.run(
            ["notify-send", "-a", "Echo", title, body],
            timeout=5,
            capture_output=True,
        )
    except FileNotFoundError:
        pass
    except Exception:
        pass


def _today_file() -> pathlib.Path:
    """Return path to today's feed file."""
    today = datetime.date.today().isoformat()
    return DATA_DIR / f"feed-{today}.json"


def _load_feed() -> list:
    path = _today_file()
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def _save_feed(entries: list) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_today_file(), "w") as f:
        json.dump(entries, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Agent auto-discovery
# ---------------------------------------------------------------------------

def discover_agents() -> dict:
    """
    Auto-discover PlatformAgent subclasses from the agents/ directory.

    Returns a dict mapping platform name -> agent instance.
    """
    from agents.base import PlatformAgent  # noqa: E402

    agents = {}
    agents_pkg = AGENTS_DIR

    for py_file in sorted(agents_pkg.glob("*.py")):
        module_name = py_file.stem
        if module_name.startswith("_") or module_name == "base":
            continue
        try:
            mod = importlib.import_module(f"agents.{module_name}")
        except Exception as exc:
            _err(f"Could not import agents.{module_name}: {exc}")
            continue

        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, PlatformAgent) and obj is not PlatformAgent:
                try:
                    instance = obj()
                    agents[instance.platform_name] = instance
                except Exception as exc:
                    _err(f"Could not instantiate {_name}: {exc}")
    return agents


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_listen(args, agents: dict) -> None:
    """Monitor all platforms for mentions."""
    _log("Listening across all platforms …", args.quiet)
    feed = _load_feed()

    for name, agent in agents.items():
        if not agent.available:
            _log(f"  {DIM}skipping {name} (no credentials){RESET}", args.quiet)
            continue
        _log(f"  checking {name} …", args.quiet)
        try:
            mentions = agent.listen()
            for m in mentions:
                m.setdefault("platform", name)
                m.setdefault("ts", datetime.datetime.utcnow().isoformat())
                feed.append(m)
                _notify(f"Echo — {name}", m.get("text", "")[:120])
        except Exception as exc:
            _err(f"  {name}: {exc}")

    _save_feed(feed)
    _log(f"Feed updated — {len(feed)} entries today.", args.quiet)

    if args.json:
        print(json.dumps(feed, indent=2, default=str))


def cmd_post(args, agents: dict) -> None:
    """Post to a specific platform."""
    platform = args.platform.lower()
    agent = agents.get(platform)
    if not agent:
        _err(f"Unknown platform: {platform}")
        sys.exit(1)
    if not agent.available:
        _err(f"{platform} credentials not configured.")
        sys.exit(1)

    _log(f"Posting to {platform} …", args.quiet)
    try:
        result = agent.post(args.message)
        _log(f"Posted: {result}", args.quiet)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
    except Exception as exc:
        _err(f"Failed to post: {exc}")
        sys.exit(1)


def cmd_announce(args, agents: dict) -> None:
    """Post to all available platforms."""
    _log("Announcing across all platforms …", args.quiet)
    results = {}
    for name, agent in agents.items():
        if not agent.available:
            _log(f"  {DIM}skipping {name}{RESET}", args.quiet)
            continue
        try:
            result = agent.post(args.message)
            results[name] = result
            _log(f"  {name}: ok", args.quiet)
        except Exception as exc:
            results[name] = {"error": str(exc)}
            _err(f"  {name}: {exc}")

    if args.json:
        print(json.dumps(results, indent=2, default=str))


def cmd_digest(args, agents: dict) -> None:
    """Show today's mentions/engagement summary."""
    feed = _load_feed()

    if args.json:
        print(json.dumps(feed, indent=2, default=str))
        return

    _log(f"Digest for {datetime.date.today().isoformat()}", args.quiet)
    if not feed:
        _log("  No mentions today.", args.quiet)
        return

    by_platform: dict[str, list] = {}
    for entry in feed:
        by_platform.setdefault(entry.get("platform", "unknown"), []).append(entry)

    for plat, entries in by_platform.items():
        _log(f"  {BOLD}{plat}{RESET} — {len(entries)} mention(s)", args.quiet)
        for e in entries[:5]:
            text = e.get("text", "")[:80]
            _log(f"    {DIM}{e.get('ts', '?')}{RESET}  {text}", args.quiet)
        if len(entries) > 5:
            _log(f"    … and {len(entries) - 5} more", args.quiet)


def cmd_status(args, agents: dict) -> None:
    """Account status and metrics."""
    status_data = {}
    for name, agent in agents.items():
        info = {
            "available": agent.available,
            "platform": name,
        }
        if agent.available:
            try:
                info["metrics"] = agent.metrics()
            except Exception as exc:
                info["metrics_error"] = str(exc)
        status_data[name] = info

    if args.json:
        print(json.dumps(status_data, indent=2, default=str))
        return

    _log("Platform status:", args.quiet)
    for name, info in status_data.items():
        mark = "\033[32m●\033[0m" if info["available"] else "\033[31m○\033[0m"
        _log(f"  {mark} {BOLD}{name}{RESET}", args.quiet)
        if info.get("metrics"):
            for k, v in info["metrics"].items():
                _log(f"      {k}: {v}", args.quiet)


def cmd_schedule(args, agents: dict) -> None:
    """Schedule a post for later."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    sched_file = DATA_DIR / "scheduled.json"
    existing = []
    if sched_file.exists():
        with open(sched_file) as f:
            existing = json.load(f)

    entry = {
        "time": args.time,
        "message": args.message,
        "created": datetime.datetime.utcnow().isoformat(),
        "posted": False,
    }
    existing.append(entry)
    with open(sched_file, "w") as f:
        json.dump(existing, f, indent=2, default=str)

    _log(f"Scheduled for {args.time}: {args.message[:60]}…", args.quiet)
    if args.json:
        print(json.dumps(entry, indent=2, default=str))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="echo",
        description="Echo — social media agent for halo-ai",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress banner and info messages")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("listen", help="Monitor all platforms for mentions")

    p_post = sub.add_parser("post", help="Post to a specific platform")
    p_post.add_argument("platform", help="Target platform name")
    p_post.add_argument("message", help="Message to post")

    p_ann = sub.add_parser("announce", help="Post to all platforms")
    p_ann.add_argument("message", help="Message to broadcast")

    sub.add_parser("digest", help="Today's mentions/engagement summary")
    sub.add_parser("status", help="Account status and metrics")

    p_sched = sub.add_parser("schedule", help="Schedule a post")
    p_sched.add_argument("time", help="When to post (ISO datetime or cron expr)")
    p_sched.add_argument("message", help="Message to post")

    return parser


def main() -> None:
    # Load env
    if load_dotenv and ENV_FILE.exists():
        load_dotenv(ENV_FILE)

    # Ensure agents package is importable
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        if not args.quiet:
            print(BANNER)
        parser.print_help()
        sys.exit(0)

    if not args.quiet:
        print(BANNER)

    agents = discover_agents()
    _log(f"Discovered {len(agents)} platform(s): {', '.join(agents) or '(none)'}", args.quiet)

    dispatch = {
        "listen": cmd_listen,
        "post": cmd_post,
        "announce": cmd_announce,
        "digest": cmd_digest,
        "status": cmd_status,
        "schedule": cmd_schedule,
    }

    handler = dispatch.get(args.command)
    if handler:
        handler(args, agents)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
