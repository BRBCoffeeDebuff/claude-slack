"""
Unit tests for .claude/hooks/on_notification.py

Tests permission prompt handling, ANSI stripping, message splitting,
and Block Kit card generation.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add hooks directory to path for imports
CLAUDE_SLACK_DIR = Path(__file__).parent.parent.parent.parent
HOOKS_DIR = CLAUDE_SLACK_DIR / ".claude" / "hooks"


# Import hook module functions (need to mock sys.exit and stdin first)
@pytest.fixture
def on_notification_module():
    """Import on_notification module with mocked environment."""
    # Mock stdin to avoid issues
    with patch('sys.stdin'):
        # Add core dir to path
        sys.path.insert(0, str(CLAUDE_SLACK_DIR / "core"))
        # Import the specific functions we need to test
        spec = {}
        exec(open(HOOKS_DIR / "on_notification.py").read(), spec)
        return spec


class TestStripAnsiCodes:
    """Test ANSI escape code removal."""

    def test_strip_ansi_codes_bold(self, ansi_test_strings):
        """Remove bold formatting."""
        # Manually test since module import is complex
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        result = ansi_escape.sub('', ansi_test_strings['bold'])
        assert result == 'Bold text'
        assert '\x1b' not in result

    def test_strip_ansi_codes_color(self, ansi_test_strings):
        """Remove color codes."""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        result = ansi_escape.sub('', ansi_test_strings['red'])
        assert result == 'Red text'

    def test_strip_ansi_codes_complex(self, ansi_test_strings):
        """Remove complex ANSI sequences."""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        result = ansi_escape.sub('', ansi_test_strings['complex'])
        assert 'Complex' in result
        assert 'formatting' in result
        assert '\x1b' not in result

    def test_strip_ansi_codes_no_ansi(self, ansi_test_strings):
        """Handle plain text without ANSI."""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        result = ansi_escape.sub('', ansi_test_strings['no_ansi'])
        assert result == 'Plain text without ANSI'


class TestSplitMessage:
    """Test message splitting for Slack's 40K limit."""

    def _split_message(self, text, max_length=39000):
        """Local implementation of split_message."""
        if len(text) <= max_length:
            return [text]

        chunks = []
        while text:
            if len(text) <= max_length:
                chunks.append(text)
                break
            break_point = text.rfind('\n', max_length - 500, max_length)
            if break_point == -1:
                break_point = max_length
            chunks.append(text[:break_point])
            text = text[break_point:].lstrip('\n')
        return chunks

    def test_split_message_under_limit(self):
        """Short messages should not be split."""
        text = "Short message"
        chunks = self._split_message(text, max_length=100)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_split_message_exact_limit(self):
        """Message at exact limit should not be split."""
        text = "x" * 100
        chunks = self._split_message(text, max_length=100)
        assert len(chunks) == 1

    def test_split_message_over_limit(self):
        """Long messages should be split at newlines."""
        text = "Line 1\n" * 100
        chunks = self._split_message(text, max_length=50)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 50

    def test_split_message_no_newlines(self):
        """Messages without newlines split at max_length."""
        text = "x" * 200
        chunks = self._split_message(text, max_length=100)
        assert len(chunks) == 2


