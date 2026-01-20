# SMS Setup Guide

VM Monitor supports SMS alerts via multiple providers.

## Supported Providers

| Provider | Coverage | Cost |
|----------|----------|------|
| **Twilio** | Global | ~$0.08/SMS |
| **Textbelt** | Global | $0.05-$0.15/SMS |
| **İleti Merkezi** | Turkey | Pay-per-SMS |

## Configuration

Create `instance/sms_config.json`:

### Twilio

```json
{
  "provider": "twilio",
  "recipient": "+1234567890",
  "dashboard_url": "https://your-dashboard.com",
  "twilio": {
    "account_sid": "ACxxxxxxxxxxxxxxxxx",
    "auth_token": "your_auth_token",
    "from_number": "+19876543210"
  }
}
```

**Setup Steps:**
1. Create account at [twilio.com](https://www.twilio.com)
2. Get Account SID and Auth Token from Console
3. Buy or verify a phone number
4. Enable SMS for target countries in Geo Permissions

### Textbelt

```json
{
  "provider": "textbelt",
  "recipient": "+1234567890",
  "dashboard_url": "https://your-dashboard.com",
  "textbelt": {
    "api_key": "your_textbelt_key"
  }
}
```

**Note:** Use `textbelt` as API key for 1 free SMS/day (testing).

### İleti Merkezi (Turkey)

```json
{
  "provider": "iletimerkezi",
  "recipient": "5551234567",
  "dashboard_url": "https://your-dashboard.com",
  "iletimerkezi": {
    "api_key": "your_api_key",
    "api_hash": "your_api_hash",
    "sender": "YOURSENDER"
  }
}
```

## SMS Schedule

Default schedule (Turkey timezone):
- 08:30
- 12:00
- 13:30
- 17:00

SMS is only sent if there are alerts (≥90%) or warnings (≥80%).

## Manual Trigger

- **Dashboard:** Click "📱 Send SMS" button in header
- **API:** `POST /api/send-sms`
- **View Schedule:** `GET /api/schedule`

## Disabling SMS

Set provider to `disabled`:

```json
{
  "provider": "disabled"
}
```

Or set feature flag:

```json
{
  "sms": false
}
```
