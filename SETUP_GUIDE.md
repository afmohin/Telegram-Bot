# Skysysx Auto-Push Bot - Complete Setup Guide

## Overview
This bot automates credential pushing to `skysysx.net/e/thanatos` via Telegram. It uses Selenium browser automation to paste credentials, click Convert, then Push, and sends results back to Telegram.

---

## Prerequisites

### 1. Python 3.8+
Download from: https://www.python.org/downloads/
- During installation, check **"Add Python to PATH"**

### 2. Google Chrome
Download from: https://www.google.com/chrome/
- Must be installed (bot uses ChromeDriver automatically)

### 3. Telegram App
- You need Telegram to interact with the bot

---

## Installation Steps

### Step 1: Download the Files
Place these files in a folder:
- `skysysx_bot.py` (main bot script)
- `demo_creds.txt` (sample credentials file)

### Step 2: Install Dependencies
Open Command Prompt / PowerShell in the folder and run:
```bash
pip install selenium requests
```

### Step 3: Verify Installation
```bash
python --version
pip show selenium
```

---

## Running the Bot

### Start the Bot
```bash
python skysysx_bot.py
```

You should see:
```
==========================================
  Skysysx Auto-Push Bot v3.0
  Target: skysysx.net/e/thanatos
  Batch: 50 | Interval: 5s
  IDs: source, target, convert, push
==========================================

[+] Browser ready
```

The bot is now running and polling Telegram for messages.

---

## How to Test It Works

### Test 1: Bot Response
1. Open Telegram
2. Go to **@mohin_cookies_bot**
3. Send `/start`
4. You should receive the help menu

### Test 2: File Upload
1. Upload `demo_creds.txt` to the bot
2. Bot should reply:
   ```
   ✅ Loaded: demo_creds.txt
   📊 3 credentials
    Batches of 50
   
   Type go to start instantly,
   or bot will auto-start when server is online.
   ```

### Test 3: Start Job
1. Send `go` to the bot
2. Bot will check server status
3. If server is online → starts pushing
4. If server is offline → waits and notifies when online

### Test 4: Check Status
Send `/status` to see:
- Server online/offline status
- Job running or idle
- Number of loaded credentials

---

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Show help menu |
| `go` | Start pushing credentials |
| `/stop` | Stop current job |
| `/status` | Check server and job status |

---

## File Format for Credentials

Create a `.txt` file with this format (one per line):
```
username|||password|||cookies
```

**Example:**
```
john_doe|||P@ssw0rd123|||session_id=abc123; token=xyz789
jane_smith|||MySecret456|||session_id=def456; token=uvw012
```

**Notes:**
- Lines starting with `#` are ignored (comments)
- Empty lines are ignored
- Must have 3 parts separated by `|||`

---

## How the Bot Works (8 Steps)

1. **Refreshes** `skysysx.net/e/thanatos` every 5 seconds
2. **Notifies** on Telegram when server comes online
3. **Parses** uploaded file (`username|||password|||cookies`)
4. **Splits** credentials into batches of 50
5. **Clicks Convert** button on the website
6. **Clicks Push** button
7. **Sends** each batch result to Telegram
8. **Sends** complete results as a `.txt` file

---

## Troubleshooting

### Problem: "Driver init failed"
**Solution:** Install ChromeDriver manually
```bash
pip install webdriver-manager
```
Or download from: https://chromedriver.chromium.org/

### Problem: "ModuleNotFoundError: No module named 'selenium'"
**Solution:**
```bash
pip install selenium requests
```

### Problem: Bot not responding on Telegram
**Solution:**
- Check if another instance is already running
- Verify internet connection
- Check bot token is correct in the script

### Problem: Server stays offline
**Solution:**
- The bot will wait up to 10 minutes
- Check `skysysx.net` manually in browser
- Bot will auto-start when server recovers

### Problem: Unicode/Encoding errors (Windows)
**Solution:** Run with UTF-8 encoding:
```bash
python -X utf8 skysysx_bot.py
```

---

## Important Notes

- **Only one instance** can run at a time
- Bot uses **long polling** (checks Telegram every 1 second)
- Requires **Chrome browser** installed
- Headless mode (no visible browser window)
- Results saved as `push_results_TIMESTAMP.txt`
- Uploads saved in `uploads/` folder

---

## Configuration (Edit in skysysx_bot.py)

```python
BOT_TOKEN = "your_bot_token_here"
ADMIN_CHAT_ID = "your_telegram_chat_id"
TARGET_URL = "http://skysysx.net/e/thanatos"
API_BASE = "http://skysysx.net"
REFRESH_INTERVAL = 5  # seconds
CONVERT_BATCH_SIZE = 50
```

---

## Quick Start Checklist

- [ ] Python installed
- [ ] Chrome installed
- [ ] Dependencies installed (`pip install selenium requests`)
- [ ] Bot script in folder
- [ ] Run `python skysysx_bot.py`
- [ ] Test with `/start` on Telegram
- [ ] Upload credentials file
- [ ] Send `go` to start

---

## Support

If the website's HTML structure changes (button IDs, classes), update the selectors in `skysysx_bot.py`:
- `By.ID, "source"` - input textarea
- `By.ID, "target"` - output textarea
- `By.ID, "convert"` - convert button
- `By.ID, "push"` - push button
- `By.ID, "pushInterface"` - main interface container
