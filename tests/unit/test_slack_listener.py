"""
Unit tests for core/slack_listener.py

Tests Slack event handling including message routing,
permission button handling, and reaction responses.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

# Add core directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))


class TestGetSocketForThread:
    """Tests for get_socket_for_thread()."""

    def test_get_socket_for_thread_exists(self, temp_registry_db, sample_session_data):
        """Registry lookup by thread_ts."""
        # Create session with thread_ts
        temp_registry_db.create_session(sample_session_data)

        with patch('slack_listener.registry_db', temp_registry_db):
            from slack_listener import get_socket_for_thread
            socket_path = get_socket_for_thread(sample_session_data['thread_ts'])
            assert socket_path == sample_session_data['socket_path']

    def test_get_socket_for_thread_prefers_wrapper(self, temp_registry_db, sample_session_data):
        """Prefer wrapper session (8 chars) over Claude UUID (36 chars)."""
        # Create wrapper session (8 char ID)
        wrapper_data = sample_session_data.copy()
        wrapper_data['session_id'] = 'wrap1234'  # 8 chars
        temp_registry_db.create_session(wrapper_data)

        # Create Claude UUID session (36 chars) with same thread
        uuid_data = sample_session_data.copy()
        uuid_data['session_id'] = '12345678-1234-5678-1234-567812345678'  # 36 chars UUID
        uuid_data['socket_path'] = '/tmp/uuid.sock'
        temp_registry_db.create_session(uuid_data)

        with patch('slack_listener.registry_db', temp_registry_db):
            from slack_listener import get_socket_for_thread
            socket_path = get_socket_for_thread(sample_session_data['thread_ts'])
            # Should prefer wrapper's socket
            assert socket_path == wrapper_data['socket_path']

    def test_get_socket_for_thread_not_found(self, temp_registry_db):
        """Returns None when thread not found."""
        with patch('slack_listener.registry_db', temp_registry_db):
            from slack_listener import get_socket_for_thread
            socket_path = get_socket_for_thread('nonexistent.thread')
            assert socket_path is None

    def test_get_socket_for_thread_no_registry(self):
        """Returns None when no registry database."""
        with patch('slack_listener.registry_db', None):
            from slack_listener import get_socket_for_thread
            socket_path = get_socket_for_thread('any.thread')
            assert socket_path is None


class TestGetSocketForChannel:
    """Tests for get_socket_for_channel()."""

    def test_get_socket_for_channel_exists(self, temp_registry_db, sample_session_data_custom_channel, mock_slack_client):
        """Custom channel mode lookup."""
        temp_registry_db.create_session(sample_session_data_custom_channel)

        # Create socket file
        socket_path = sample_session_data_custom_channel['socket_path']
        Path(socket_path).parent.mkdir(parents=True, exist_ok=True)
        Path(socket_path).touch()

        try:
            with patch('slack_listener.registry_db', temp_registry_db):
                with patch('slack_listener.app') as mock_app:
                    mock_app.client = mock_slack_client
                    from slack_listener import get_socket_for_channel
                    result = get_socket_for_channel(sample_session_data_custom_channel['channel'])
                    assert result == socket_path
        finally:
            if Path(socket_path).exists():
                Path(socket_path).unlink()

    def test_get_socket_for_channel_skips_stale(self, temp_registry_db, sample_session_data_custom_channel, mock_slack_client):
        """Skips sessions with missing socket files."""
        temp_registry_db.create_session(sample_session_data_custom_channel)
        # Don't create the socket file - it's stale

        with patch('slack_listener.registry_db', temp_registry_db):
            with patch('slack_listener.app') as mock_app:
                mock_app.client = mock_slack_client
                from slack_listener import get_socket_for_channel
                result = get_socket_for_channel(sample_session_data_custom_channel['channel'])
                assert result is None


class TestSendResponse:
    """Tests for send_response()."""

    def test_send_response_registry_mode(self, temp_registry_db, sample_session_data, tmp_path):
        """Routes via registry socket when thread found."""
        temp_registry_db.create_session(sample_session_data)

        # Create actual socket
        socket_path = tmp_path / "test.sock"

        import socket as sock_module
        server = sock_module.socket(sock_module.AF_UNIX, sock_module.SOCK_STREAM)
        server.bind(str(socket_path))
        server.listen(1)
        server.setblocking(False)

        # Update session with real socket path
        temp_registry_db.update_session(sample_session_data['session_id'], {
            'socket_path': str(socket_path),
            'slack_thread_ts': '123.456',
            'slack_channel': 'C123'
        })

        try:
            with patch('slack_listener.registry_db', temp_registry_db):
                with patch('slack_listener.get_socket_for_thread', return_value=str(socket_path)):
                    from slack_listener import send_response
                    mode = send_response("test message", thread_ts='123.456')
                    assert mode == "registry_socket"
        finally:
            server.close()

    def test_send_response_file_fallback(self, tmp_path):
        """Falls back to file write when socket unavailable."""
        response_file = tmp_path / "slack_response.txt"

        with patch('slack_listener.registry_db', None):
            with patch('slack_listener.SOCKET_PATH', '/nonexistent/socket'):
                with patch('slack_listener.RESPONSE_FILE', response_file):
                    from slack_listener import send_response
                    mode = send_response("test message")
                    assert mode == "file"
                    assert response_file.read_text() == "test message"


class TestHandleMessage:
    """Tests for handle_message event handler."""

    def test_handle_message_threaded(self, temp_registry_db, sample_session_data, tmp_path):
        """Routes threaded message to correct session."""
        temp_registry_db.create_session(sample_session_data)

        # Create mock socket
        socket_path = tmp_path / "test.sock"

        with patch('slack_listener.registry_db', temp_registry_db):
            with patch('slack_listener.get_socket_for_thread', return_value=str(socket_path)):
                with patch('slack_listener.send_response') as mock_send:
                    mock_send.return_value = "registry_socket"

                    from slack_listener import handle_message

                    event = {
                        'type': 'message',
                        'user': 'U123',
                        'text': 'Hello Claude',
                        'ts': '111.222',
                        'channel': 'C123',
                        'channel_type': 'channel',
                        'thread_ts': sample_session_data['thread_ts']
                    }

                    say = MagicMock()
                    handle_message(event, say)

                    mock_send.assert_called_once()

    def test_handle_message_ignores_bot(self):
        """Ignores messages from bots."""
        from slack_listener import handle_message

        event = {
            'type': 'message',
            'bot_id': 'B123',  # Bot message
            'text': 'Bot message',
            'channel': 'C123'
        }

        say = MagicMock()
        handle_message(event, say)

        say.assert_not_called()

    def test_handle_message_channel_requires_prefix(self):
        """Channel messages need command prefix."""
        with patch('slack_listener.send_response') as mock_send:
            from slack_listener import handle_message

            # Regular message without prefix
            event = {
                'type': 'message',
                'user': 'U123',
                'text': 'just chatting',  # No prefix
                'ts': '111.222',
                'channel': 'C123',
                'channel_type': 'channel'
                # No thread_ts = not threaded
            }

            # Mock to return None for channel lookup
            with patch('slack_listener.get_socket_for_channel', return_value=None):
                say = MagicMock()
                handle_message(event, say)

                mock_send.assert_not_called()


class TestHandleReaction:
    """Tests for handle_reaction event handler."""

    def test_handle_reaction_approve(self, mock_slack_client):
        """1 emoji maps to '1' response."""
        with patch('slack_listener.send_response') as mock_send:
            mock_send.return_value = "registry_socket"

            from slack_listener import handle_reaction

            body = {
                'event': {
                    'type': 'reaction_added',
                    'user': 'U123',
                    'reaction': 'one',
                    'item': {
                        'channel': 'C123',
                        'ts': '111.222'
                    }
                }
            }

            mock_slack_client.conversations_history.return_value = {
                'ok': True,
                'messages': [{'ts': '111.222', 'thread_ts': '100.000'}]
            }

            handle_reaction(body, mock_slack_client)

            mock_send.assert_called_once()
            assert mock_send.call_args[0][0] == "1"

    def test_handle_reaction_approve_thumbsup(self, mock_slack_client):
        """Thumbsup emoji maps to '1'."""
        with patch('slack_listener.send_response') as mock_send:
            mock_send.return_value = "registry_socket"

            from slack_listener import handle_reaction

            body = {
                'event': {
                    'type': 'reaction_added',
                    'user': 'U123',
                    'reaction': '+1',
                    'item': {
                        'channel': 'C123',
                        'ts': '111.222'
                    }
                }
            }

            mock_slack_client.conversations_history.return_value = {
                'ok': True,
                'messages': [{'ts': '111.222'}]
            }

            handle_reaction(body, mock_slack_client)

            mock_send.assert_called_once()
            assert mock_send.call_args[0][0] == "1"

    def test_handle_reaction_approve_remember(self, mock_slack_client):
        """2 emoji maps to '2'."""
        with patch('slack_listener.send_response') as mock_send:
            mock_send.return_value = "registry_socket"

            from slack_listener import handle_reaction

            body = {
                'event': {
                    'type': 'reaction_added',
                    'user': 'U123',
                    'reaction': 'two',
                    'item': {
                        'channel': 'C123',
                        'ts': '111.222'
                    }
                }
            }

            mock_slack_client.conversations_history.return_value = {
                'ok': True,
                'messages': [{'ts': '111.222'}]
            }

            handle_reaction(body, mock_slack_client)

            mock_send.assert_called_once()
            assert mock_send.call_args[0][0] == "2"

    def test_handle_reaction_deny(self, mock_slack_client):
        """3 emoji maps to '3'."""
        with patch('slack_listener.send_response') as mock_send:
            mock_send.return_value = "registry_socket"

            from slack_listener import handle_reaction

            body = {
                'event': {
                    'type': 'reaction_added',
                    'user': 'U123',
                    'reaction': 'three',
                    'item': {
                        'channel': 'C123',
                        'ts': '111.222'
                    }
                }
            }

            mock_slack_client.conversations_history.return_value = {
                'ok': True,
                'messages': [{'ts': '111.222'}]
            }

            handle_reaction(body, mock_slack_client)

            mock_send.assert_called_once()
            assert mock_send.call_args[0][0] == "3"

    def test_handle_reaction_deny_thumbsdown(self, mock_slack_client):
        """Thumbsdown emoji maps to '3'."""
        with patch('slack_listener.send_response') as mock_send:
            mock_send.return_value = "registry_socket"

            from slack_listener import handle_reaction

            body = {
                'event': {
                    'type': 'reaction_added',
                    'user': 'U123',
                    'reaction': '-1',
                    'item': {
                        'channel': 'C123',
                        'ts': '111.222'
                    }
                }
            }

            mock_slack_client.conversations_history.return_value = {
                'ok': True,
                'messages': [{'ts': '111.222'}]
            }

            handle_reaction(body, mock_slack_client)

            mock_send.assert_called_once()
            assert mock_send.call_args[0][0] == "3"

    def test_handle_reaction_unmapped(self, mock_slack_client):
        """Ignores unknown emoji."""
        with patch('slack_listener.send_response') as mock_send:
            from slack_listener import handle_reaction

            body = {
                'event': {
                    'type': 'reaction_added',
                    'user': 'U123',
                    'reaction': 'smile',  # Not mapped
                    'item': {
                        'channel': 'C123',
                        'ts': '111.222'
                    }
                }
            }

            handle_reaction(body, mock_slack_client)

            mock_send.assert_not_called()


class TestHandlePermissionButton:
    """Tests for handle_permission_button."""

    def test_handle_permission_button_approve(self, mock_slack_client):
        """Button click sends response to Claude."""
        with patch('slack_listener.send_response') as mock_send:
            mock_send.return_value = "registry_socket"

            from slack_listener import handle_permission_button

            ack = MagicMock()
            body = {
                'user': {'id': 'U123', 'name': 'testuser'},
                'channel': {'id': 'C123'},
                'message': {'ts': '111.222', 'thread_ts': '100.000'},
                'actions': [
                    {'action_id': 'permission_response_1', 'value': '1', 'style': 'primary'}
                ]
            }

            with patch('slack_listener.get_socket_for_channel', return_value=None):
                handle_permission_button(ack, body, mock_slack_client)

            ack.assert_called_once()
            mock_send.assert_called_once()
            assert mock_send.call_args[0][0] == "1"

    def test_handle_permission_button_deny_prompts_feedback(self, mock_slack_client):
        """Deny button prompts for feedback in thread mode."""
        with patch('slack_listener.send_response') as mock_send:
            from slack_listener import handle_permission_button

            ack = MagicMock()
            body = {
                'user': {'id': 'U123', 'name': 'testuser'},
                'channel': {'id': 'C123'},
                'message': {'ts': '111.222', 'thread_ts': '100.000'},
                'actions': [
                    {'action_id': 'permission_response_3', 'value': '3', 'style': 'danger'}
                ]
            }

            with patch('slack_listener.get_socket_for_channel', return_value=None):
                handle_permission_button(ack, body, mock_slack_client)

            ack.assert_called_once()
            # In thread mode with deny, should update message for feedback
            mock_slack_client.chat_update.assert_called_once()
            # send_response should NOT be called yet (waiting for feedback)
            mock_send.assert_not_called()
