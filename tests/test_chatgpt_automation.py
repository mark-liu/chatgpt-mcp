"""Tests for chatgpt_automation — AppleScript injection prevention."""
from unittest.mock import patch, MagicMock
import subprocess

from chatgpt_mcp.chatgpt_automation import ChatGPTAutomation


class TestNavigateAppleScriptInjection:
    """Verify conversation titles are passed as argv, not interpolated."""

    def _make_automation_with_conversations(self, conversations):
        """Helper: return an automation instance whose list_conversations is mocked."""
        auto = ChatGPTAutomation()
        auto.list_conversations = MagicMock(return_value=conversations)
        return auto

    @patch("chatgpt_mcp.chatgpt_automation._run_osascript")
    def test_malicious_title_not_interpolated(self, mock_osascript):
        """A title containing AppleScript injection must be passed as a
        subprocess argument, never interpolated into the script body."""
        mock_osascript.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )

        malicious = '" & do shell script "whoami'
        auto = self._make_automation_with_conversations(
            [{"index": 1, "title": malicious}]
        )
        auto.navigate_to_conversation(title="whoami")

        # The osascript call must use stdin (input=) with "-" as the script
        # source, and pass the title as a positional argument — NOT via -e
        # with the title baked in.
        call_args = mock_osascript.call_args
        assert call_args is not None, "osascript was never called"

        positional = call_args[0][0] if call_args[0] else call_args[1].get("args", [])
        # Should be called like: osascript("-", title, input=script_bytes)
        # Our helper wraps subprocess.run so we check for "-" flag and the
        # title appearing as a separate argument, not inside -e string.

        # After the fix, _run_osascript is called with positional args only
        # (no -e flag) and the title is passed as a separate argv element.
        args_tuple = call_args[0]  # positional args to _run_osascript
        assert "-e" not in args_tuple, (
            "Title must not be passed via -e (string interpolation); "
            "use stdin + argv instead"
        )
        assert malicious in args_tuple, (
            "Malicious title must appear as a separate positional argument, "
            f"but args were: {args_tuple}"
        )

    @patch("chatgpt_mcp.chatgpt_automation._run_osascript")
    def test_title_with_newlines_safe(self, mock_osascript):
        """Titles with CR/LF must not break the AppleScript."""
        mock_osascript.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )
        title_with_newlines = "line1\nline2\rline3"
        auto = self._make_automation_with_conversations(
            [{"index": 1, "title": title_with_newlines}]
        )
        auto.navigate_to_conversation(index=1)

        call_args = mock_osascript.call_args
        assert call_args is not None
        args_tuple = call_args[0]
        assert "-e" not in args_tuple
        assert title_with_newlines in args_tuple
