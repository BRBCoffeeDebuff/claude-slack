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
- Interactive buttons and emoji reactions to approve/deny permissions
- Answer Claude's questions directly in Slack (AskUserQuestion support)
- Real-time progress updates as Claude works through tasks
- Speech-to-text input on mobile
- Rich session summaries with modified files and stats
- DM mode for personal notifications and interaction

## Features at a Glance

| Feature | Description |
|---------|-------------|
| **Permission Handling** | Interactive buttons or emoji reactions (✅ ❌ 🔄) to approve/deny |
| **AskUserQuestion** | Answer Claude's questions via emoji (1️⃣ 2️⃣ 3️⃣ 4️⃣) or thread replies |
| **Real-time Updates** | Todo progress, session summaries, modified file lists |
| **DM Mode** | Subscribe to sessions, send messages from anywhere |
| **Global Shortcuts** | Access sessions and modes from Slack's ⚡ menu |
| **Auto Channels** | Automatic channel creation per project |
| **Session Tracking** | Handles `/compact` and `/resume` seamlessly |

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
4. Claude asks a question → Hooks post options with emoji → You react to answer → Response sent back

**Key Components:**
| Component | Purpose |
|-----------|---------|
| `slack_listener.py` | Receives Slack events (messages, button clicks, reactions) |
| `claude_wrapper_hybrid.py` | Wraps Claude Code, creates sockets for bidirectional I/O |
| `session_registry.py` | Daemon managing sessions via Unix socket IPC |
| `registry_db.py` | SQLite database for session state (WAL mode for concurrency) |
| `dm_mode.py` | DM commands and user preferences |
| `line_logger.py` | Line-based terminal capture for reliable option parsing |
| `permission_parser.py` | Extracts permission options from terminal output |
| `session_discovery.py` | Finds active sessions after `/compact` or `/resume` |

**Hooks:**
| Hook | Purpose |
|------|---------|
| `on_permission_request.py` | Permission prompts → Slack with buttons/emoji |
| `on_pretooluse.py` | AskUserQuestion → Slack with emoji options |
| `on_notification.py` | General notifications → Slack |
| `on_stop.py` | Session summaries → Slack |
| `on_posttooluse.py` | Todo updates → Slack |

---

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

## Interactive Features

### Permission Handling

When Claude needs permission (e.g., to run a command or edit a file), you'll see a message in Slack with the exact options from the terminal:

**Button Mode:**
- Click the button corresponding to your choice
- Options match exactly what you'd see in the terminal

**Emoji Mode (Quick Responses):**
| Emoji | Action |
|-------|--------|
| ✅ or 👍 or 1️⃣ | Approve (Option 1) |
| 🔄 or 2️⃣ | Approve and remember (Option 2) |
| ❌ or 👎 or 3️⃣ | Deny (Option 3) |

The integration automatically detects whether the prompt has 2 or 3 options and adjusts accordingly.

### AskUserQuestion Support

When Claude asks you a question with multiple-choice options (via the `AskUserQuestion` tool), you can answer directly in Slack:

**Emoji Selection:**
- React with 1️⃣ 2️⃣ 3️⃣ or 4️⃣ to select an option
- For multi-select questions, add multiple reactions

**"Other" Response:**
- Reply in the thread to provide custom text
- Your reply becomes the "Other" option response

**Example:**
```
Claude asks: "Which database should we use?"
  1️⃣ PostgreSQL - Relational, ACID compliant
  2️⃣ MongoDB - Document store, flexible schema
  3️⃣ Redis - In-memory, fast caching
  4️⃣ SQLite - Embedded, zero config

React with 1️⃣ to select PostgreSQL, or reply "MySQL" in the thread for a custom choice.
```

### Real-Time Progress

**Todo Updates:**
- See Claude's task list update in real-time as it works
- Progress indicators show completed vs pending tasks

**Session Summaries:**
- When a session ends, get a rich summary including:
  - Files modified with change counts
  - Tasks completed
  - Duration and token usage

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
1. Click the ⚡ lightning bolt in Slack's message input (or press Cmd/Ctrl + /)
2. Search for "Claude" or the shortcut name
3. Select the shortcut

Shortcuts work from any channel or DM - no need to message the bot directly.

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

The manifest includes:
- All required OAuth scopes
- Event subscriptions (messages, reactions, app mentions)
- Global shortcuts (Get Sessions, Attach, Mode changes)
- Interactivity for buttons and modals

#### Permission Tiers

| Tier | Scopes | Features |
|------|--------|----------|
| **Minimum** | `app_mentions:read`, `channels:history`, `channels:read`, `chat:write`, `reactions:read`, `reactions:write`, `users:read` | Basic messaging, emoji reactions |
| **Recommended** | All minimum + `channels:join`, `channels:manage`, `chat:write.public`, `groups:*`, `im:*`, `mpim:*` | Auto-create channels, private channels, DMs |

**With minimum permissions:**
- You must manually create channels and invite the bot (`/invite @Claude Code Bot`)
- Private channels and DMs won't work

**With recommended permissions:**
- Channels created automatically with `claude-slack -c channel-name`
- Full DM mode support
- Private channel support

#### Scope Reference

