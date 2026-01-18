# Claude-Slack Integration

Slack integration for Claude Code sessions - enables bidirectional communication between Claude terminal sessions and Slack.

I've found VibeTunnel + Tailscale super helpful for using Claude Code on the go, but the UI can be limiting. As sessions get longer, VT can get bogged down and difficult to use. Slack provides:
- Push notifications when Claude finishes or needs input
- Better UI for consuming and generating responses on mobile
- Speech-to-text for hands-free interaction
- Interactive buttons for permission approvals

## Features

- **Bidirectional Communication**: Send messages from Slack to Claude and receive responses back
- **Interactive Permission Buttons**: Approve/deny permissions with one tap
- **Real-time Todo Updates**: See task progress as Claude works
- **Rich Session Summaries**: Get completion status, modified files, and stats when sessions end
- **Dedicated Project Channels**: Each project gets its own Slack channel with top-level messages (`-c` flag)
- **Multiple Concurrent Sessions**: Run multiple Claude sessions across different projects
- **Subagent Support**: Works with Claude's Task tool subagents

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Slack App     │◄───►│  Slack Listener  │◄───►│  Claude Code    │
│  (Socket Mode)  │     │  (Python daemon) │     │  (via wrapper)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │ Session Registry │
                        │    (SQLite)      │
                        └──────────────────┘
```

**Key Components:**
- **Slack Listener**: Receives messages/button clicks from Slack, routes to correct Claude session
- **Claude Wrapper**: Wraps Claude Code, captures output, manages Unix sockets for input
- **Session Registry**: SQLite database tracking active sessions, Slack threads, and routing info
- **Hooks**: Claude Code hooks that post notifications, responses, and todo updates to Slack

## Quick Start

> **Note:** Steps 1-6 are **one-time setup**. After that, just run `claude-slack` from any project directory.

### 1. Prerequisites

- Python 3.10+ (tested on 3.14)
- Slack workspace with admin access to create apps
- Claude Code CLI installed

### 2. Install Dependencies

```bash
# Clone this repository
git clone https://github.com/BRBCoffeeDebuff/claude-slack.git ~/.claude/claude-slack

# Navigate to the directory
cd ~/.claude/claude-slack

# Create virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install Python packages
pip install -r requirements.txt
```

**Required packages:**
- `slack-bolt` - Slack SDK for bot interactions
- `slack-sdk` - Slack API client
- `sqlalchemy` - Database ORM for session registry
- `python-dotenv` - Environment variable management

### 3. Create Slack App

1. Go to https://api.slack.com/apps and click "Create New App"
2. Choose "From an app manifest"
3. Select your workspace
4. Paste this manifest:

```yaml
display_information:
  name: Claude Code Bot
  description: Bidirectional communication with Claude Code sessions
  background_color: "#000000"
features:
  bot_user:
    display_name: Claude Code Bot
    always_online: true
oauth_config:
  scopes:
    bot:
      - channels:history
      - channels:read
      - chat:write
      - chat:write.public
      - reactions:read
      - reactions:write
      - users:read
      - groups:history
      - groups:read
      - im:history
      - im:read
      - im:write
      - mpim:history
      - mpim:read
settings:
  event_subscriptions:
    bot_events:
      - app_mention
      - message.channels
      - message.groups
      - message.im
      - message.mpim
      - reaction_added
  interactivity:
    is_enabled: true
  org_deploy_enabled: false
  socket_mode_enabled: true
  token_rotation_enabled: false
```

5. Click "Create"
6. Go to "OAuth & Permissions" and install the app to your workspace
7. Copy the "Bot User OAuth Token" (starts with `xoxb-`)
8. Go to "Basic Information" > "App-Level Tokens"
9. Click "Generate Token and Scopes"
10. Name: "Socket Mode Token", add scope: `connections:write`
11. Copy the token (starts with `xapp-`)

### 4. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit with your tokens
nano .env
```

Add your tokens to `.env`:
```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here
SLACK_CHANNEL=#your-default-channel
```

