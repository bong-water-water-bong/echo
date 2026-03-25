<div align="center">

# echo

### She watches. She listens. She speaks — so you don't have to.

**Autonomous social media agent for halo-ai**

</div>

---

## What is Echo?

Echo is your private social media manager for the halo-ai project. She monitors the top 5 platforms for mentions, tracks engagement, and posts updates — all while keeping your identity completely private.

She never sleeps. She never misses a mention. And she never reveals who's behind the curtain.

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
