"""ChatGPT Desktop app automation via AppleScript.

Fixes focus stealing, uses clipboard paste, starts new conversations.
Conversation management: list, navigate, read old chats.
"""
import subprocess
import time
import json
import os

# Timeout for all AppleScript subprocess calls (seconds)
APPLESCRIPT_TIMEOUT = 30


def _run_osascript(*args: str, **kwargs) -> subprocess.CompletedProcess:
    """Run osascript with a timeout. Raises on timeout."""
    try:
        return subprocess.run(
            ["osascript", *args],
            capture_output=True,
            timeout=APPLESCRIPT_TIMEOUT,
            **kwargs,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(
            f"AppleScript timed out after {APPLESCRIPT_TIMEOUT}s"
        )


class ChatGPTAutomation:
    def __init__(self):
        self.applescript_path = os.path.join(
            os.path.dirname(__file__), "read_chatgpt_screen.applescript"
        )

    def activate_chatgpt(self):
        """Bring ChatGPT to front (only called once at send time, not on reads)."""
        _run_osascript("-e", 'tell application "ChatGPT" to activate')
        time.sleep(0.5)

    def new_conversation(self):
        """Start a new conversation via Cmd+N."""
        script = '''
        tell application "System Events"
            tell process "ChatGPT"
                keystroke "n" using command down
            end tell
        end tell
        '''
        _run_osascript("-e", script)
        time.sleep(0.5)

    def send_message_clipboard(self, message: str):
        """Send message via clipboard paste — preserves formatting, instant."""
        # Save current clipboard as raw bytes (preserves images, rich text)
        old_clip = subprocess.run(
            ["pbpaste"], capture_output=True, timeout=APPLESCRIPT_TIMEOUT,
        ).stdout  # bytes

        # Set clipboard to message
        subprocess.run(
            ["pbcopy"], input=message.encode(),
            capture_output=True, timeout=APPLESCRIPT_TIMEOUT,
        )
        time.sleep(0.2)

        # Paste and send
        script = '''
        tell application "System Events"
            tell process "ChatGPT"
                keystroke "v" using command down
                delay 0.3
                key code 36
            end tell
        end tell
        '''
        _run_osascript("-e", script)

        # Restore clipboard (raw bytes)
        time.sleep(0.5)
        subprocess.run(
            ["pbcopy"], input=old_clip,
            capture_output=True, timeout=APPLESCRIPT_TIMEOUT,
        )

    def read_screen_content(self) -> dict:
        """Read ChatGPT screen WITHOUT stealing focus."""
        try:
            result = _run_osascript(self.applescript_path, text=True)
            if result.returncode == 0:
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    return {"status": "error", "message": "JSON parse error",
                            "raw": result.stdout}
            else:
                return {"status": "error", "message": result.stderr}
        except TimeoutError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def list_conversations(self) -> list[dict]:
        """List conversations via the Chats menu bar.

        No focus steal — reads menu bar items without activating.
        Returns a list of dicts with 'index' (1-based) and 'title'.
        """
        script = (
            'tell application "System Events"\n'
            '  tell process "ChatGPT"\n'
            '    set output to ""\n'
            '    set chatMenu to menu 1 of menu bar item "Chats" of menu bar 1\n'
            '    set chatItems to every menu item of chatMenu\n'
            '    repeat with ci in chatItems\n'
            '      set ciTitle to ""\n'
            '      try\n'
            '        set ciTitle to title of ci as text\n'
            '      end try\n'
            '      if ciTitle is not "" and ciTitle is not "missing value" then\n'
            '        if output is not "" then set output to output & linefeed\n'
            '        set output to output & ciTitle\n'
            '      end if\n'
            '    end repeat\n'
            '    return output\n'
            '  end tell\n'
            'end tell\n'
        )
        try:
            result = _run_osascript("-e", script, text=True)
            if result.returncode != 0 or not result.stdout.strip():
                return []
            conversations = []
            for idx, line in enumerate(result.stdout.strip().split("\n"), 1):
                title = line.strip()
                if title:
                    conversations.append({"index": idx, "title": title})
            return conversations
        except TimeoutError:
            return []

    def navigate_to_conversation(
        self, *, title: str | None = None, index: int | None = None
    ) -> str:
        """Click on a conversation in the sidebar by title or 1-based index.

        Activates ChatGPT once (clicking requires focus), then clicks the
        matching sidebar element.  Returns the title of the conversation
        that was navigated to.

        Args:
            title: Substring match against conversation titles (case-insensitive).
            index: 1-based index from list_conversations().

        Raises:
            ValueError: If neither title nor index is provided, or not found.
        """
        if title is None and index is None:
            raise ValueError("Provide either title or index")

        conversations = self.list_conversations()
        if not conversations:
            raise RuntimeError("No conversations found in sidebar")

        target: dict | None = None
        if index is not None:
            for conv in conversations:
                if conv["index"] == index:
                    target = conv
                    break
            if target is None:
                raise ValueError(
                    f"Index {index} not found (have {len(conversations)} conversations)"
                )
        else:
            # Case-insensitive substring match
            needle = title.lower()
            for conv in conversations:
                if needle in conv["title"].lower():
                    target = conv
                    break
            if target is None:
                raise ValueError(
                    f"No conversation matching '{title}' found"
                )

        # Navigate via Chats menu — no AX tree search needed
        escaped_title = target["title"].replace("\\", "\\\\").replace('"', '\\"')
        script = f'''
tell application "System Events"
    tell process "ChatGPT"
        click menu item "{escaped_title}" of menu 1 of menu bar item "Chats" of menu bar 1
    end tell
end tell
'''
        result = _run_osascript("-e", script, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Navigation failed: {result.stderr.strip()}")

        time.sleep(1)  # Let the conversation load
        return target["title"]


async def check_chatgpt_access() -> bool:
    """Check if ChatGPT app is running — never activate it."""
    result = _run_osascript(
        "-e",
        'tell application "System Events" to return '
        'application process "ChatGPT" exists',
        text=True,
    )
    if result.stdout.strip() != "true":
        raise Exception("ChatGPT app is not running. Open it first.")
    # Check window exists
    result2 = _run_osascript(
        "-e",
        'tell application "System Events" to tell process "ChatGPT" '
        'to return count of windows',
        text=True,
    )
    if result2.stdout.strip() == "0":
        raise Exception("ChatGPT has no visible window. Open the app window.")
    return True