### 5. Add to PATH

```bash
# For bash
echo 'export PATH="$HOME/.claude/claude-slack/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# For zsh
echo 'export PATH="$HOME/.claude/claude-slack/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### 6. Start the Listener

**Option A: Manual (foreground)**
```bash
# Start the Slack listener (run in background or separate terminal)
claude-slack-listener

# Or use the ensure script (starts if not running)
claude-slack-ensure
```

**Option B: Systemd Service (recommended for 24/7)**
```bash
# Install and start the service
claude-slack-service install
claude-slack-service start

# Other commands
claude-slack-service status   # Check status
claude-slack-service logs     # View logs (follow mode)
claude-slack-service restart  # Restart service
claude-slack-service stop     # Stop service
claude-slack-service uninstall # Remove service
```

The systemd service:
- Auto-starts on login
- Auto-restarts on crash or disconnect
- Survives machine sleep/wake cycles
- Runs with security hardening (read-only filesystem, no privilege escalation)

### 7. Start a Claude Session

First, create a Slack channel for your project (e.g., `#claude-myproject`) and invite the bot:
1. In Slack, create a new channel or use an existing one
2. Invite the bot: `/invite @Claude Code Bot`

Then start Claude:

```bash
# Navigate to your project
cd /path/to/your/project

# Start Claude with Slack integration (recommended: dedicated channel per project)
claude-slack -c channel-name

# Or use thread mode in your default channel (no setup needed)
claude-slack
```

> **Tip:** Custom channel mode (`-c`) is recommended. Each project gets its own dedicated Slack channel with top-level messages, making it easier to follow conversations and manage multiple projects.

## Usage

### Basic Usage

```bash
# Start in a dedicated Slack channel (recommended)
# The channel must exist and have the bot invited
claude-slack -c claude-myproject

# Start with a specific message
claude-slack -c claude-myproject --print "Help me refactor this code"

# Or use thread mode in default channel (from .env)
claude-slack

# Send permissions to a separate channel
claude-slack -c claude-myproject --permissions-channel security-approvals
```

### Interacting via Slack

1. **Custom Channel Mode** (`-c`, recommended): Messages are top-level in a dedicated channel. Just type in the channel to send messages to Claude.

2. **Thread Mode**: Claude creates a thread in your default channel. Reply in the thread to send messages to Claude.

3. **Permission Prompts**: When Claude needs permission, you'll see interactive buttons:
   - **Yes** - Approve this action
   - **Yes, don't ask again** - Approve and remember for similar actions
   - **No** - Deny and provide feedback

4. **Quick Responses**: React with emoji for fast permission responses:
   - 1️⃣ or 👍 = Approve
   - 2️⃣ = Approve and remember
   - 3️⃣ or 👎 = Deny

### Session Management

```bash
# List active sessions
claude-slack-sessions

# Clean up stale sessions
claude-slack-cleanup

# Ensure listener is running
claude-slack-ensure
```

## Available Commands

| Command | Description |
|---------|-------------|
| `claude-slack` | Start a new Claude session with Slack integration |
| `claude-slack-listener` | Start the Slack listener daemon (foreground) |
| `claude-slack-service` | Manage systemd service (install/start/stop/status/logs) |
| `claude-slack-ensure` | Ensure listener is running (start if not) |
| `claude-slack-sessions` | List all active sessions |
| `claude-slack-cleanup` | Clean up stale/inactive sessions |
| `claude-slack-test` | Test Slack connection |

## How It Works

### Hooks

This integration uses Claude Code hooks to communicate with Slack:

| Hook | Purpose |
|------|---------|
| **Notification** (`on_notification.py`) | Posts permission prompts with interactive buttons |
| **Stop** (`on_stop.py`) | Posts Claude's responses and session summaries |
| **PostToolUse** (`on_posttooluse.py`) | Updates todo progress in real-time |

### Session Flow

