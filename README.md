# Skysysx Auto-Push Bot - Setup Guide

## What This Bot Does
Automates pushing credentials to skysysx.net using Telegram + Selenium browser automation.

## File Format
Upload a `.txt` file with this format (one per line):
```
username|||password|||cookies
```

**Example:**
```
john_doe|||P@ssw0rd123|||session_id=abc123; token=xyz789
jane_smith|||MySecret456|||session_id=def456; token=uvw012
```

## How to Run

### 1. Install Dependencies
```bash
pip install selenium requests
```

### 2. Install Chrome Driver
- **Windows:** Download from https://chromedriver.chromium.org/
- **Linux:** `sudo apt install chromium-driver`

### 3. Run the Bot
```bash
python3 skysysx_bot.py
```

## Telegram Commands
| Command | Description |
|---------|-------------|
| `/start` | Show help |
| `go` | Start pushing now |
| `/stop` | Stop current job |
| `/status` | Check server status |

## Workflow
1. Bot waits for server to be online
2. User uploads `.txt` file via Telegram
3. Bot parses credentials (batches of 50)
4. Opens headless Chrome → navigates to target site
5. Pastes creds → clicks "Convert" → clicks "Push"
6. Sends results back to Telegram

## Note
- Only ADMIN_CHAT_ID (5624145641) can control the bot
- Bot token and chat ID are hardcoded in the script
- Requires Chrome/Chromium installed on the server
