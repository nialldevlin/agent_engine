"""Tests for token estimation utilities."""

import pytest
from agent_engine.utils.token_utils import (
    estimate_tokens_rough,
    estimate_tokens_messages,
    estimate_prompt_tokens,
    estimate_tokens,
    CHARS_PER_TOKEN,
)


class TestEstimateTokensRough:
    """Tests for estimate_tokens_rough function."""

    def test_empty_string(self):
        """Empty string should return 0 tokens."""
        assert estimate_tokens_rough("") == 0

    def test_single_character(self):
        """Single character should return 1 token (max(1, ...))."""
        assert estimate_tokens_rough("a") == 1

    def test_basic_text(self):
        """Basic text should use chars-per-token heuristic."""
        text = "Hello world"
        expected = len(text) // CHARS_PER_TOKEN
        assert estimate_tokens_rough(text) == expected

    def test_exact_token_boundary(self):
        """Text exactly divisible by CHARS_PER_TOKEN."""
        text = "aaaa"  # 4 chars = 1 token
        assert estimate_tokens_rough(text) == 1

    def test_long_text(self):
        """Long text should scale proportionally."""
        text = "a" * 1000
        expected = 1000 // CHARS_PER_TOKEN
        assert estimate_tokens_rough(text) == expected

    def test_with_spaces_and_punctuation(self):
        """Spaces and punctuation count as characters."""
        text = "Hello, world!"
        expected = len(text) // CHARS_PER_TOKEN
        assert estimate_tokens_rough(text) == expected

    def test_multiline_text(self):
        """Multiline text should count all characters including newlines."""
        text = "Line 1\nLine 2\nLine 3"
        expected = len(text) // CHARS_PER_TOKEN
        assert estimate_tokens_rough(text) == expected


class TestEstimateTokensMessages:
    """Tests for estimate_tokens_messages function."""

    def test_empty_messages_list(self):
        """Empty messages list should return 0."""
        assert estimate_tokens_messages([]) == 0

    def test_none_messages(self):
        """None messages should be treated as empty."""
        assert estimate_tokens_messages(None) == 0

    def test_single_text_message(self):
        """Single message with string content.

        Note: When content is a string, it iterates character-by-character,
        so "Hello" becomes ['H', 'e', 'l', 'l', 'o'] = 5 tokens (1 each).
        """
        messages = [{"role": "user", "content": "Hello"}]
        result = estimate_tokens_messages(messages)
        # 5 for metadata + 5 for each character (1 token each)
        expected = 5 + 5  # 5 chars = 5 tokens (each char > 1 char = 1 token minimum)
        assert result == expected

    def test_multiple_messages(self):
        """Multiple messages should accumulate tokens.

        When content is a string, each character is counted separately.
        """
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = estimate_tokens_messages(messages)
        # First message: 5 (metadata) + 5 (5 characters)
        # Second message: 5 (metadata) + 8 (8 characters including space)
        expected = 5 + 5 + 5 + 8
        assert result == expected

    def test_message_with_dict_text_content(self):
        """Message with dict containing text part."""
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "Hello"}]
            }
        ]
        result = estimate_tokens_messages(messages)
        expected = 5 + estimate_tokens_rough("Hello")
        assert result == expected

    def test_message_with_image(self):
        """Message with image should add 200 tokens."""
        messages = [
            {
                "role": "user",
                "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "..."}}]
            }
        ]
        result = estimate_tokens_messages(messages)
        # 5 for metadata + 200 for image
        assert result == 205

    def test_message_with_mixed_content(self):
        """Message with both text and image."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Look at this"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "..."}}
                ]
            }
        ]
        result = estimate_tokens_messages(messages)
        expected = 5 + estimate_tokens_rough("Look at this") + 200
        assert result == expected

    def test_empty_content_dict(self):
        """Message with dict but missing text key."""
        messages = [
            {"role": "user", "content": [{"type": "text"}]}
        ]
        result = estimate_tokens_messages(messages)
        # 5 for metadata + 0 for empty text
        assert result == 5

    def test_message_with_empty_content(self):
        """Message with empty content."""
        messages = [{"role": "user", "content": ""}]
        result = estimate_tokens_messages(messages)
        # 5 for metadata + 0 for empty string
        assert result == 5

    def test_message_missing_content_key(self):
        """Message without content key should not error."""
        messages = [{"role": "user"}]
        result = estimate_tokens_messages(messages)
        # 5 for metadata + 0 for missing content
        assert result == 5

    def test_large_message_with_multiple_parts(self):
        """Complex message with multiple content parts."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Part 1"},
                    {"type": "text", "text": "Part 2"},
                    {"type": "image", "source": {...}},
                    {"type": "text", "text": "Part 3"},
                ]
            }
        ]
        result = estimate_tokens_messages(messages)
        expected = (
            5 +
            estimate_tokens_rough("Part 1") +
            estimate_tokens_rough("Part 2") +
            200 +
            estimate_tokens_rough("Part 3")
        )
        assert result == expected