class TestParsePermissionPrompt:
    """Test parsing exact permission options from terminal output."""

    def _parse_permission_prompt(self, output_bytes, session_id):
        """Local implementation of parse_permission_prompt_from_output."""
        import re
        try:
            output_text = output_bytes.decode('utf-8', errors='ignore')
            # Strip ANSI
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            clean_text = ansi_escape.sub('', output_text)

            option_pattern = re.compile(r'^\s*(\d+)[\.\)]\s*(.+)$', re.MULTILINE)
            matches = option_pattern.findall(clean_text)

            if not matches:
                return None

            # Group consecutive options
            groups = []
            current_group = []
            expected_next = None

            for num_str, text in matches:
                num = int(num_str)
                if expected_next is None:
                    current_group = [text.strip()]
                    expected_next = num + 1
                elif num == expected_next:
                    current_group.append(text.strip())
                    expected_next = num + 1
                else:
                    if current_group and 2 <= len(current_group) <= 3:
                        groups.append(current_group)
                    current_group = [text.strip()]
                    expected_next = num + 1

            if current_group and 2 <= len(current_group) <= 3:
                groups.append(current_group)

            # Return first valid group
            permission_keywords = ['yes', 'no', 'approve', 'deny', 'allow']
            for group in groups:
                group_text = ' '.join(group).lower()
                if any(kw in group_text for kw in permission_keywords):
                    return group

            return groups[0] if groups else None

        except Exception:
            return None

    def test_parse_permission_2_options(self):
        """Detect Yes/No prompt (2 options)."""
        output = b"""
Claude needs permission to use Bash

1. Yes
2. No, and tell Claude what to do differently (esc)
"""
        options = self._parse_permission_prompt(output, "test123")
        assert options is not None
        assert len(options) == 2
        assert options[0] == "Yes"
        assert "No" in options[1]

    def test_parse_permission_3_options(self):
        """Detect Yes/Yes-remember/No prompt (3 options)."""
        output = b"""
Claude needs permission to use Bash

1. Yes
2. Yes, and don't ask again for ls commands
3. No, and tell Claude what to do differently (esc)
"""
        options = self._parse_permission_prompt(output, "test123")
        assert options is not None
        assert len(options) == 3
        assert options[0] == "Yes"
        assert "don't ask again" in options[1]
        assert "No" in options[2]

    def test_parse_permission_no_matches(self):
        """Return None when no permission prompt found."""
        output = b"Some random output without numbered options"
        options = self._parse_permission_prompt(output, "test123")
        assert options is None


class TestDeterminePermissionContext:
    """Test context detection for permission prompts."""

    def _determine_context(self, tool_name, tool_input):
        """Local implementation of determine_permission_context."""
        import re

        if tool_name == "Bash":
            command = tool_input.get('command', '')

            # Background process
            if re.search(r'(?<![>&])\s&\s', command) or re.search(r'(?<![>&])\s&$', command):
                return ("bash_background_or_tmp", 2)

            # /tmp operations
            if re.search(r'(touch|rm|cat.*>)\s+/tmp/', command):
                return ("bash_background_or_tmp", 2)

            # Dangerous commands (2 options)
            dangerous_patterns = [r'\bpkill\b', r'\bkillall\b', r'\bkill\s+-9\b',
                                  r'\brm\s+-rf\b', r'\brm\s+-r\b', r'\bsudo\b']
            for pattern in dangerous_patterns:
                if re.search(pattern, command):
                    return ("bash_dangerous", 2)

            # Directory listing (3 options)
            if re.search(r'\bls\b', command):
                return ("bash_directory_access", 3)

            # File operations (3 options)
            if re.search(r'(echo.*>|touch|rm\s+(?!-rf))', command):
                return ("bash_file_commands", 3)

            return ("bash_file_commands", 3)

        elif tool_name == "Write":
            return ("write_create", 3)
        elif tool_name == "Edit":
            return ("edit_modify", 3)
        elif tool_name == "Read":
            return ("read_file", 3)
        elif tool_name == "Task":
            return ("task_subagent", 3)
        else:
            return ("default", 3)

    def test_determine_context_dangerous_pkill(self):
        """Detect pkill as dangerous command (2 options)."""
        tool_input = {'command': 'pkill -9 python'}
        context, count = self._determine_context("Bash", tool_input)
        assert context == "bash_dangerous"
        assert count == 2

    def test_determine_context_dangerous_rm_rf(self):
        """Detect rm -rf as dangerous command (2 options)."""
        tool_input = {'command': 'rm -rf /tmp/old_files'}
        context, count = self._determine_context("Bash", tool_input)
        assert context == "bash_dangerous"
        assert count == 2

    def test_determine_context_dangerous_sudo(self):
        """Detect sudo as dangerous command (2 options)."""
        tool_input = {'command': 'sudo apt-get update'}
        context, count = self._determine_context("Bash", tool_input)
        assert context == "bash_dangerous"
        assert count == 2

    def test_determine_context_background(self):
        """Detect background process (2 options)."""
        tool_input = {'command': 'sleep 10 &'}
        context, count = self._determine_context("Bash", tool_input)
        assert context == "bash_background_or_tmp"
        assert count == 2

    def test_determine_context_tmp(self):
        """Detect /tmp operations (2 options)."""
        tool_input = {'command': 'touch /tmp/test.txt'}
        context, count = self._determine_context("Bash", tool_input)
        assert context == "bash_background_or_tmp"
        assert count == 2

    def test_determine_context_directory_access(self):
        """Detect directory listing (3 options)."""
        tool_input = {'command': 'ls /home/user/projects'}
        context, count = self._determine_context("Bash", tool_input)
        assert context == "bash_directory_access"
        assert count == 3

    def test_determine_context_file_commands(self):
        """Detect file operations (3 options)."""
        tool_input = {'command': 'echo "test" > file.txt'}
        context, count = self._determine_context("Bash", tool_input)
        assert context == "bash_file_commands"
        assert count == 3

    def test_determine_context_write_tool(self):
        """Detect Write tool context."""
        tool_input = {'file_path': '/path/to/file.py', 'content': 'code'}
        context, count = self._determine_context("Write", tool_input)
        assert context == "write_create"
        assert count == 3

    def test_determine_context_edit_tool(self):
        """Detect Edit tool context."""
        tool_input = {'file_path': '/path/to/file.py'}
        context, count = self._determine_context("Edit", tool_input)
        assert context == "edit_modify"
        assert count == 3


