# Telegram Setup Guide

VM Monitor supports Telegram notifications as an alternative to SMS.

## Why Telegram?

| Feature | SMS | Telegram |
|---------|-----|----------|
| **Cost** | ~$0.05-0.15/msg | Free |
| **Rich Text** | No | Yes (Markdown) |
| **Multi-recipient** | Extra cost | Free |
| **Setup** | Provider account | 2 minutes |

## Quick Setup

### Step 1: Create a Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot`
3. Choose a name (e.g., "My VM Alerts")
4. Choose a username ending in `bot` (e.g., `myvm_alerts_bot`)
5. Copy the **bot token** (looks like `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Get Your Chat ID

1. Open your new bot in Telegram (click the link BotFather gives you)
2. Send any message (e.g., "hi")
3. Open this URL in your browser (replace `YOUR_BOT_TOKEN`):
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
4. Find `"chat":{"id":XXXXXXXX}` - that's your chat ID

### Step 3: Configure VM Monitor

Create or edit `dashboard/instance/sms_config.json`:

```json
{
  "provider": "telegram",
  "dashboard_url": "https://your-dashboard.com",
  "telegram": {
    "bot_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
    "chat_id": "your_chat_id"
  }
}
```

### Step 4: Test

```bash
curl "https://api.telegram.org/botYOUR_BOT_TOKEN/sendMessage?chat_id=YOUR_CHAT_ID&text=Test"
```

You should receive a "Test" message in Telegram.

## Multiple Recipients

To send alerts to multiple people, use `chat_ids` array:

```json
{
  "provider": "telegram",
  "telegram": {
    "bot_token": "your_token",
    "chat_ids": ["123456789", "987654321"]
  }
}
```

> [!NOTE]
> Each recipient must message the bot first before they can receive notifications.
> This is a Telegram privacy requirement.

### Adding a New Recipient

1. New person opens the bot link (e.g., `t.me/myvm_alerts_bot`)
2. Sends any message to the bot
3. Get their chat ID from `/getUpdates`
4. Add their ID to `chat_ids` array

## Alternative: Use a Group

If you prefer not requiring each person to message the bot:

1. Create a Telegram group
2. Add the bot to the group
3. Send a message in the group
4. Get the group's chat ID from `/getUpdates` (negative number like `-1001234567890`)
5. Use the group ID in config

## Environment Variables

Instead of config file, you can use environment variables:

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

## Troubleshooting

### Bot doesn't respond to /getUpdates
- Make sure you sent a message to the bot after creating it
- Wait a few seconds and try again

### "Chat not found" error
- User hasn't messaged the bot yet
- Wrong chat ID format

### Messages not delivered
- Check bot token is correct
- Verify chat ID in config matches the user

## Message Relay Service (Optional)

For multi-tenant setups or to avoid exposing the bot token in each dashboard, use the [Message Relay Service](https://github.com/aydinguven/message-relay):

```json
{
  "provider": "relay",
  "relay": {
    "url": "http://relay-server:5001",
    "api_key": "your-api-key",
    "template": "custom",
    "chat_ids": ["123456789"]
  }
}
```

Benefits:
- Bot token stays in one place
- Template-only messaging (prevents abuse)
- Centralized logging and rate limiting

## Disabling Notifications

```json
{
  "provider": "disabled"
}
```
