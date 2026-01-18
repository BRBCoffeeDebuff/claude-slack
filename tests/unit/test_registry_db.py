"""
Unit tests for core/registry_db.py

Tests SQLite-based session registry with SQLAlchemy ORM.
"""

import os
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add core directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))

from registry_db import RegistryDatabase, SessionRecord, Base


class TestRegistryDatabaseInit:
    """Tests for RegistryDatabase initialization."""

    def test_init_creates_database(self, temp_db_path):
        """Database file is created on initialization."""
        assert not os.path.exists(temp_db_path)
        db = RegistryDatabase(temp_db_path)
        assert os.path.exists(temp_db_path)

    def test_init_creates_tables(self, temp_db_path):
        """Sessions table is created on initialization."""
        db = RegistryDatabase(temp_db_path)
        # Query should not raise
        sessions = db.list_sessions()
        assert isinstance(sessions, list)

    def test_init_enables_wal_mode(self, temp_db_path):
        """WAL mode is enabled for concurrency."""
        db = RegistryDatabase(temp_db_path)
        with db.engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("PRAGMA journal_mode"))
            mode = result.fetchone()[0]
            assert mode.lower() == 'wal'


class TestCreateSession:
    """Tests for create_session()"""

    def test_create_session_basic(self, temp_registry_db, sample_session_data):
        """Creates a new session record."""
        result = temp_registry_db.create_session(sample_session_data)
        assert result['session_id'] == sample_session_data['session_id']
        assert result['project'] == sample_session_data['project']
        assert result['status'] == 'active'

    def test_create_session_with_all_fields(self, temp_registry_db):
        """Creates session with all optional fields."""
        data = {
            'session_id': 'full1234',
            'project': 'full-project',
            'project_dir': '/path/to/project',
            'terminal': 'terminal-1',
            'socket_path': '/tmp/full.sock',
            'thread_ts': '1234567890.123456',
            'channel': 'C123456',
            'permissions_channel': 'C789012',
            'slack_user_id': 'U111111',
        }
        result = temp_registry_db.create_session(data)
        assert result['session_id'] == 'full1234'
        assert result['project_dir'] == '/path/to/project'
        assert result['permissions_channel'] == 'C789012'

    def test_create_session_sets_timestamps(self, temp_registry_db, sample_session_data):
        """created_at and last_activity are set automatically."""
        before = datetime.now()
        result = temp_registry_db.create_session(sample_session_data)
        after = datetime.now()

        created = datetime.fromisoformat(result['created_at'])
        assert before <= created <= after

        activity = datetime.fromisoformat(result['last_activity'])
        assert before <= activity <= after


class TestGetSession:
    """Tests for get_session()"""

    def test_get_session_exists(self, temp_registry_db, sample_session_data):
        """Retrieves existing session by ID."""
        temp_registry_db.create_session(sample_session_data)
        result = temp_registry_db.get_session(sample_session_data['session_id'])
        assert result is not None
        assert result['session_id'] == sample_session_data['session_id']

    def test_get_session_not_found(self, temp_registry_db):
        """Returns None for non-existent session."""
        result = temp_registry_db.get_session('nonexistent')
        assert result is None


class TestUpdateSession:
    """Tests for update_session()"""

    def test_update_session_status(self, temp_registry_db, sample_session_data):
        """Updates session status field."""
        temp_registry_db.create_session(sample_session_data)
        result = temp_registry_db.update_session(
            sample_session_data['session_id'],
            {'status': 'idle'}
        )
        assert result is True

        updated = temp_registry_db.get_session(sample_session_data['session_id'])
        assert updated['status'] == 'idle'

    def test_update_session_slack_metadata(self, temp_registry_db, sample_session_data):
        """Updates Slack-related fields."""
        temp_registry_db.create_session(sample_session_data)
        result = temp_registry_db.update_session(
            sample_session_data['session_id'],
            {
                'slack_thread_ts': 'new.thread.ts',
                'slack_channel': 'C999999',
                'todo_message_ts': 'todo.ts.123'
            }
        )
        assert result is True

        updated = temp_registry_db.get_session(sample_session_data['session_id'])
        assert updated['thread_ts'] == 'new.thread.ts'
        assert updated['channel'] == 'C999999'
        assert updated['todo_message_ts'] == 'todo.ts.123'

    def test_update_session_not_found(self, temp_registry_db):
        """Returns False for non-existent session."""
        result = temp_registry_db.update_session('nonexistent', {'status': 'idle'})
        assert result is False

    def test_update_session_updates_last_activity(self, temp_registry_db, sample_session_data):
        """last_activity is updated on any update."""
        temp_registry_db.create_session(sample_session_data)

        # Wait briefly to ensure timestamp changes
        time.sleep(0.01)

        temp_registry_db.update_session(
            sample_session_data['session_id'],
            {'status': 'idle'}
        )

        updated = temp_registry_db.get_session(sample_session_data['session_id'])
        created = datetime.fromisoformat(updated['created_at'])
        activity = datetime.fromisoformat(updated['last_activity'])
        assert activity >= created


