# Telegram Runbook (Long Polling)

## 1) Environment

Create `.env` next to `main.py` (or set environment variables in your shell):

- `RUN_MODE=telegram`
- Telegram bot token (see `.env.example`)

## 2) Start

```bash
python main.py
```

You should see logs from the Telegram runner and a repeating `telegram_get_updates@v1` cycle in the event stream.

## 3) The "it is alive but /start doesn't work" checklist

If you can run `python main.py` and see events, but Telegram doesn't react:

1. **Wrong mode**: if `RUN_MODE` is not `telegram`, all Telegram effects are forced into **stub** mode.
2. **No bot chat**: open the bot in Telegram and press **Start** at least once.
3. **Wrong chat_id**: Telegram returns `Bad Request: chat not found` when you try to send to a chat that never started the bot.
4. **Token mismatch**: if the runner immediately exits with "stub mode: missing ...", your token is not provided.

## 4) Minimal sanity test

- Start the bot.
- Open Telegram and press **Start**.
- Send any message.
- You should receive the main menu message from BusinesAIOS.
