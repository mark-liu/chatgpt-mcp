"""MCP tools for ChatGPT Desktop automation.

No focus stealing on reads, new conversation per ask,
clipboard paste for formatting, configurable poll interval.
Conversation management: list, navigate, read old chats.
"""
import asyncio
import time
from mcp.server.fastmcp import FastMCP
from chatgpt_mcp.chatgpt_automation import ChatGPTAutomation, check_chatgpt_access

# Poll intervals for quick vs deep modes
QUICK_POLL_INTERVAL = 5
QUICK_MAX_WAIT = 60
DEEP_POLL_INTERVAL = 120
DEEP_MAX_WAIT = 3600

# Text stability: consider complete after N consecutive identical reads
TEXT_STABILITY_THRESHOLD = 3

# Grace period after sending before polling — lets GPT transition from
# idle state (model+voice buttons visible) to generating state (Stop
# button visible). Without this, the first poll sees the old completion
# indicators and returns immediately with just the prompt.
POST_SEND_GRACE_SECONDS = 5

# How long to wait for generation to begin after sending (seconds).
# If neither isGenerating nor text-changed within this window, fall
# through to normal polling (handles edge case where GPT responds
# instantly for cached/short answers).
GENERATION_START_TIMEOUT = 30


def _read_screen() -> dict:
    """Read screen and return raw parsed data (no focus steal)."""
    try:
        automation = ChatGPTAutomation()
        return automation.read_screen_content()
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _extract_text(screen_data: dict) -> str:
    """Extract and clean conversation text from screen data."""
    texts = screen_data.get("texts", [])
    current_content = "\n".join(texts)
    cleaned = current_content.strip()
    cleaned = (
        cleaned.replace("Regenerate", "")
        .replace("Continue generating", "")
        .replace("\u258d", "")
        .strip()
    )
    return cleaned


def is_conversation_complete() -> bool:
    """Check if ChatGPT conversation is complete (no focus steal)."""
    screen_data = _read_screen()
    if screen_data.get("status") == "success":
        indicators = screen_data.get("indicators", {})
        return indicators.get("conversationComplete", False)
    return False


def is_generating() -> bool:
    """Check if ChatGPT is actively generating (Stop button or thinking text)."""
    screen_data = _read_screen()
    if screen_data.get("status") == "success":
        indicators = screen_data.get("indicators", {})
        return indicators.get("isGenerating", False)
    return False


def get_screen_state() -> tuple[str, bool, bool]:
    """Get text, completion status, and generation status in one read.

    Returns:
        (text, is_complete, is_generating)
    """
    screen_data = _read_screen()
    if screen_data.get("status") != "success":
        return (f"Failed to read ChatGPT screen: {screen_data.get('message', 'unknown')}", False, False)
    indicators = screen_data.get("indicators", {})
    text = _extract_text(screen_data) or "No response received from ChatGPT."
    complete = indicators.get("conversationComplete", False)
    generating = indicators.get("isGenerating", False)
    return (text, complete, generating)


def get_current_conversation_text() -> str:
    """Get the current conversation text from ChatGPT (no focus steal)."""
    text, _, _ = get_screen_state()
    return text


async def wait_for_response_completion(max_wait_time: int = DEEP_MAX_WAIT,
                                       check_interval: float = DEEP_POLL_INTERVAL,
                                       sent_text: str = "") -> bool:
    """Wait for ChatGPT response to complete.

    Two-phase approach:
      Phase 1 — Wait for generation to START (avoids returning stale
                completion state from before the message was sent).
      Phase 2 — Wait for generation to FINISH.

    Phase 2 uses three signals:
    1. Button heuristic — AppleScript detects model/voice button sequence
    2. Generation detection — Stop button or "Thinking" text means still working
    3. Text stability — if text is identical for N consecutive reads AND not
       generating, consider it complete (catches button heuristic misses)

    Text stability is suppressed while isGenerating is True, preventing
    false completions during deep research / o1 thinking phases.

    No focus stealing during the wait — reads screen content passively.

    Args:
        sent_text: The prompt that was just sent. Used to detect when the
                   response has actually appeared (text differs from prompt).
    """
    start_time = time.time()

    # -- Phase 1: wait for generation to begin --
    # After sending, old UI state may linger (conversationComplete=True,
    # isGenerating=False) for a moment. We wait until either:
    #   a) isGenerating becomes True, or
    #   b) screen text changes from what we sent (GPT responded instantly)
    # with a hard timeout so we don't block forever on edge cases.
    generation_started = False
    phase1_deadline = start_time + GENERATION_START_TIMEOUT

    while time.time() < phase1_deadline:
        text, complete, generating = get_screen_state()

        if generating:
            generation_started = True
            break

        # Text changed meaningfully — GPT responded (possibly instantly)
        if sent_text and text and _text_differs(text, sent_text):
            generation_started = True
            break

        await asyncio.sleep(2)  # fast poll during phase 1

    # -- Phase 2: wait for generation to finish --
    last_text = ""
    stable_count = 0

    while time.time() - start_time < max_wait_time:
        text, complete, generating = get_screen_state()

        # Signal 1: button heuristic says done — but ONLY trust it if
        # generation already started (or phase 1 timed out).
        if complete and generation_started:
            # Extra guard: make sure we have more than just the prompt
            if not sent_text or _text_differs(text, sent_text):
                return True

        # Signal 2: if actively generating, reset stability counter
        if generating:
            generation_started = True  # confirm generation seen
            stable_count = 0
            last_text = text
            await asyncio.sleep(check_interval)
            continue

        # Signal 3: text stability fallback (only when NOT generating)
        # Only triggers after generation has started or phase 1 timed out
        if generation_started or time.time() > phase1_deadline:
            if text and text == last_text:
                stable_count += 1
                if stable_count >= TEXT_STABILITY_THRESHOLD:
                    return True
            else:
                stable_count = 0
                last_text = text

        await asyncio.sleep(check_interval)
    return False