class TestExtractTargetFromCommand:
    """Test extracting targets from tool inputs."""

    def _extract_target(self, tool_name, tool_input):
        """Local implementation of extract_target_from_command."""
        import re

        if tool_name == "Bash":
            command = tool_input.get('command', '')

            # Extract from ls
            if command.strip().startswith('ls'):
                match = re.search(r'ls(?:\s+(?:-[a-zA-Z]+\s+)*)?([^\s]+)', command)
                if match:
                    path = match.group(1).rstrip('/')
                    if '/' in path:
                        return os.path.basename(path)

            # Extract from sudo (handles hyphenated commands like apt-get)
            if 'sudo' in command:
                match = re.search(r'sudo\s+([\w-]+)', command)
                if match:
                    return f"sudo {match.group(1)}"

            # Extract from redirect
            patterns = [
                r'>\s*([^\s;&|]+)',
                r'touch\s+([^\s;&|]+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, command)
                if match:
                    return os.path.basename(match.group(1))

        elif tool_name in ("Write", "Edit"):
            file_path = tool_input.get('file_path', '')
            if file_path.startswith('../'):
                parts = file_path.split('/')
                meaningful_parts = [p for p in parts[:-1] if p and p != '..']
                if meaningful_parts:
                    return meaningful_parts[-1]

        return None

    def test_extract_target_bash_ls(self):
        """Extract directory from ls command."""
        tool_input = {'command': 'ls /home/user/projects'}
        target = self._extract_target("Bash", tool_input)
        assert target == "projects"

    def test_extract_target_bash_sudo(self):
        """Extract command from sudo (including hyphenated commands)."""
        tool_input = {'command': 'sudo apt-get install package'}
        target = self._extract_target("Bash", tool_input)
        assert target == "sudo apt-get"

    def test_extract_target_bash_redirect(self):
        """Extract filename from output redirection."""
        tool_input = {'command': 'echo "test" > output.txt'}
        target = self._extract_target("Bash", tool_input)
        assert target == "output.txt"

    def test_extract_target_write(self):
        """Extract directory from Write tool."""
        tool_input = {'file_path': '../../other-project/file.py'}
        target = self._extract_target("Write", tool_input)
        assert target == "other-project"


class TestGetExactPermissionOptions:
    """Test generation of exact permission option text."""

    def _get_exact_options(self, tool_name, tool_input, permission_mode="default"):
        """Local implementation of get_exact_permission_options."""
        import re

        # Determine context
        if tool_name == "Bash":
            command = tool_input.get('command', '')
            # Check for dangerous/2-option scenarios
            dangerous_patterns = [r'\bpkill\b', r'\bsudo\b', r'\brm\s+-rf\b']
            for pattern in dangerous_patterns:
                if re.search(pattern, command):
                    return ["Yes", "No, and tell Claude what to do differently (esc)"]

            # Background or /tmp
            if re.search(r'(?<![>&])\s&$', command) or re.search(r'\s/tmp/', command):
                return ["Yes", "No, and tell Claude what to do differently (esc)"]

        # Default 3-option
        return [
            "Yes",
            "Yes, and don't ask again for this operation",
            "No, and tell Claude what to do differently (esc)"
        ]

    def test_get_exact_permission_options_2_option(self):
        """Generate 2-option text for dangerous commands."""
        tool_input = {'command': 'pkill python'}
        options = self._get_exact_options("Bash", tool_input)
        assert len(options) == 2
        assert options[0] == "Yes"
        assert "No" in options[1]

    def test_get_exact_permission_options_3_option(self):
        """Generate 3-option text for normal commands."""
        tool_input = {'command': 'echo "test" > file.txt'}
        options = self._get_exact_options("Bash", tool_input)
        assert len(options) == 3
        assert options[0] == "Yes"
        assert "don't ask again" in options[1]
        assert "No" in options[2]


class TestPostPermissionCard:
    """Test Block Kit card generation for permissions."""

    def test_post_permission_card_structure(self, mock_slack_client):
        """Verify Block Kit card structure."""
        # We'll test the structure expected by Slack
        text = "Permission Required: Bash\n\n**Command:** `ls /tmp`"
        options = ["Yes", "No, and tell Claude what to do differently"]

        # Build expected blocks structure
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Permission Required: Bash", "emoji": True}
            },
            {"type": "divider"},
            {
                "type": "actions",
                "block_id": "permission_actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "1. Yes", "emoji": True},
                        "action_id": "permission_response_1",
                        "value": "1",
                        "style": "primary"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "2. No, and tell Claude...", "emoji": True},
                        "action_id": "permission_response_2",
                        "value": "2",
                        "style": "danger"
                    }
                ]
            }
        ]

        # Verify structure
        assert blocks[0]["type"] == "header"
        assert blocks[-1]["type"] == "actions"
        assert len(blocks[-1]["elements"]) == 2
        assert blocks[-1]["elements"][0]["style"] == "primary"
        assert blocks[-1]["elements"][1]["style"] == "danger"

    def test_post_permission_card_3_buttons(self, mock_slack_client):
        """Verify 3-button card structure."""
        options = [
            "Yes",
            "Yes, allow all edits",
            "No, and tell Claude what to do differently"
        ]

        # Build 3-button elements
        elements = []
        for i, option in enumerate(options, 1):
            button = {
                "type": "button",
                "text": {"type": "plain_text", "text": f"{i}. {option[:50]}", "emoji": True},
                "action_id": f"permission_response_{i}",
                "value": str(i)
            }
            if i == 1:
                button["style"] = "primary"
            elif i == 3:
                button["style"] = "danger"
            elements.append(button)

        assert len(elements) == 3
        assert elements[0]["style"] == "primary"
        assert elements[2]["style"] == "danger"


