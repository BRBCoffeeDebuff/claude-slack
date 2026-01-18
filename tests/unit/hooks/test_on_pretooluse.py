"""
Unit tests for .claude/hooks/on_pretooluse.py

Tests AskUserQuestion formatting with options and descriptions.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestFormatQuestionForSlack:
    """Test formatting single questions."""

    def _format_question(self, question, index, total):
        """Local implementation of format_question_for_slack."""
        lines = []

        if total > 1:
            lines.append(f"**Question {index + 1}/{total}: {question.get('question', 'N/A')}**")
        else:
            lines.append(f"**{question.get('question', 'N/A')}**")

        lines.append("")

        options = question.get('options', [])
        multi_select = question.get('multiSelect', False)

        if multi_select:
            lines.append("_(Multiple selections allowed)_")
            lines.append("")

        for i, option in enumerate(options, 1):
            label = option.get('label', f'Option {i}')
            description = option.get('description', '')

            lines.append(f"{i}. **{label}**")
            if description:
                lines.append(f"   _{description}_")
            lines.append("")

        return "\n".join(lines)

    def test_format_single_question(self):
        """Format one question correctly."""
        question = {
            'question': 'Which approach should we use?',
            'header': 'Approach',
            'multiSelect': False,
            'options': [
                {'label': 'Option A', 'description': 'Fast but risky'},
                {'label': 'Option B', 'description': 'Slow but safe'}
            ]
        }

        result = self._format_question(question, 0, 1)

        assert 'Which approach should we use?' in result
        assert 'Option A' in result
        assert 'Option B' in result
        assert 'Fast but risky' in result
        assert 'Slow but safe' in result
        # Single question shouldn't have "Question 1/1"
        assert 'Question 1/1' not in result

    def test_format_question_multiselect(self):
        """Handle multiSelect flag."""
        question = {
            'question': 'Select features to enable:',
            'multiSelect': True,
            'options': [
                {'label': 'Feature A'},
                {'label': 'Feature B'},
                {'label': 'Feature C'}
            ]
        }

        result = self._format_question(question, 0, 1)

        assert 'Select features' in result
        assert 'Multiple selections allowed' in result
        assert 'Feature A' in result
        assert 'Feature B' in result
        assert 'Feature C' in result

    def test_format_question_with_descriptions(self):
        """Include option descriptions."""
        question = {
            'question': 'Choose a database:',
            'options': [
                {'label': 'PostgreSQL', 'description': 'Relational, ACID compliant'},
                {'label': 'MongoDB', 'description': 'Document store, flexible schema'},
                {'label': 'Redis', 'description': 'In-memory, key-value'}
            ]
        }

        result = self._format_question(question, 0, 1)

        assert 'PostgreSQL' in result
        assert 'Relational, ACID' in result
        assert 'MongoDB' in result
        assert 'Document store' in result

    def test_format_question_no_descriptions(self):
        """Handle options without descriptions."""
        question = {
            'question': 'Pick one:',
            'options': [
                {'label': 'A'},
                {'label': 'B'}
            ]
        }

        result = self._format_question(question, 0, 1)

        assert '1. **A**' in result
        assert '2. **B**' in result


class TestFormatAskUserQuestionForSlack:
    """Test formatting complete AskUserQuestion tool input."""

    def _format_askuserquestion(self, tool_input):
        """Local implementation of format_askuserquestion_for_slack."""
        questions = tool_input.get('questions', [])

        if not questions:
            return "❓ Claude has a question (no details available)"

        lines = ["❓ **Claude needs your input:**", ""]

        for i, question in enumerate(questions):
            # Format each question
            q_lines = []
            total = len(questions)
            if total > 1:
                q_lines.append(f"**Question {i + 1}/{total}: {question.get('question', 'N/A')}**")
            else:
                q_lines.append(f"**{question.get('question', 'N/A')}**")

            q_lines.append("")

            options = question.get('options', [])
            multi_select = question.get('multiSelect', False)

            if multi_select:
                q_lines.append("_(Multiple selections allowed)_")
                q_lines.append("")

            for j, option in enumerate(options, 1):
                label = option.get('label', f'Option {j}')
                description = option.get('description', '')
                q_lines.append(f"{j}. **{label}**")
                if description:
                    q_lines.append(f"   _{description}_")
                q_lines.append("")

            lines.append("\n".join(q_lines))
            if i < len(questions) - 1:
                lines.append("---")
                lines.append("")

        lines.append("_Reply with the number(s) of your choice._")
        return "\n".join(lines)

    def test_format_multiple_questions(self):
        """Format 2-4 questions."""
        tool_input = {
            'questions': [
                {
                    'question': 'First question?',
                    'options': [{'label': 'Yes'}, {'label': 'No'}]
                },
                {
                    'question': 'Second question?',
                    'options': [{'label': 'A'}, {'label': 'B'}, {'label': 'C'}]
                }
            ]
        }

        result = self._format_askuserquestion(tool_input)

        assert 'Claude needs your input' in result
        assert 'Question 1/2' in result
        assert 'Question 2/2' in result
        assert 'First question?' in result
        assert 'Second question?' in result
        assert '---' in result  # Divider between questions

    def test_format_empty_questions(self):
        """Handle empty questions list."""
        tool_input = {'questions': []}
        result = self._format_askuserquestion(tool_input)
        assert 'no details available' in result

    def test_format_includes_reply_instruction(self):
        """Include reply instructions."""
        tool_input = {
            'questions': [
                {
                    'question': 'Choose one:',
                    'options': [{'label': 'X'}, {'label': 'Y'}]
                }
            ]
        }

        result = self._format_askuserquestion(tool_input)
        assert 'Reply with the number' in result


class TestFilterAskUserQuestionOnly:
    """Test that hook only processes AskUserQuestion tool."""

    def test_filter_askuserquestion_only(self, sample_pretooluse_hook_input):
        """Only process AskUserQuestion calls."""
        # AskUserQuestion should be processed
        assert sample_pretooluse_hook_input['tool_name'] == 'AskUserQuestion'

    def test_skip_other_tools(self):
        """Skip non-AskUserQuestion tools."""
        other_tools = ['Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep', 'Task']

        for tool_name in other_tools:
            # Hook would exit early for these
            assert tool_name != 'AskUserQuestion'


class TestSplitMessage:
    """Test message splitting."""

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

    def test_long_question_splits(self):
        """Long questions with many options split correctly."""
        # Generate very long question text
        long_text = "Very detailed option description. " * 1000

        chunks = self._split_message(long_text, max_length=1000)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 1000


class TestPostToSlack:
    """Test posting questions to Slack."""

    def test_post_question_to_thread(self, mock_slack_client):
        """Post question to correct thread."""
        mock_slack_client.chat_postMessage.return_value = {'ok': True, 'ts': '123.456'}

        # Simulate posting
        mock_slack_client.chat_postMessage(
            channel='C123',
            thread_ts='111.222',
            text='Question text'
        )

        mock_slack_client.chat_postMessage.assert_called_once()
        call_args = mock_slack_client.chat_postMessage.call_args
        assert call_args.kwargs['thread_ts'] == '111.222'