def _text_differs(current: str, sent: str) -> bool:
    """Check if current screen text meaningfully differs from the sent prompt.

    Simple heuristic: if current text is substantially longer than the sent
    prompt, or doesn't start with the sent text, something new appeared.
    """
    sent_stripped = sent.strip()[:200]  # compare first 200 chars only
    current_stripped = current.strip()

    # Much longer → response appeared
    if len(current_stripped) > len(sent_stripped) + 100:
        return True

    # Doesn't even contain the sent text → UI refreshed
    if sent_stripped and sent_stripped[:80] not in current_stripped:
        return True

    return False


async def get_chatgpt_response(quick: bool = False, sent_text: str = "") -> str:
    """Get the latest response from ChatGPT after sending a message.

    Args:
        sent_text: The prompt that was sent. Passed to polling so it can
                   distinguish "GPT hasn't started yet" from "GPT is done".
    """
    if quick:
        max_wait, interval = QUICK_MAX_WAIT, QUICK_POLL_INTERVAL
    else:
        max_wait, interval = DEEP_MAX_WAIT, DEEP_POLL_INTERVAL

    try:
        if await wait_for_response_completion(max_wait_time=max_wait,
                                              check_interval=interval,
                                              sent_text=sent_text):
            return get_current_conversation_text()
        return "Timeout: ChatGPT response did not complete within the time limit."
    except Exception as e:
        raise Exception(f"Failed to get response from ChatGPT: {e}")


async def ask_chatgpt(prompt: str, quick: bool = False,
                      conversation: str | None = None) -> str:
    """Send a prompt to ChatGPT and return the response.

    Args:
        prompt: The message to send.
        quick: If True, use short poll interval (5s) and short timeout (60s).
               Default False uses deep mode (900s poll, 3600s timeout).
        conversation: Optional conversation title to continue. If provided,
                      navigates to the matching sidebar conversation instead
                      of opening a new one.
    """
    await check_chatgpt_access()

    try:
        automation = ChatGPTAutomation()

        if conversation:
            # Navigate to existing conversation (activates once internally)
            automation.navigate_to_conversation(title=conversation)
        else:
            # Activate once, open new chat
            automation.activate_chatgpt()
            automation.new_conversation()

        automation.send_message_clipboard(prompt)

        # Grace period: let UI transition from idle → generating.
        # Without this, the first poll sees stale completion indicators.
        await asyncio.sleep(POST_SEND_GRACE_SECONDS)

        # Wait for response (passive — no focus steal)
        return await get_chatgpt_response(quick=quick, sent_text=prompt)

    except Exception as e:
        raise Exception(f"Failed to send message to ChatGPT: {e}")


def setup_mcp_tools(mcp: FastMCP):
    """Register MCP tools."""

    @mcp.tool()
    async def ask_chatgpt_tool(prompt: str, quick: bool = False,
                               conversation: str = "") -> str:
        """Send a prompt to ChatGPT and return the response.

        Args:
            prompt: The message to send to ChatGPT.
            quick: If True, poll every 5s with 60s timeout (for fast queries).
                   If False (default), poll every 15min with 1h timeout (for
                   deep research, o1, etc).
            conversation: Optional conversation title to continue. If provided,
                          navigates to the matching sidebar conversation instead
                          of starting a new one. Substring match, case-insensitive.
        """
        conv = conversation if conversation else None
        return await ask_chatgpt(prompt, quick=quick, conversation=conv)

    @mcp.tool()
    async def get_chatgpt_response_tool() -> str:
        """Get the current conversation text from ChatGPT immediately.

        Returns whatever is on screen right now — no polling, no waiting.
        Prefixes status so callers know the state:
          [GENERATING] — Stop button or thinking text detected
          [COMPLETE]   — model+voice buttons detected (idle/done)
          [UNKNOWN]    — neither signal detected (may still be loading)
        Use ask_chatgpt_tool if you need to send a message and wait for a response.
        """
        await check_chatgpt_access()
        text, complete, generating = get_screen_state()
        if generating:
            return f"[GENERATING] ChatGPT is still working. Check back later.\n\nPartial content so far:\n{text}"
        if complete:
            return f"[COMPLETE]\n{text}"
        # Neither generating nor complete — could be transitioning or
        # the button heuristic missed. Flag as unknown.
        return f"[UNKNOWN] Could not determine if ChatGPT is done or still working.\n\n{text}"

    @mcp.tool()
    async def list_conversations_tool() -> str:
        """List conversations from the ChatGPT sidebar.

        Reads the sidebar without stealing focus. Returns a JSON list of
        conversations with index (1-based) and title.
        """
        await check_chatgpt_access()
        try:
            automation = ChatGPTAutomation()
            conversations = automation.list_conversations()
            if not conversations:
                return "No conversations found in sidebar."
            lines = [f"{c['index']}. {c['title']}" for c in conversations]
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing conversations: {e}"

    @mcp.tool()
    async def read_conversation_tool(conversation: str) -> str:
        """Navigate to a named conversation and read its content.

        Args:
            conversation: Title to match (substring, case-insensitive).
        """
        await check_chatgpt_access()
        try:
            automation = ChatGPTAutomation()
            matched_title = automation.navigate_to_conversation(title=conversation)
            # Give the conversation time to fully render
            time.sleep(2)
            text = get_current_conversation_text()
            if not text or text == "No response received from ChatGPT.":
                return f"Navigated to '{matched_title}' but no content found."
            return f"=== {matched_title} ===\n\n{text}"
        except Exception as e:
            return f"Error reading conversation: {e}"