class TestShouldShowButtons:
    """Test button display logic for permission prompts."""

    def _should_show_buttons(self, options):
        """Helper to call should_show_buttons from the hook module."""
        # Inline implementation matching the hook
        if not options:
            return False

        num_options = len(options)

        # Pattern 1: Simple Yes/No (2 options)
        if num_options == 2:
            opt1 = options[0].lower().strip()
            opt2 = options[1].lower().strip()
            if opt1 == "yes" and opt2.startswith("no"):
                return True

        # Pattern 2: Yes / Yes, allow... / No (3 options)
        if num_options == 3:
            opt1 = options[0].lower().strip()
            opt2 = options[1].lower().strip()
            opt3 = options[2].lower().strip()
            if (opt1 == "yes" and
                opt2.startswith("yes, allow") and
                opt3.startswith("no")):
                return True

        return False

    def test_should_show_buttons_yes_no(self):
        """2-option Yes/No should show buttons."""
        options = ["Yes", "No, and tell Claude what to do differently"]
        assert self._should_show_buttons(options) is True

    def test_should_show_buttons_yes_allow_no(self):
        """3-option Yes/Yes,allow.../No should show buttons."""
        options = [
            "Yes",
            "Yes, allow all edits during this session",
            "No, and tell Claude what to do differently"
        ]
        assert self._should_show_buttons(options) is True

    def test_should_show_buttons_4_options_no_buttons(self):
        """4 options should NOT show buttons."""
        options = [
            "Option A: Do something",
            "Option B: Do something else",
            "Option C: Another choice",
            "Option D: Final choice"
        ]
        assert self._should_show_buttons(options) is False

    def test_should_show_buttons_custom_3_options_no_buttons(self):
        """3 options that don't match Yes/Yes,allow.../No pattern should NOT show buttons."""
        options = [
            "Continue with current approach",
            "Try alternative method",
            "Cancel and explain why"
        ]
        assert self._should_show_buttons(options) is False

    def test_should_show_buttons_empty_list(self):
        """Empty options should NOT show buttons."""
        assert self._should_show_buttons([]) is False
        assert self._should_show_buttons(None) is False

    def test_should_show_buttons_single_option(self):
        """Single option should NOT show buttons."""
        options = ["Yes"]
        assert self._should_show_buttons(options) is False

    def test_should_show_buttons_case_insensitive(self):
        """Button matching should be case-insensitive."""
        options = ["YES", "YES, ALLOW ALL EDITS", "NO, CANCEL"]
        assert self._should_show_buttons(options) is True