class TestEstimatePromptTokens:
    """Tests for estimate_prompt_tokens function."""

    def test_empty_prompt(self):
        """Empty system and messages should still count tools."""
        result = estimate_prompt_tokens("", [])
        assert result == {"system": 0, "messages": 0, "tools": 0}

    def test_system_only(self):
        """System prompt without messages."""
        system = "You are a helpful assistant"
        result = estimate_prompt_tokens(system, [])
        assert result["system"] == estimate_tokens_rough(system)
        assert result["messages"] == 0
        assert result["tools"] == 0

    def test_messages_only(self):
        """Messages without system prompt."""
        messages = [{"role": "user", "content": "Hello"}]
        result = estimate_prompt_tokens("", messages)
        assert result["system"] == 0
        assert result["messages"] == estimate_tokens_messages(messages)
        assert result["tools"] == 0

    def test_with_tools(self):
        """Prompt with tools should multiply by 100."""
        tools = [
            {"name": "tool1", "description": "First tool"},
            {"name": "tool2", "description": "Second tool"},
        ]
        result = estimate_prompt_tokens("", [], tools)
        assert result["tools"] == 200  # 2 tools * 100

    def test_complete_prompt(self):
        """Complete prompt with all components."""
        system = "You are helpful"
        messages = [{"role": "user", "content": "Hello"}]
        tools = [{"name": "tool1"}]

        result = estimate_prompt_tokens(system, messages, tools)

        assert "system" in result
        assert "messages" in result
        assert "tools" in result
        assert result["system"] == estimate_tokens_rough(system)
        assert result["messages"] == estimate_tokens_messages(messages)
        assert result["tools"] == 100

    def test_none_tools(self):
        """None tools should default to 0."""
        result = estimate_prompt_tokens("System", [], None)
        assert result["tools"] == 0

    def test_empty_tools_list(self):
        """Empty tools list should count as 0."""
        result = estimate_prompt_tokens("System", [], [])
        assert result["tools"] == 0

    def test_many_tools(self):
        """Many tools should scale linearly."""
        tools = [{"name": f"tool{i}"} for i in range(10)]
        result = estimate_prompt_tokens("", [], tools)
        assert result["tools"] == 1000  # 10 tools * 100


class TestEstimateTokensAlias:
    """Tests for estimate_tokens alias function."""

    def test_alias_is_equivalent(self):
        """estimate_tokens should be alias for estimate_tokens_rough."""
        text = "test text for tokens"
        assert estimate_tokens(text) == estimate_tokens_rough(text)

    def test_alias_empty_string(self):
        """Alias should handle empty string."""
        assert estimate_tokens("") == 0

    def test_alias_long_text(self):
        """Alias should handle long text."""
        text = "a" * 500
        assert estimate_tokens(text) == estimate_tokens_rough(text)
