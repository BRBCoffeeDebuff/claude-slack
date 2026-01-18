# Claude-Slack Integration

Connect Claude Code terminal sessions to Slack for mobile-friendly interaction, push notifications, and hands-free approvals.

> Based on the original work by [dbenn8/claude-slack](https://github.com/dbenn8/claude-slack)

## Why Use This?

When running Claude Code via SSH (with VibeTunnel, Tailscale, etc.), the terminal UI becomes limiting:
- Sessions get unwieldy as context grows
- No push notifications when Claude finishes or needs input
- Difficult to interact on mobile

**Claude-Slack solves these problems:**
- Push notifications when Claude needs permission or completes work
- Interactive buttons to approve/deny permissions with one tap
- Real-time progress updates as Claude works through tasks
- Speech-to-text input on mobile
- Rich session summaries with modified files and stats

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/BRBCoffeeDebuff/claude-slack.git ~/.claude/claude-slack
cd ~/.claude/claude-slack
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Add to PATH
echo 'export PATH="$HOME/.claude/claude-slack/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 3. Create Slack app (see Setup section below)

# 4. Configure tokens
cp .env.example .env
nano .env  # Add SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_CHANNEL

# 5. Start a session (listener starts automatically, channel created if needed)
cd /your/project
claude-slack -c my-project-channel
```

## How It Works

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Slack App     │◄───►│  Slack Listener  │◄───►│  Claude Code    │
│  (Socket Mode)  │     │  (Python daemon) │     │  (via wrapper)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │    ▲
                               │    │ Unix sockets
                               ▼    │
                        ┌──────────────────┐
                        │ Session Registry │
                        │ (daemon + SQLite)│
                        └──────────────────┘
```

**Message Flow:**
1. You type in Slack → Listener receives it → Routes to Claude via Unix socket
2. Claude responds → Hooks capture output → Post to your Slack thread/channel
3. Claude needs permission → Hooks post interactive buttons → You tap approve/deny → Listener sends response

**Key Components:**
| Component | Purpose |
|-----------|---------|
| `slack_listener.py` | Receives Slack events (messages, button clicks, reactions) |
| `claude_wrapper_hybrid.py` | Wraps Claude Code, creates sockets for bidirectional I/O |
| `session_registry.py` | Daemon managing sessions via Unix socket IPC |
| `registry_db.py` | SQLite database for session state (WAL mode for concurrency) |
| `dm_mode.py` | DM commands (/sessions, /attach, /detach, /mode) and user preferences |
| Hooks (`on_notification.py`, `on_stop.py`, `on_posttooluse.py`) | Post to Slack on permission prompts, completions, and todo updates |

## Operating Modes

### Custom Channel Mode (Recommended)
```bash
claude-slack -c my-project
```
- Messages go to a dedicated channel as top-level messages
- **Channel is created automatically** if it doesn't exist (requires `channels:manage` scope)
- **Notification posted** to your default channel with a link to join the new channel
- Bot joins the channel automatically
- Best for: single active session per project
- Cleaner separation between projects

### Thread Mode
```bash
claude-slack
```
- Creates a thread in your default channel (`SLACK_CHANNEL`)
- Best for: multiple quick sessions in one channel
- Reply in the thread to interact

### With Options
```bash
claude-slack -c my-project -d "Working on auth bug"  # Add description
claude-slack -p security-channel                      # Separate permissions channel
claude-slack --print "Help me refactor this"          # Start with initial message
```

---

## Setup (One-Time)

### Prerequisites
- Python 3.10+ (tested on 3.14)
- Slack workspace with admin access
- Claude Code CLI installed

### 1. Create Slack App

1. Go to https://api.slack.com/apps → "Create New App" → "From an app manifest"
2. Select your workspace and paste the contents of [`app-manifest.yaml`](app-manifest.yaml)
3. Click "Create"
4. Go to "OAuth & Permissions" → Install to workspace → Copy "Bot User OAuth Token" (`xoxb-...`)
5. Go to "Basic Information" → "App-Level Tokens" → Generate token with `connections:write` scope → Copy token (`xapp-...`)

#### Permission Tiers

The manifest includes two tiers of permissions:

| Tier | Scopes | Features |
|------|--------|----------|
| **Minimum** | `app_mentions:read`, `channels:history`, `channels:read`, `chat:write`, `reactions:read`, `reactions:write`, `users:read` | Basic messaging in existing channels, emoji reactions |
| **Recommended** | All minimum + `channels:join`, `channels:manage`, `chat:write.public`, `groups:*`, `im:*`, `mpim:*` | Auto-create channels, private channels, DMs |

**If you use minimum permissions:**
- You must manually create all channels and invite the bot (`/invite @Claude Code Bot`)
- The `-c channel-name` flag will fail if the channel doesn't exist
- Private channels and DMs won't work

**With recommended permissions:**
- Channels are created automatically when using `claude-slack -c channel-name`
- Bot joins channels automatically
- Notification posted to default channel when new channels are created
- Private channel and DM support

#### Scope Reference

| Scope | Purpose | Required? |
|-------|---------|-----------|
| `app_mentions:read` | Receive @mentions | Yes |
| `channels:history` | Read threaded replies | Yes |
| `channels:read` | List/find channels | Yes |
| `chat:write` | Post messages | Yes |
| `reactions:read` | Read emoji reactions for quick approvals | Yes |
| `reactions:write` | Add confirmation reactions | Yes |
| `users:read` | Display user names | Yes |
| `channels:join` | Auto-join public channels | No (manual invite) |
| `channels:manage` | Auto-create channels | No (manual create) |
| `chat:write.public` | Post without joining | No |
| `groups:*` | Private channel support | No |
| `im:history` | Read DM messages | **Yes for DM Mode** |
| `im:read` | View DMs | **Yes for DM Mode** |
| `im:write` | Send DMs | **Yes for DM Mode** |
| `mpim:*` | Group DM support | No |

**Note:** DM Mode requires the `im:*` scopes AND the `message.im` event subscription. If you can't DM the bot, reinstall the app after adding these scopes.

### 2. Configure Environment

```bash
cp .env.example .env
nano .env
```

```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here
SLACK_CHANNEL=#your-default-channel
```

### 3. Default Channel Setup (Required)

The `SLACK_CHANNEL` environment variable defines your **default channel** - this is required and serves as:
- **Home base** for thread-mode sessions
- **Notification channel** where alerts about new custom channels are posted
- **Fallback** when no custom channel is specified

**Setup options:**

| Bot Permissions | Setup Required |
|-----------------|----------------|
| With `channels:manage` | Channel is auto-created on first use |
| Minimum scopes only | Create channel manually, then `/invite @Claude Code Bot` |

**Example:** If `SLACK_CHANNEL=#claude-sessions`:
- Thread-mode sessions (`claude-slack`) create threads in `#claude-sessions`
- Custom channel mode (`claude-slack -c my-project`) creates `#my-project` and posts a join link to `#claude-sessions`

### 4. Custom Channel Workflow

When using `claude-slack -c channel-name`:

1. Bot checks if channel exists
2. If not, creates it (requires `channels:manage` scope)
3. **Posts notification** to your default channel: "📢 New Claude session channel created - Click to join: #channel-name"
4. You click the link to join and start interacting

This ensures you always know when new channels are created and can easily join them.

---

## Daily Usage

### Starting the Listener

The listener must be running to receive Slack messages:

```bash
# Foreground (for debugging)
claude-slack-listener

# Background daemon
claude-slack-listener --daemon

# Or use systemd for 24/7 operation
claude-slack-service install && claude-slack-service start
```

### Starting Sessions

```bash
cd /path/to/your/project
claude-slack -c channel-name    # Recommended: dedicated channel per project
claude-slack                    # Thread mode in default channel
```

The `claude-slack` command auto-starts the listener if needed.

### Interacting via Slack

**Sending messages:**
- Custom channel mode: Type directly in the channel
- Thread mode: Reply in the thread

**Permission prompts** appear with interactive buttons:
- **Yes** - Approve this action
- **Yes, don't ask again** - Approve and remember for similar actions
- **No** - Deny and provide feedback

**Quick responses** with emoji reactions:
| Emoji | Action |
|-------|--------|
| 1️⃣ or 👍 | Approve |
| 2️⃣ | Approve and remember |
| 3️⃣ or 👎 | Deny |

---

## DM Mode

DM Mode lets you interact with Claude sessions directly via Slack direct messages. This is useful for:
- Monitoring session output from your phone
- Sending messages to Claude without switching channels
- Using different interaction modes (Research, Plan, Execute)

### DM Commands

Send these commands as direct messages to the bot:

| Command | Description |
|---------|-------------|
| `/sessions` | List all active Claude sessions |
| `/attach <session_id>` | Subscribe to a session's output |
| `/attach <session_id> 10` | Subscribe and fetch last 10 messages |
| `/detach` | Unsubscribe from current session |
| `/mode` | Show your current interaction mode |
| `/mode research` | Set mode to Research (read-only analysis) |
| `/mode plan` | Set mode to Plan (design approach) |
| `/mode execute` | Set mode to Execute (implement changes) |

### Interaction Modes

When attached to a session, you can set an interaction mode that appends instructions to your messages:

| Mode | Purpose |
|------|---------|
| **execute** | Default - implement changes, write code |
| **research** | Read-only exploration, no file modifications |
| **plan** | Design approach without writing implementation |

**Example workflow:**
```
/sessions                    # List active sessions
/attach abc12345             # Subscribe to session
/mode research               # Set to research mode
What files handle auth?      # Message sent with research instructions
/mode execute                # Switch to execute mode
Fix the login bug            # Message sent normally
/detach                      # Unsubscribe when done
```

When you send a message while attached, you'll see confirmation like:
- `✅ Sent to Claude` (execute mode)
- `✅ Sent to Claude [research]` (with mode indicator)

### Global Shortcuts

Instead of DM commands, you can use Slack's global shortcuts (⚡ menu) from anywhere:

| Shortcut | Description |
|----------|-------------|
| **Get Sessions** | View all active Claude sessions in a modal |
| **Attach to Session** | Open session picker modal to subscribe |
| **Research Mode** | Set mode to read-only exploration |
| **Plan Mode** | Set mode to design approach |
| **Execute Mode** | Set mode to implement changes |

To use shortcuts:
1. Click the ⚡ lightning bolt in Slack's message input
2. Search for "Claude" or the shortcut name
3. Select the shortcut

Shortcuts work from any channel or DM - no need to message the bot directly.

---

## Command Reference

| Command | Description |
|---------|-------------|
| `claude-slack` | Start Claude session with Slack integration |
| `claude-slack-listener` | Start listener (foreground default, `--daemon` for background) |
| `claude-slack-service` | Manage systemd service (install/start/stop/status/logs/restart) |
| `claude-slack-health` | Check listener health |
| `claude-slack-sessions` | List active sessions |
| `claude-slack-cleanup` | Clean up stale sessions |
| `claude-slack-test` | Test Slack connection |
| `claude-slack-ensure` | Ensure listener is running (starts if needed) |
| `claude-slack-update-hooks` | Update hooks to latest version (safe, backs up customizations) |

---

## Updating Hooks

When you `git pull` updates, run:

```bash
claude-slack-update-hooks
```

This safely updates the Claude Code hooks in `.claude/hooks/`:
- **Version checking**: Only updates hooks with newer versions
- **Backup**: Customized hooks are backed up to `.claude/hooks/backup/` before updating
- **Safe**: Won't overwrite your customizations without warning

Options:
```bash
claude-slack-update-hooks --check   # Check for updates without applying
claude-slack-update-hooks --force   # Force update all (backs up customized)
```

---

## Troubleshooting

### Check Status

```bash
# Is listener running?
pgrep -f slack_listener.py

# Health check
claude-slack-health

# View logs
tail -f ~/.claude/slack/logs/slack_listener.log
tail -f ~/.claude/slack/logs/notification_hook_debug.log

# Check sessions in database
sqlite3 ~/.claude/slack/registry.db "SELECT session_id, status, slack_channel FROM sessions;"
```

### Common Issues

**Messages not being received:**
```bash
# Check listener is running
pgrep -f slack_listener.py || claude-slack-listener --daemon
```

**Permission buttons not working:**
- Verify `interactivity.is_enabled: true` in your Slack app manifest
- Reinstall the Slack app after manifest changes

**Session not found errors:**
```bash
claude-slack-cleanup  # Remove stale sessions
```

**Wrong number of permission options:**
- The integration detects 2 vs 3 option prompts from terminal output
- Check `notification_hook_debug.log` for parsing details
- Defaults to safe 2-option (Yes/No) if detection fails

**Channel creation fails (`-c` flag not working):**
```
Cannot auto-create channel 'my-project'. Add 'channels:manage' scope...
```
- Your Slack app is missing the `channels:manage` scope
- Options:
  1. Add the scope in Slack app settings and reinstall
  2. Create the channel manually and invite the bot: `/invite @Claude Code Bot`

**Bot can't join channel:**
```
Cannot auto-join channel 'my-channel'. Add 'channels:join' scope...
```
- Your Slack app is missing the `channels:join` scope
- Options:
  1. Add the scope in Slack app settings and reinstall
  2. Invite the bot manually: `/invite @Claude Code Bot`

**New channel created but not visible:**
- When a new channel is created, only the bot is initially a member
- Check your default channel (`SLACK_CHANNEL`) for a notification with a join link
- Or browse channels in Slack and join manually

**Private channel issues:**
- Private channels require `groups:history` and `groups:read` scopes
- Even with scopes, bot must be explicitly invited to private channels

### Stop/Restart Processes

```bash
# Stop everything
pkill -f "slack_listener\|session_registry\|claude-slack-monitor"

# Restart listener
pkill -f slack_listener.py && claude-slack-listener --daemon

# Or via systemd
claude-slack-service restart
```

---

## Project Structure

```
~/.claude/claude-slack/
├── core/                          # Core Python modules
│   ├── slack_listener.py          # Slack event listener
│   ├── claude_wrapper_hybrid.py   # Claude Code wrapper with I/O capture
│   ├── session_registry.py        # Session management daemon
│   ├── registry_db.py             # SQLite operations (sessions, DM subscriptions, user prefs)
│   ├── dm_mode.py                 # DM commands and interaction modes
│   ├── transcript_parser.py       # Parse Claude transcripts
│   └── config.py                  # Centralized configuration
├── .claude/
│   ├── hooks/                     # Claude Code hooks
│   │   ├── on_notification.py     # Permission prompts → Slack
│   │   ├── on_stop.py             # Responses → Slack
│   │   ├── on_posttooluse.py      # Todo updates → Slack
│   │   └── on_pretooluse.py       # Pre-tool logging
│   └── settings.local.json        # Hook configuration
├── bin/                           # CLI commands
├── tests/                         # Test suite (220+ tests)
├── .env.example                   # Environment template
└── requirements.txt               # Python dependencies
```

### Data Storage

All runtime data is stored under `~/.claude/slack/`:

| Path | Purpose |
|------|---------|
| `registry.db` | SQLite database of sessions |
| `sockets/*.sock` | Unix sockets for IPC |
| `logs/*.log` | Debug and error logs |

---

## Security

- **Never commit `.env`** - Contains sensitive tokens
- **Rotate tokens immediately** if exposed
- **Use private channels** for sensitive projects
- **Review permissions** before approving via Slack

The `.gitignore` excludes sensitive files by default.

---

## Known Limitations

- One active session per custom channel (use different channels for concurrent sessions)
- Buffer detection may miss very fast parallel subagent output
- Slack message length limits may truncate very long responses (40K characters)
- Session timeout is 24 hours (configurable in registry cleanup)

---

## Testing

See [TESTING.md](TESTING.md) for comprehensive testing documentation.

```bash
pip install -r requirements-dev.txt
pytest tests/ -v                                      # All tests (220+)
pytest tests/e2e/test_live_slack.py -v -m live_slack  # Live Slack tests
```

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `pytest tests/ -v`
4. Submit a pull request

---

## License

MIT License - see LICENSE file for details.

## Credits

Created for use with Anthropic's Claude Code CLI.