1. `claude-slack` starts the wrapper which:
   - Generates a unique session ID
   - Creates a Unix socket for receiving Slack messages
   - Registers the session in SQLite database
   - Posts initial message to Slack
   - Starts Claude Code with hooks configured

2. When Claude needs permission:
   - Notification hook captures the request
   - Posts to Slack with interactive buttons
   - User clicks button → Slack listener receives it
   - Listener sends response to Claude via Unix socket

3. When Claude responds:
   - Stop hook captures the response
   - Posts to the correct Slack thread
   - Includes rich summary (if session complete)

## Troubleshooting

### Checking Logs

```bash
# Slack listener logs
tail -f ~/.claude/slack/logs/slack_listener.log

# Notification hook debug logs
tail -f ~/.claude/slack/logs/notification_hook_debug.log

# Wrapper logs (session-specific)
tail -f ~/.claude/slack/logs/wrapper_*.log

# Session registry
sqlite3 ~/.claude/slack/registry.db "SELECT session_id, status, slack_channel FROM sessions;"
```

### Common Issues

**Messages not being received:**
```bash
# Check if listener is running
pgrep -f slack_listener.py

# Restart listener
pkill -f slack_listener.py
claude-slack-listener
```

**Permission buttons not working:**
- Ensure `interactivity.is_enabled: true` in your Slack app manifest
- Check that the Slack app has been reinstalled after manifest changes

**Wrong number of permission options:**
- The integration detects 2 vs 3 option prompts from terminal output
- If detection fails, it defaults to safe 2-option (Yes/No)
- Check `notification_hook_debug.log` for parsing details

**Session not found errors:**
```bash
# Clean up stale sessions
claude-slack-cleanup

# Check registry for orphaned sessions
sqlite3 ~/.claude/slack/registry.db "SELECT * FROM sessions WHERE status='active';"
```

**Subagent permissions not routing:**
- Subagents use the same project_dir, so buffer lookup should work
- Check that the main session is still active in the registry

## Project Structure

```
~/.claude/claude-slack/
├── core/                          # Core Python modules
│   ├── slack_listener.py          # Slack event listener (buttons, messages)
│   ├── claude_wrapper_hybrid.py   # Wraps Claude Code with I/O capture
│   ├── session_registry.py        # High-level session management
│   ├── registry_db.py             # SQLite database schema/operations
│   ├── transcript_parser.py       # Parse Claude transcripts for summaries
│   └── config.py                  # Centralized configuration
├── .claude/
│   ├── hooks/                     # Claude Code hook scripts
│   │   ├── on_notification.py     # Permission prompts → Slack
│   │   ├── on_stop.py             # Responses → Slack
│   │   ├── on_posttooluse.py      # Todo updates → Slack
│   │   └── on_pretooluse.py       # Pre-tool logging
│   └── settings.local.json        # Hook configuration
├── bin/                           # Executable scripts
│   ├── claude-slack               # Main entry point
│   ├── claude-slack-listener      # Start listener
│   ├── claude-slack-ensure        # Ensure listener running
│   ├── claude-slack-sessions      # List sessions
│   ├── claude-slack-cleanup       # Clean up sessions
│   └── claude-slack-test          # Test connection
├── .env.example                   # Environment template
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## Data Storage

All data is stored under `~/.claude/slack/`:

| Path | Purpose |
|------|---------|
| `registry.db` | SQLite database of sessions |
| `sockets/*.sock` | Unix sockets for IPC |
| `logs/*.log` | Debug and error logs |

## Security

- **Never commit `.env`** - Contains sensitive tokens
- **Rotate tokens** immediately if exposed
- **Use private channels** for sensitive projects
- **Review permissions** before approving via Slack

The `.gitignore` excludes sensitive files by default.

## Known Limitations

- One active session per custom channel (use different channel names for concurrent project sessions)
- Buffer detection may fail for very fast parallel subagents
- Slack message length limits may truncate very long responses
- Session timeout is 24 hours (configurable in registry cleanup)

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Test thoroughly
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Credits

Created for use with Anthropic's Claude Code CLI.