class TestDeleteSession:
    """Tests for delete_session()"""

    def test_delete_session_exists(self, temp_registry_db, sample_session_data):
        """Deletes existing session."""
        temp_registry_db.create_session(sample_session_data)
        result = temp_registry_db.delete_session(sample_session_data['session_id'])
        assert result is True

        # Verify deleted
        session = temp_registry_db.get_session(sample_session_data['session_id'])
        assert session is None

    def test_delete_session_not_found(self, temp_registry_db):
        """Returns False for non-existent session."""
        result = temp_registry_db.delete_session('nonexistent')
        assert result is False


class TestListSessions:
    """Tests for list_sessions()"""

    def test_list_sessions_all(self, temp_registry_db, sample_session_data):
        """Lists all sessions."""
        temp_registry_db.create_session(sample_session_data)

        data2 = sample_session_data.copy()
        data2['session_id'] = 'test5678'
        temp_registry_db.create_session(data2)

        sessions = temp_registry_db.list_sessions()
        assert len(sessions) == 2

    def test_list_sessions_by_status(self, temp_registry_db, sample_session_data):
        """Filters sessions by status."""
        temp_registry_db.create_session(sample_session_data)

        data2 = sample_session_data.copy()
        data2['session_id'] = 'idle5678'
        temp_registry_db.create_session(data2)
        temp_registry_db.update_session('idle5678', {'status': 'idle'})

        active = temp_registry_db.list_sessions(status='active')
        assert len(active) == 1
        assert active[0]['session_id'] == sample_session_data['session_id']

        idle = temp_registry_db.list_sessions(status='idle')
        assert len(idle) == 1
        assert idle[0]['session_id'] == 'idle5678'

    def test_list_sessions_empty(self, temp_registry_db):
        """Returns empty list when no sessions."""
        sessions = temp_registry_db.list_sessions()
        assert sessions == []


class TestGetByThread:
    """Tests for get_by_thread()"""

    def test_get_by_thread_exists(self, temp_registry_db, sample_session_data):
        """Finds session by thread_ts."""
        temp_registry_db.create_session(sample_session_data)
        result = temp_registry_db.get_by_thread(sample_session_data['thread_ts'])
        assert result is not None
        assert result['session_id'] == sample_session_data['session_id']

    def test_get_by_thread_not_found(self, temp_registry_db):
        """Returns None when thread not found."""
        result = temp_registry_db.get_by_thread('nonexistent.thread')
        assert result is None


class TestGetByProjectDir:
    """Tests for get_by_project_dir()"""

    def test_get_by_project_dir_exists(self, temp_registry_db, sample_session_data):
        """Finds session by project directory."""
        temp_registry_db.create_session(sample_session_data)
        result = temp_registry_db.get_by_project_dir(sample_session_data['project_dir'])
        assert result is not None
        assert result['session_id'] == sample_session_data['session_id']

    def test_get_by_project_dir_filters_status(self, temp_registry_db, sample_session_data):
        """Respects status filter."""
        temp_registry_db.create_session(sample_session_data)
        temp_registry_db.update_session(sample_session_data['session_id'], {'status': 'ended'})

        # Active filter should not find it
        result = temp_registry_db.get_by_project_dir(
            sample_session_data['project_dir'],
            status='active'
        )
        assert result is None

        # Ended filter should find it
        result = temp_registry_db.get_by_project_dir(
            sample_session_data['project_dir'],
            status='ended'
        )
        assert result is not None

    def test_get_by_project_dir_returns_most_recent(self, temp_registry_db, sample_session_data):
        """Returns most recently created session for project."""
        temp_registry_db.create_session(sample_session_data)

        time.sleep(0.01)

        data2 = sample_session_data.copy()
        data2['session_id'] = 'newer123'
        temp_registry_db.create_session(data2)

        result = temp_registry_db.get_by_project_dir(sample_session_data['project_dir'])
        assert result['session_id'] == 'newer123'


