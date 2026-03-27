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
        time.sleep(1)

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
        time.sleep(1)

    def send_message_clipboard(self, message: str):
        """Send message via clipboard paste — preserves formatting, instant."""
        # Save current clipboard
        old_clip = _run_osascript(
            "-e", 'the clipboard as text', text=True
        ).stdout

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

        # Restore clipboard
        time.sleep(0.5)
        subprocess.run(
            ["pbcopy"], input=old_clip.encode(),
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
        """Read sidebar conversation list without stealing focus.

        Returns a list of dicts with 'index' (1-based) and 'title'.
        Reads the AX tree passively — no activation, no focus steal.
        """
        script_path = os.path.join(
            os.path.dirname(__file__), "list_conversations.applescript"
        )
        try:
            result = _run_osascript(script_path, text=True)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if data.get("status") == "success":
                    return data.get("conversations", [])
                raise RuntimeError(data.get("message", "Unknown error"))
            raise RuntimeError(result.stderr.strip() or "AppleScript failed")
        except json.JSONDecodeError:
            raise RuntimeError(f"JSON parse error: {result.stdout[:200]}")

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

        # Activate once — clicking requires focus
        self.activate_chatgpt()

        # Click the conversation by its title text in the sidebar.
        # We use AXPress on the parent cell/row that contains the matching
        # static text, or fall back to clicking the static text itself.
        escaped_title = target["title"].replace("\\", "\\\\").replace('"', '\\"')
        script = f'''
        tell application "System Events"
            tell process "ChatGPT"
                set allElements to entire contents of window 1
                repeat with elem in allElements
                    try
                        if class of elem is static text then
                            set txt to value of elem
                            if txt is "{escaped_title}" then
                                -- Try clicking the parent (row/cell) first
                                set parentElem to value of attribute "AXParent" of elem
                                try
                                    click parentElem
                                on error
                                    click elem
                                end try
                                return "ok"
                            end if
                        end if
                    end try
                end repeat
                return "not_found"
            end tell
        end tell
        '''
        result = _run_osascript("-e", script, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Navigation failed: {result.stderr.strip()}")
        if result.stdout.strip() == "not_found":
            raise RuntimeError(
                f"Could not find clickable element for '{target['title']}'"
            )

        time.sleep(1)  # Let the conversation load
        return target["title"]


async def check_chatgpt_access() -> bool:
    """Check if ChatGPT app is installed and running."""
    try:
        result = _run_osascript(
            "-e",
            'tell application "System Events" to return '
            'application process "ChatGPT" exists',
            text=True,
        )
        if result.stdout.strip() != "true":
            try:
                _run_osascript(
                    "-e", 'tell application "ChatGPT" to activate',
                    "-e", "delay 2",
                )
            except (subprocess.CalledProcessError, TimeoutError):
                raise Exception("Could not activate ChatGPT app.")
        return True
    except Exception as e:
        raise Exception(f"Cannot access ChatGPT app: {e}")