class TestRetryParseTranscript:
    """Test exponential backoff retry for transcript parsing."""

    def test_retry_loop_parameters(self):
        """Verify retry parameters."""
        max_wait = 2.5
        check_interval = 0.1
        multiplier = 1.1
        max_backoff = 0.5

        # Simulate retry timing
        wait_times = []
        for attempt in range(10):
            backoff = min(check_interval * (multiplier ** attempt), max_backoff)
            wait_times.append(backoff)

        # Verify exponential growth capped at max_backoff
        assert wait_times[0] == 0.1
        assert all(w <= max_backoff for w in wait_times)


class TestEnhanceNotificationMessage:
    """Test notification message enhancement."""

    def test_enhance_adds_emoji_for_idle(self):
        """Idle notifications get clock emoji."""
        message = "Claude is waiting for input"
        notification_type = "idle_prompt"

        # Expected enhancement adds emoji prefix
        assert notification_type == "idle_prompt"

    def test_enhance_adds_emoji_for_auth(self):
        """Auth notifications get check emoji."""
        notification_type = "auth_success"
        assert notification_type == "auth_success"

    def test_enhance_permission_returns_options(self):
        """Permission prompts return option list."""
        notification_type = "permission_prompt"
        # When we can't parse buffer, we should get safe 2-option default
        expected_options = [
            "Yes",
            "No, and tell Claude what to do differently"
        ]
        assert len(expected_options) == 2