| Scope | Purpose | Required? |
|-------|---------|-----------|
| `app_mentions:read` | Receive @mentions | Yes |
| `channels:history` | Read threaded replies | Yes |
| `channels:read` | List/find channels | Yes |
| `chat:write` | Post messages | Yes |
| `reactions:read` | Read emoji reactions for approvals | Yes |
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

The `SLACK_CHANNEL` environment variable defines your **default channel**:
- **Home base** for thread-mode sessions
- **Notification channel** for alerts about new custom channels
- **Fallback** when no custom channel is specified

### 4. Install Global Hooks (Optional)

To enable Slack integration for ALL Claude Code sessions (not just those started with `claude-slack`):

```bash
~/.claude/claude-slack/bin/install-hooks
```

This installs hooks globally to `~/.claude/hooks/` so any `claude` session gets Slack notifications.

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

### Session Commands in Terminal

These commands work in your Claude terminal session and are detected by the Slack integration:

| Command | Effect |
|---------|--------|
| `/compact` | Compacts conversation - Slack thread routing is preserved |
| `/resume` | Resumes a session - Slack thread routing is preserved |

The integration automatically detects these commands and updates session tracking to maintain Slack connectivity.

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

## Updating

### Updating Code

```bash
cd ~/.claude/claude-slack
git pull
pip install -r requirements.txt  # In case of new dependencies
```

### Updating Hooks

When you `git pull` updates, run:

```bash
claude-slack-update-hooks
```

This safely updates the Claude Code hooks:
- **Version checking**: Only updates hooks with newer versions
- **Backup**: Customized hooks are backed up before updating
- **Safe**: Won't overwrite your customizations without warning

Options:
```bash
claude-slack-update-hooks --check   # Check for updates without applying
claude-slack-update-hooks --force   # Force update all (backs up customized)
```

### Database Migrations

**Migrations are automatic.** When the listener or registry starts, new database columns and tables are created automatically. No manual migration steps required.

The database uses SQLite with WAL mode for concurrent access.

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

# Clean up dead sessions
claude-slack-cleanup
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

**AskUserQuestion not showing options:**
- Ensure you're running the latest hooks: `claude-slack-update-hooks`
- Check `notification_hook_debug.log` for parsing details

**Session not found errors:**
```bash
claude-slack-cleanup  # Remove stale sessions
```

**Wrong number of permission options:**
- The integration parses terminal output to detect options
- Uses line-based logging (500 lines) for reliable capture
- Defaults to safe 2-option (Yes/No) if detection fails
- Check `notification_hook_debug.log` for `[METRIC] parse_source=` entries

**Channel creation fails (`-c` flag not working):**
- Your Slack app needs the `channels:manage` scope
- Options:
  1. Add the scope in Slack app settings and reinstall
  2. Create the channel manually and invite the bot: `/invite @Claude Code Bot`

**DM commands not working:**
- Ensure `im:history`, `im:read`, `im:write` scopes are added
- Ensure `message.im` event is subscribed
- Reinstall the app after adding scopes

**Session lost after `/compact` or `/resume`:**
- This should be handled automatically
- Check that `session_discovery.py` exists in `core/`
- Restart the listener: `claude-slack-service restart`

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
│   ├── registry_db.py             # SQLite operations
│   ├── dm_mode.py                 # DM commands and interaction modes
│   ├── line_logger.py             # Line-based terminal capture
│   ├── permission_parser.py       # Permission option extraction
│   ├── session_discovery.py       # Active session discovery
│   ├── transcript_parser.py       # Parse Claude transcripts
│   └── config.py                  # Centralized configuration
├── .claude/
│   ├── hooks/                     # Claude Code hooks
│   │   ├── on_permission_request.py  # Permission prompts → Slack
│   │   ├── on_pretooluse.py          # AskUserQuestion → Slack
│   │   ├── on_notification.py        # General notifications
│   │   ├── on_stop.py                # Session summaries
│   │   └── on_posttooluse.py         # Todo updates
│   └── settings.local.json        # Hook configuration
├── bin/                           # CLI commands
├── tests/                         # Test suite (400+ tests)
│   ├── unit/                      # Unit tests
│   └── e2e/                       # End-to-end tests
├── docs/                          # Documentation
│   ├── plans/                     # Implementation plans
│   └── research/                  # Research notes
├── .env.example                   # Environment template
├── app-manifest.yaml              # Slack app manifest
└── requirements.txt               # Python dependencies
```

### Data Storage

All runtime data is stored under `~/.claude/slack/`:

| Path | Purpose |
|------|---------|
| `registry.db` | SQLite database (sessions, DM subscriptions, user prefs, AskUser state) |
| `sockets/*.sock` | Unix sockets for IPC |
| `logs/*.log` | Debug and error logs |
| `askuser_responses/` | Temporary response files for AskUserQuestion |
| `permission_responses/` | Temporary response files for permissions |

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
- Slack message length limits may truncate very long responses (40K characters)
- Session timeout is 24 hours (configurable in registry cleanup)
- Multi-select AskUserQuestion requires all reactions before timeout

---

## Testing

```bash
pip install -r requirements-dev.txt
pytest tests/ -v                                      # All tests (400+)
pytest tests/unit/ -v                                 # Unit tests only
pytest tests/e2e/ -v                                  # E2E tests
pytest tests/e2e/test_live_slack.py -v -m live_slack  # Live Slack tests
```

See [TESTING.md](TESTING.md) for comprehensive testing documentation.

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