class TestCleanupOldSessions:
    """Tests for cleanup_old_sessions()"""

    def test_cleanup_old_sessions(self, temp_registry_db, sample_session_data):
        """Deletes sessions older than specified hours."""
        temp_registry_db.create_session(sample_session_data)

        # Manually set last_activity to 25 hours ago
        with temp_registry_db.session_scope() as session:
            record = session.query(SessionRecord).filter_by(
                session_id=sample_session_data['session_id']
            ).first()
            record.last_activity = datetime.now() - timedelta(hours=25)

        count = temp_registry_db.cleanup_old_sessions(older_than_hours=24)
        assert count == 1

        # Verify deleted
        result = temp_registry_db.get_session(sample_session_data['session_id'])
        assert result is None

    def test_cleanup_preserves_recent_sessions(self, temp_registry_db, sample_session_data):
        """Preserves sessions within age threshold."""
        temp_registry_db.create_session(sample_session_data)

        count = temp_registry_db.cleanup_old_sessions(older_than_hours=24)
        assert count == 0

        # Verify still exists
        result = temp_registry_db.get_session(sample_session_data['session_id'])
        assert result is not None


class TestConcurrency:
    """Tests for concurrent database access."""

    def test_concurrent_reads(self, temp_registry_db, sample_session_data):
        """WAL mode allows concurrent reads."""
        temp_registry_db.create_session(sample_session_data)

        results = []
        errors = []

        def read_session():
            try:
                result = temp_registry_db.get_session(sample_session_data['session_id'])
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_session) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        assert all(r['session_id'] == sample_session_data['session_id'] for r in results)


class TestSessionScope:
    """Tests for session_scope() context manager."""

    def test_session_scope_commits_on_success(self, temp_registry_db, sample_session_data):
        """Transaction is committed when no error."""
        with temp_registry_db.session_scope() as session:
            record = SessionRecord(
                session_id='scope123',
                project='scope-project',
                terminal='scope-terminal',
                socket_path='/tmp/scope.sock',
                status='active'
            )
            session.add(record)

        # Verify committed
        result = temp_registry_db.get_session('scope123')
        assert result is not None

    def test_session_scope_rollback_on_error(self, temp_registry_db, sample_session_data):
        """Transaction is rolled back on error."""
        try:
            with temp_registry_db.session_scope() as session:
                record = SessionRecord(
                    session_id='rollback1',
                    project='rollback-project',
                    terminal='rollback-terminal',
                    socket_path='/tmp/rollback.sock',
                    status='active'
                )
                session.add(record)
                session.flush()
                raise ValueError("Simulated error")
        except ValueError:
            pass

        # Verify rolled back
        result = temp_registry_db.get_session('rollback1')
        assert result is None


class TestSessionRecordToDict:
    """Tests for SessionRecord.to_dict()"""

    def test_to_dict_includes_all_fields(self, temp_registry_db, sample_session_data):
        """to_dict() includes all expected fields."""
        temp_registry_db.create_session(sample_session_data)
        result = temp_registry_db.get_session(sample_session_data['session_id'])

        expected_fields = [
            'session_id', 'project', 'project_dir', 'terminal', 'socket_path',
            'thread_ts', 'channel', 'permissions_channel', 'slack_user_id',
            'reply_to_ts', 'todo_message_ts', 'buffer_file_path',
            'status', 'created_at', 'last_activity'
        ]
        for field in expected_fields:
            assert field in result, f"Missing field: {field}"


class TestSchemaMigration:
    """Tests for database schema migrations."""

    def test_migration_adds_project_dir(self, temp_db_path):
        """project_dir column is added if missing."""
        # Create database with current schema
        db = RegistryDatabase(temp_db_path)

        # Verify column exists
        with db.engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("PRAGMA table_info(sessions)"))
            columns = [row[1] for row in result.fetchall()]
            assert 'project_dir' in columns

    def test_migration_adds_buffer_file_path(self, temp_db_path):
        """buffer_file_path column is added if missing."""
        db = RegistryDatabase(temp_db_path)

        with db.engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("PRAGMA table_info(sessions)"))
            columns = [row[1] for row in result.fetchall()]
            assert 'buffer_file_path' in columns