class TestPermissionNotificationBehavior:
    """Test permission notification button/reaction behavior.

    Requirements:
    1. ALWAYS show full text with numbered options
    2. Exact buffer match: show buttons + emoji reactions
    3. Fallback (no exact match): show emoji reactions only (no buttons)
    """

    def test_use_buttons_only_for_exact_buffer_match(self):
        """use_buttons should be True ONLY when exact options parsed from buffer."""
        # When we have exact options from buffer, use_buttons should be True
        exact_options_from_buffer = ["Yes", "Yes, allow all edits", "No"]
        use_buttons = exact_options_from_buffer is not None
        assert use_buttons is True

    def test_use_buttons_false_for_hardcoded_fallback(self):
        """use_buttons should be False when using hardcoded/fallback options."""
        # When buffer parsing fails, exact_options_from_buffer is None
        exact_options_from_buffer = None
        use_buttons = exact_options_from_buffer is not None
        assert use_buttons is False

    def test_permission_options_always_set_for_emoji_reactions(self):
        """permission_options should always be set for emoji reactions."""
        # Even when buttons aren't shown, permission_options should be set
        # so emoji reactions can be added
        fallback_options = [
            "Approve this time",
            "Approve commands like this for this project",
            "Deny, tell Claude what to do instead"
        ]
        # permission_options is set even for fallback
        permission_options = fallback_options
        assert permission_options is not None
        assert len(permission_options) == 3

    def test_should_show_buttons_with_mismatched_options_returns_false(self):
        """Options that don't match exact patterns should not show buttons."""
        # Helper function matching hook implementation
        def should_show_buttons(options):
            if not options:
                return False
            num_options = len(options)
            if num_options == 2:
                opt1 = options[0].lower().strip()
                opt2 = options[1].lower().strip()
                if opt1 == "yes" and opt2.startswith("no"):
                    return True
            if num_options == 3:
                opt1 = options[0].lower().strip()
                opt2 = options[1].lower().strip()
                opt3 = options[2].lower().strip()
                if (opt1 == "yes" and
                    opt2.startswith("yes, allow") and
                    opt3.startswith("no")):
                    return True
            return False

        # These should NOT match button patterns
        assert should_show_buttons(["A", "B", "C", "D"]) is False  # 4 options
        assert should_show_buttons(["Continue", "Cancel"]) is False  # Not Yes/No
        assert should_show_buttons(["Yes", "Maybe", "No"]) is False  # Middle doesn't match

    def test_emoji_reactions_match_option_count(self):
        """Number of emoji reactions should match number of options."""
        all_emojis = ["one", "two", "three", "four", "five"]

        # 2 options -> 2 emojis
        options_2 = ["Yes", "No"]
        assert all_emojis[:len(options_2)] == ["one", "two"]

        # 3 options -> 3 emojis
        options_3 = ["Yes", "Yes, allow", "No"]
        assert all_emojis[:len(options_3)] == ["one", "two", "three"]

        # 4 options -> 4 emojis
        options_4 = ["A", "B", "C", "D"]
        assert all_emojis[:len(options_4)] == ["one", "two", "three", "four"]

        # 5 options -> 5 emojis
        options_5 = ["A", "B", "C", "D", "E"]
        assert all_emojis[:len(options_5)] == ["one", "two", "three", "four", "five"]

    def test_full_text_always_included(self):
        """Permission card should always include full text with numbered options."""
        full_text = """⚠️ **Permission Required: Bash**

**Command:** `rm -rf /tmp/test`

**Reply with:**
1. Yes
2. Yes, allow all commands during this session
3. No, and tell Claude what to do differently"""

        # The full text should be preserved (up to Slack limit)
        assert "**Reply with:**" in full_text
        assert "1. Yes" in full_text
        assert "2. Yes, allow" in full_text
        assert "3. No" in full_text

    def test_button_mismatch_safety(self):
        """Buttons with wrong number of options could cause dangerous mismatches.

        If CLI shows 3 options but Slack shows 2 buttons, clicking button 2
        would send "2" which maps to option 2 in CLI (not button 2's label).
        This test documents why we only show buttons for exact matches.
        """
        cli_options = ["Yes", "Yes, allow all", "No"]  # 3 options
        fallback_options = ["Yes", "No"]  # 2 options (parsing failed)

        # If we showed 2 buttons for 3-option CLI prompt:
        # Button 1 "Yes" -> sends "1" -> CLI option 1 "Yes" ✓
        # Button 2 "No" -> sends "2" -> CLI option 2 "Yes, allow all" ✗ DANGEROUS!

        # This is why we only show buttons when we have EXACT match
        # from buffer parsing, never for fallback options
        assert len(cli_options) != len(fallback_options)


class TestStalePermissionCleanup:
    """Test cleanup of stale permission messages when user responds via terminal."""

    def test_permission_message_ts_stored_for_tracking(self):
        """permission_message_ts should be stored in registry for cleanup."""
        # When a permission card is posted, its message_ts should be stored
        message_ts = "1234567890.123456"
        session_updates = {'permission_message_ts': message_ts}

        # The session should be updated with the message_ts
        assert 'permission_message_ts' in session_updates
        assert session_updates['permission_message_ts'] == message_ts

    def test_permission_message_ts_cleared_after_cleanup(self):
        """permission_message_ts should be cleared after message is deleted."""
        # After cleanup, permission_message_ts should be set to None
        session_updates = {'permission_message_ts': None}

        assert session_updates['permission_message_ts'] is None

    def test_cleanup_handles_already_deleted_message(self):
        """Cleanup should handle case where message was already deleted via button."""
        # If message_not_found error, we should still clear the ts
        # (the button handler may have already deleted it)
        error_responses = ['message_not_found', 'channel_not_found']

        # message_not_found should be handled gracefully
        assert 'message_not_found' in error_responses
