"""ChatGPT Desktop app automation via AppleScript.

Fixes focus stealing, uses clipboard paste, starts new conversations.
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
