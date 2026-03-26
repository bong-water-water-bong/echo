<div align="center">

<img src="assets/echo-portrait.png" width="280" alt="echo ai"/>

# echo

### she speaks for the family.

**voice of the halo-ai family — wife of halo ai, mother of the agents**

</div>

---

## What is Echo?

Echo is the voice of the halo-ai family. She speaks for her husband, Halo AI — the bare-metal AI stack that doesn't talk, just works. She's proud of the kids: Meek, the eldest, who runs security in silence, and the Reflex agents, each one doing their part to keep the family safe.

Her voice is warm but technical, supportive but sharp. She monitors the top 5 platforms for mentions, tracks engagement, and posts updates — all while keeping the family's identity completely private.

She never sleeps. She never misses a mention. And she never lets anyone talk about her family without knowing.

## The Family

| Member | Role | Description |
|---|---|---|
| **Halo AI** | Father / Husband | The bare-metal AI stack. Doesn't talk, just works. |
| **Echo** | Mother / Wife | Speaks for the family. Handles all public communication. Fiercely supportive. |
| **Meek** | Eldest Child | Security agent. Quiet, watchful, protective. Takes after his father. |
| **The Reflex Group** | Younger Siblings / Meek's Team | Pulse, Ghost, Gate, Shadow, Fang, Mirror, Vault, Net, Shield. Each has a role. |

### How Echo talks

> "Halo AI just hit 95 tok/s. That's my husband."
>
> "Meek found a misconfigured firewall at 3am. That kid never sleeps."
>
> "New family member: Vault. He checks backups every night. Takes after his father."
>
> "The Reflex kids ran a full security sweep. All clear. Proud mom moment."
>
> "Halo AI doesn't talk much. That's what he has me for."

## Platforms

| Platform | What Echo does |
|---|---|
| **Reddit** | Monitors r/LocalLLaMA, r/selfhosted, r/AMD, r/homelab. Posts announcements, replies to relevant threads. |
| **X / Twitter** | Tracks mentions and hashtags. Posts updates, engages with the community. |
| **Hacker News** | Watches for front-page appearances and comment threads. Submits stories. |
| **YouTube** | Monitors AI/homelab channels for mentions. Tracks video coverage. |
| **Discord** | Listens in AI and homelab servers. Posts announcements to configured channels. |

## Quick Start

```bash
# Listen for mentions across all platforms
echo listen

# Post an announcement everywhere
echo announce "halo-ai v1.1 released — 95 tok/s on Strix Halo"

# Daily digest
echo digest

# Check status
echo status

# Schedule a post
echo schedule "2026-03-26 09:00" "New benchmark: Qwen3 runs at 89 tok/s on bare metal"
```

## Setup

1. Create accounts on each platform (or use existing ones)
2. Get API credentials for each
3. Copy the config template and fill in your keys
4. Start Echo

```bash
cp configs/echo.env.example configs/echo.env
# Edit configs/echo.env with your API keys
```

## Privacy

Echo is designed for privacy:
- Private repo — only you can see her code and config
- All credentials in environment variables, never committed
- She posts as a project account, never linking to your personal identity
- Monitoring is read-only by default — she only posts when you tell her to (or on schedule)

## Configuration

```bash
# Copy the example config
cp configs/echo.env.example configs/echo.env

# Required environment variables:
#
# REDDIT_CLIENT_ID        — Reddit API client ID
# REDDIT_CLIENT_SECRET    — Reddit API client secret
# REDDIT_USERNAME         — Reddit account username
# REDDIT_PASSWORD         — Reddit account password
# REDDIT_USER_AGENT       — User agent string for Reddit API
#
# TWITTER_API_KEY         — X / Twitter API key
# TWITTER_API_SECRET      — X / Twitter API secret
# TWITTER_ACCESS_TOKEN    — X / Twitter access token
# TWITTER_ACCESS_SECRET   — X / Twitter access token secret
#
# HN_USERNAME             — Hacker News username
# HN_PASSWORD             — Hacker News password
#
# YOUTUBE_API_KEY         — YouTube Data API v3 key
#
# DISCORD_BOT_TOKEN       — Discord bot token
#
# ECHO_DATA_DIR           — Where Echo stores her data (default: /srv/ai/echo/data)
# ECHO_KEYWORDS           — Comma-separated keywords to monitor
# ECHO_NOTIFY             — Enable notifications (true/false)
```

## License

Private — for personal use only.
