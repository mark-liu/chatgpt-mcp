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

1. **Send**: activates ChatGPT once, opens new conversation (Cmd+N), pastes prompt via clipboard
2. **Poll**: reads the accessibility tree passively (no focus steal) looking for two completion signals:
   - Button heuristic: model selection button followed by voice/transcribe button = idle state
   - Text stability: conversation text unchanged for 3 consecutive reads
3. **Return**: extracts all static text from the AX tree, cleans up UI artifacts, returns the response

## Install

```bash
pip install chatgpt-mcp
# or
uvx chatgpt-mcp
```

## Configure with Claude Code

```bash
claude mcp add chatgpt -- uvx chatgpt-mcp
```

## Requirements

- macOS (AppleScript + accessibility tree)
- [ChatGPT desktop app](https://chatgpt.com/desktop) installed and logged in
- Accessibility permission granted to your terminal (System Settings > Privacy & Security > Accessibility)

## Tools

### `ask_chatgpt_tool`

Send a prompt to ChatGPT in a new conversation and wait for the response.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | str | required | The message to send |
| `quick` | bool | `False` | `True`: 5s poll, 60s timeout. `False`: 15min poll, 1h timeout |

### `get_chatgpt_response_tool`

Read the current conversation without sending anything. Waits for completion using deep polling.

## Limitations

- **English-only button detection** — the AppleScript checks for English button labels ("voice", "Transcribe", "model", "GPT"). Non-English ChatGPT UI will break completion detection.
- **Completion detection is heuristic** — it works by reading button sequences and text stability, not an API signal. Edge cases exist.
- **Clipboard race window** — there's a ~0.7s window during send where the clipboard contains your prompt. Restored afterwards.
- **macOS only** — relies on AppleScript and the accessibility tree.
- **One conversation at a time** — the desktop app has one active conversation. Concurrent sends will collide.

## License

MIT
