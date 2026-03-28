# chatgpt-mcp

MCP server that automates the ChatGPT macOS desktop app. Access ChatGPT Pro features (o1, deep research, GPTs) from Claude Code or any MCP client — no API keys needed.

Forked from [xncbf/chatgpt-mcp](https://github.com/xncbf/chatgpt-mcp) with significant fixes.

## Why

ChatGPT Pro has models and features (o1 pro, deep research, custom GPTs) that aren't available via API. This server bridges the gap by automating the desktop app through AppleScript and the macOS accessibility tree.

## Key differences from upstream

- **No focus stealing on reads** — reads the AX tree without activating ChatGPT, so you can keep working while it polls for completion
- **Clipboard paste** instead of per-character keystroke injection — instant, preserves formatting
- **Configurable polling** — quick mode (5s poll, 60s timeout) for fast queries, deep mode (15min poll, 1h timeout) for o1/deep research
- **Text stability detection** — fallback completion signal when the button heuristic misses (3 consecutive identical reads = done)
- **Subprocess timeouts** — all AppleScript calls timeout after 30s instead of hanging forever

## How it works

1. **Send**: activates ChatGPT once, opens new conversation (Cmd+N) or navigates to an existing one, pastes prompt via clipboard
2. **Poll**: reads the accessibility tree passively (no focus steal) looking for two completion signals:
   - Button heuristic: model selection button followed by voice/transcribe button = idle state
   - Text stability: conversation text unchanged for 3 consecutive reads
3. **Return**: extracts all static text from the AX tree, cleans up UI artifacts, returns the response

### Conversation management

- **List**: reads the sidebar AX tree without activating ChatGPT — no focus steal
- **Navigate**: activates ChatGPT once (clicking requires focus), clicks the matching sidebar item
- **Read**: navigates to a conversation then reads its content via the existing passive reader

## Install

```bash
pip install git+https://github.com/mark-liu/chatgpt-mcp.git
```

Or run without installing:

```bash
uvx --from git+https://github.com/mark-liu/chatgpt-mcp.git chatgpt-mcp
```

PyPI: `pip install chatgpt-desktop-mcp` once published (name `chatgpt-mcp` is taken upstream).

## Configure with Claude Code

```bash
claude mcp add chatgpt -s user -- uvx --from git+https://github.com/mark-liu/chatgpt-mcp.git chatgpt-mcp
```

## Requirements

- macOS (AppleScript + accessibility tree)
- [ChatGPT desktop app](https://chatgpt.com/desktop) installed and logged in
- Accessibility permission granted to your terminal (System Settings > Privacy & Security > Accessibility)

## Tools

### `ask_chatgpt_tool`

Send a prompt to ChatGPT and wait for the response. Opens a new conversation by default, or continues an existing one if `conversation` is specified.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | str | required | The message to send |
| `quick` | bool | `False` | `True`: 5s poll, 60s timeout. `False`: 15min poll, 1h timeout |
| `conversation` | str | `""` | Optional conversation title to continue (substring match, case-insensitive). If empty, starts a new conversation |

### `get_chatgpt_response_tool`

Read the current conversation without sending anything. Waits for completion using deep polling.

### `list_conversations_tool`

List conversations from the ChatGPT sidebar without stealing focus. Returns numbered titles that can be used with `read_conversation_tool` or the `conversation` parameter of `ask_chatgpt_tool`.

### `read_conversation_tool`

Navigate to an existing conversation by title and read its full content.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `conversation` | str | required | Title to match (substring, case-insensitive) |

Activates ChatGPT once to click the sidebar item, then reads the conversation text.

## Limitations

- **English-only button detection** — the AppleScript checks for English button labels ("voice", "Transcribe", "model", "GPT"). Non-English ChatGPT UI will break completion detection.
- **Completion detection is heuristic** — it works by reading button sequences and text stability, not an API signal. Edge cases exist.
- **Clipboard race window** — there's a ~0.7s window during send where the clipboard contains your prompt. Restored afterwards.
- **macOS only** — relies on AppleScript and the accessibility tree.
- **One conversation at a time** — the desktop app has one active conversation. Concurrent sends will collide.

## License

MIT
