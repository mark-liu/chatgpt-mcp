"""Tests for mcp_tools — async sleep, event loop blocking, and generation detection."""
import inspect
from unittest.mock import patch

from chatgpt_mcp import mcp_tools


class TestWaitForResponseAsync:
    """wait_for_response_completion must be async and use asyncio.sleep."""

    def test_wait_for_response_completion_is_coroutine(self):
        """wait_for_response_completion must be an async function."""
        assert inspect.iscoroutinefunction(mcp_tools.wait_for_response_completion), (
            "wait_for_response_completion should be async (uses asyncio.sleep, not time.sleep)"
        )

    def test_no_time_sleep_in_source(self):
        """The function body must not call time.sleep (blocks the event loop)."""
        source = inspect.getsource(mcp_tools.wait_for_response_completion)
        assert "time.sleep" not in source, (
            "wait_for_response_completion must use asyncio.sleep, not time.sleep"
        )

    def test_get_chatgpt_response_awaits_wait(self):
        """get_chatgpt_response must await wait_for_response_completion."""
        source = inspect.getsource(mcp_tools.get_chatgpt_response)
        assert "await" in source and "wait_for_response_completion" in source, (
            "get_chatgpt_response must await wait_for_response_completion"
        )


class TestScreenState:
    """get_screen_state returns (text, is_complete, is_generating)."""

    @patch("chatgpt_mcp.mcp_tools._read_screen")
    def test_generating_state(self, mock_read):
        """isGenerating=True should be reflected in get_screen_state."""
        mock_read.return_value = {
            "status": "success",
            "texts": ["Hello", "Thinking about your question..."],
            "indicators": {"conversationComplete": False, "isGenerating": True},
        }
        text, complete, generating = mcp_tools.get_screen_state()
        assert generating is True
        assert complete is False
        assert "Thinking about your question" in text

    @patch("chatgpt_mcp.mcp_tools._read_screen")
    def test_complete_state(self, mock_read):
        """conversationComplete=True should be reflected."""
        mock_read.return_value = {
            "status": "success",
            "texts": ["Hello", "Here is my answer."],
            "indicators": {"conversationComplete": True, "isGenerating": False},
        }
        text, complete, generating = mcp_tools.get_screen_state()
        assert complete is True
        assert generating is False
        assert "Here is my answer" in text

    @patch("chatgpt_mcp.mcp_tools._read_screen")
    def test_error_state(self, mock_read):
        """Screen read errors should return error text and False flags."""
        mock_read.return_value = {
            "status": "error",
            "message": "No ChatGPT window found",
        }
        text, complete, generating = mcp_tools.get_screen_state()
        assert complete is False
        assert generating is False
        assert "Failed to read" in text

    @patch("chatgpt_mcp.mcp_tools._read_screen")
    def test_empty_texts_during_generation(self, mock_read):
        """No text but isGenerating=True (e.g. deep research thinking phase)."""
        mock_read.return_value = {
            "status": "success",
            "texts": [],
            "indicators": {"conversationComplete": False, "isGenerating": True},
        }
        text, complete, generating = mcp_tools.get_screen_state()
        assert generating is True
        assert complete is False


class TestGenerationAwarePolling:
    """wait_for_response_completion must not false-complete during generation."""

    def test_wait_suppresses_stability_during_generation(self):
        """Source must reset stable_count when generating is True."""
        source = inspect.getsource(mcp_tools.wait_for_response_completion)
        assert "generating" in source, (
            "wait_for_response_completion must check isGenerating flag"
        )
        assert "stable_count = 0" in source, (
            "wait_for_response_completion must reset stable_count during generation"
        )
