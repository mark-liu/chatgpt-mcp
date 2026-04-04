"""Tests for mcp_tools — async sleep and event loop blocking."""
import inspect

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
