#!/usr/bin/env python3
"""
Skysysx Auto-Converter & Push Bot
Target: http://skysysx.net/e/thanatos
Based on FULL HTML Structure:
- Textarea ID: source (input), target (output)
- Button ID: convert, push
- Format: username|password|cookie  or  username|password|extra|cookie
- Convert → Convert button click → Push button click
- API: /api/info (lock state), /api/push (push endpoint)
- Polling: every 5s for lock state, 2s for job progress
"""

import os
import re
import time
import json
import base64
import requests
import threading
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ========== CONFIGURATION ==========
BOT_TOKEN = "8590664728:AAFNdWkMCr37OZHEPgl_NGbJNibMMhyLT9M"
ADMIN_CHAT_ID = "5624145641"
TARGET_URL = "http://skysysx.net/e/thanatos"
API_BASE = "http://skysysx.net"
REFRESH_INTERVAL = 5  # seconds for lock state check
CONVERT_BATCH_SIZE = 50
# ===================================

# Globals
driver = None
conversion_running = False
pending_creds = []
batch_results = []
push_job_ids = []


# ========== SELENIUM SETUP ==========

def init_driver():
    """Initialize headless Chrome driver (works on Termux, Linux, Windows)"""
    global driver
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1280,800")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # Termux-specific paths
    if os.path.exists("/data/data/com.termux/files/usr/bin/chromium"):
        chrome_options.binary_location = "/data/data/com.termux/files/usr/bin/chromium"
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return True
    except Exception as e:
        print(f"[!] Driver init failed: {e}")
        return False


# ========== SERVER / API CHECKS ==========

def check_api_info():
    """Fetch /api/info to check lock states"""
    try:
        r = requests.get(f"{API_BASE}/api/info", timeout=10)
        if r.ok:
            return r.json()
        return None
    except:
        return None

def is_server_online():
    """Check if server is online and push is unlocked"""
    info = check_api_info()
    if not info:
        return False
    
    push_locked = info.get("push_locked", False)
    api_offline = info.get("api_offline_locked", False)
    webhook_status = info.get("webhook_status", "")
    
    # Online = not admin-locked AND not api-offline AND webhook ok
    if not push_locked and not api_offline and webhook_status != "fail":
        return True
    
    # Check order closed banner (push_locked=True) vs API offline
    if push_locked:
        print("[!] Push locked by admin (order closed)")
    if api_offline or webhook_status == "fail":
        print("[!] API offline or webhook failed")
    
    return False

def wait_for_server_online(timeout=600):
    """Wait until server comes online, checking every 5 seconds"""
    start = time.time()
    send_tg(f"🔄 Waiting for server to come online... (timeout: {timeout}s)")
    
    while time.time() - start < timeout:
        if is_server_online():
            send_tg(f"✅ *Server ONLINE!* (waited {int(time.time()-start)}s)")
            return True
        
        elapsed = int(time.time() - start)
        if elapsed % 30 == 0 and elapsed > 0:
            send_tg(f" Still waiting... ({elapsed}s elapsed)")
        
        time.sleep(REFRESH_INTERVAL)
    
    send_tg(f"❌ *Timeout* — Server did not come online within {timeout}s")
    return False


# ========== TELEGRAM FUNCTIONS ==========

def send_tg(text, chat_id=None):
    """Send Telegram message"""
    cid = chat_id or ADMIN_CHAT_ID
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": cid, 
            "text": text, 
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }, timeout=10)
    except:
        pass

def send_tg_file(filepath, caption="", chat_id=None):
    """Send file to Telegram"""
    cid = chat_id or ADMIN_CHAT_ID
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        with open(filepath, "rb") as f:
            requests.post(url, files={"document": f}, 
                         data={"chat_id": cid, "caption": caption}, timeout=30)
    except:
        pass

def get_updates(offset=0):
    """Get pending messages"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={"offset": offset + 1, "timeout": 10}, timeout=15)
        return r.json().get("result", [])
    except:
        return []


# ========== CREDENTIAL PARSING ==========

def parse_creds_file(filepath):
    """Parse username|||password|||season cookies → username|password|cookie format for site"""
    creds_list = []
    
    if not os.path.exists(filepath):
        return creds_list
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Input format: username|||password|||season cookies
            if '|||' in line:
                parts = line.split('|||')
                username = parts[0].strip() if len(parts) > 0 else ""
                password = parts[1].strip() if len(parts) > 1 else ""
                cookies = parts[2].strip() if len(parts) > 2 else ""
                
                if username and password and cookies:
                    # Convert to site format: username|password|cookie
                    site_line = f"{username}|{password}|{cookies}"
                    creds_list.append(site_line)
    
    return creds_list


# ========== BROWSER AUTOMATION (Based on actual HTML) ==========

def wait_for_element(by, selector, timeout=15):
    """Wait for element to be clickable"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, selector))
        )
        return element
    except TimeoutException:
        return None

def wait_for_presence(by, selector, timeout=15):
    """Wait for element to be present"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
        return element
    except TimeoutException:
        return None

def check_push_interface_visible():
    """Check if pushInterface is visible (display:contents, not none)"""
    try:
        interface = driver.find_element(By.ID, "pushInterface")
        display = interface.value_of_css_property("display")
        return display != "none"
    except:
        return False

def paste_to_source_textarea(batch_lines):
    """Paste credentials into #source textarea"""
    try:
        textarea = driver.find_element(By.ID, "source")
        textarea.clear()
        time.sleep(0.3)
        
        # Paste all lines at once
        batch_text = "\n".join(batch_lines)
        textarea.send_keys(batch_text)
        
        # Trigger input event
        driver.execute_script("""
            var ta = document.getElementById('source');
            ta.dispatchEvent(new Event('input', {bubbles: true}));
        """)
        
        line_count = len(batch_lines)
        print(f"[+] Pasted {line_count} lines into #source")
        return True
    except Exception as e:
        print(f"[!] Paste error: {e}")
        return False

def click_convert_button():
    """Click the Convert button (id=convert)"""
    try:
        btn = wait_for_element(By.ID, "convert", timeout=10)
        if btn:
            driver.execute_script("arguments[0].scrollIntoView(true);", btn)
            time.sleep(0.5)
            btn.click()
            print("[+] Clicked Convert button")
            time.sleep(3)  # Wait for conversion to complete
            return True
        
        # Fallback: try by text
        btn2 = wait_for_element(By.XPATH, "//button[contains(text(), 'Convert')]", timeout=5)
        if btn2:
            btn2.click()
            print("[+] Clicked Convert (fallback)")
            time.sleep(3)
            return True
            
        print("[!] Convert button not found")
        return False
    except Exception as e:
        print(f"[!] Convert click error: {e}")
        return False

def click_push_button():
    """Click the Push button (id=push)"""
    try:
        btn = wait_for_element(By.ID, "push", timeout=10)
        if btn:
            # Check if disabled
            disabled = btn.get_attribute("disabled")
            if disabled:
                print("[!] Push button is disabled — may need to convert first")
                return False
            
            driver.execute_script("arguments[0].scrollIntoView(true);", btn)
            time.sleep(0.5)
            
            # Click via JS for reliability
            driver.execute_script("arguments[0].click();", btn)
            print("[+] Clicked Push button")
            time.sleep(4)  # Wait for push to initiate
            return True
        
        # Fallback
        btn2 = wait_for_element(By.XPATH, "//button[contains(text(), 'Push')]", timeout=5)
        if btn2:
            driver.execute_script("arguments[0].click();", btn2)
            print("[+] Clicked Push (fallback)")
            time.sleep(4)
            return True
            
        print("[!] Push button not found")
        return False
    except Exception as e:
        print(f"[!] Push click error: {e}")
        return False

def get_push_result():
    """Read the push result from pushResult element"""
    try:
        result_el = driver.find_element(By.ID, "pushResult")
        text = result_el.text.strip()
        if text and text != "Not pushed":
            return text
    except:
        pass
    
    # Also check target textarea for converted output
    try:
        target_el = driver.find_element(By.ID, "target")
        target_text = target_el.get_attribute("value")
        if target_text:
            return f"✅ Converted successfully ({len(target_text.split(chr(10)))} lines)"
    except:
        pass
    
    return None

def get_converted_count():
    """Get success/fail counts from the status tags"""
    try:
        ok_el = driver.find_element(By.ID, "okCount")
        fail_el = driver.find_element(By.ID, "failCount")
        return ok_el.text, fail_el.text
    except:
        return "Success: ?", "Failed: ?"


# ========== MAIN BATCH WORKFLOW ==========

def process_batch(batch_lines, batch_num, total_batches):
    """Process a single batch: paste → convert → push → get result"""
    
    # Step 1: Paste into source textarea
    if not paste_to_source_textarea(batch_lines):
        return False, "Failed to paste"
    
    time.sleep(0.5)
    
    # Step 2: Click Convert
    if not click_convert_button():
        return False, "Convert failed"
    
    # Step 3: Check conversion results
    ok_text, fail_text = get_converted_count()
    
    # Step 4: Click Push
    if not click_push_button():
        return False, f"Push failed ({ok_text}, {fail_text})"
    
    # Step 5: Get push result
    time.sleep(2)
    result = get_push_result()
    
    # Extract job ID from result if present
    if result:
        job_match = re.search(r'Job\s+(\S+)', result)
        if job_match:
            push_job_ids.append(job_match.group(1))
    
    return True, result or f"Pushed ({ok_text}, {fail_text})"


def run_conversion_job():
    """Main conversion job — processes all batches"""
    global conversion_running, driver, pending_creds, batch_results, push_job_ids
    
    conversion_running = True
    batch_results = []
    push_job_ids = []
    
    try:
        # Step 1: Wait for server
        if not wait_for_server_online():
            send_tg("❌ Server offline. Aborting.")
            conversion_running = False
            return
        
        # Step 2: Navigate to page
        send_tg("🌐 Loading target page...")
        driver.get(TARGET_URL)
        time.sleep(4)
        
        # Step 3: Check if push interface is visible
        if not check_push_interface_visible():
            send_tg("⚠️ Push interface is hidden (locked/offline). Waiting for unlock...")
            
            # Wait and retry
            for i in range(60):  # 5 minutes max
                time.sleep(5)
                driver.get(TARGET_URL)
                time.sleep(3)
                if check_push_interface_visible():
                    send_tg("✅ Push interface now visible!")
                    break
                if i % 6 == 0:
                    send_tg(f"⏳ Still waiting for unlock... ({i*5}s)")
            else:
                send_tg("❌ Push interface never became visible.")
                conversion_running = False
                return
        
        # Step 4: Prepare batches
        total = len(pending_creds)
        batches = [pending_creds[i:i+CONVERT_BATCH_SIZE] 
                  for i in range(0, total, CONVERT_BATCH_SIZE)]
        
        send_tg(f"📊 *Starting*\nTotal: {total}\nBatches: {len(batches)}")
        
        success_count = 0
        fail_count = 0
        
        # Step 5: Process each batch
        for idx, batch in enumerate(batches, 1):
            if not conversion_running:
                send_tg(" Stopped by user.")
                break
            
            send_tg(f"⏳ *Batch {idx}/{len(batches)}* — {len(batch)} accounts...")
            
            # Refresh page before each batch for clean state
            if idx > 1:
                driver.get(TARGET_URL)
                time.sleep(3)
                if not check_push_interface_visible():
                    send_tg(f"⚠️ Interface locked during batch {idx}. Aborting.")
                    break
            
            ok, msg = process_batch(batch, idx, len(batches))
            
            if ok:
                success_count += len(batch)
                result_preview = msg[:300] if msg else "Done"
                send_tg(f"✅ *Batch {idx} Complete*\n`{result_preview}`")
            else:
                fail_count += len(batch)
                send_tg(f"❌ *Batch {idx} Failed*\n`{msg[:200]}`")
            
            # Small delay between batches
            time.sleep(2)
        
        # Step 6: Save and send results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = f"push_results_{timestamp}.txt"
        
        with open(result_file, 'w', encoding='utf-8') as f:
            f.write(f"Target: {TARGET_URL}\n")
            f.write(f"Total Credentials: {total}\n")
            f.write(f"Success: {success_count}\n")
            f.write(f"Failed: {fail_count}\n")
            f.write(f"Job IDs: {', '.join(push_job_ids)}\n")
            f.write(f"Time: {datetime.now()}\n")
            f.write("="*50 + "\n\n")
            for line in batch_results:
                f.write(str(line) + "\n\n")
        
        send_tg_file(result_file, 
            f"📁 *Results*\n✅ {success_count}/{total} pushed\n {len(push_job_ids)} jobs")
        
        send_tg(f"🏁 *Complete!*\n✅ {success_count} | ❌ {fail_count}")
        
    except Exception as e:
        send_tg(f"❌ *Error:* `{str(e)[:300]}`")
        import traceback
        traceback.print_exc()
    finally:
        conversion_running = False


# ========== TELEGRAM COMMAND HANDLER ==========

def handle_telegram_commands():
    """Listen for Telegram commands and file uploads"""
    global conversion_running, pending_creds, batch_results, push_job_ids, driver
    last_update_id = 0
    
    while True:
        try:
            updates = get_updates(last_update_id)
            
            for update in updates:
                last_update_id = update["update_id"]
                msg = update.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")
                document = msg.get("document")
                
                if not chat_id:
                    continue
                
                # Handle file upload
                if document:
                    file_id = document["file_id"]
                    file_name = document.get("file_name", "creds.txt")
                    
                    # Download file from Telegram
                    file_info = requests.get(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
                    ).json()
                    file_path_tg = file_info["result"]["file_path"]
                    download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path_tg}"
                    
                    os.makedirs("uploads", exist_ok=True)
                    local_path = f"uploads/{chat_id}_{file_name}"
                    
                    r = requests.get(download_url)
                    with open(local_path, 'wb') as f:
                        f.write(r.content)
                    
                    # Parse credentials
                    global pending_creds
                    creds = parse_creds_file(local_path)
                    
                    if not creds:
                        send_tg("❌ Invalid format. Use:\n`username|||password|||cookies`", chat_id)
                        continue
                    
                    pending_creds = creds
                    
                    send_tg(
                        f"✅ *Loaded: {file_name}*\n"
                        f"📊 {len(creds)} credentials\n"
                        f"📦 Batches of {CONVERT_BATCH_SIZE}\n\n"
                        f"Type `go` to start instantly,\n"
                        f"or bot will auto-start when server is online.",
                        chat_id
                    )
                    continue
                
                # Handle text commands
                if not text:
                    continue
                
                if text.lower() == 'go' and not conversion_running and pending_creds:
                    send_tg("🚀 Starting now...", chat_id)
                    threading.Thread(target=run_conversion_job, daemon=True).start()
                
                elif text.startswith('/'):
                    cmd = text.split()[0].lower()
                    
                    if cmd == '/start':
                        send_tg(
                            "🤖 *Skysysx Auto-Push Bot*\n\n"
                            "Commands:\n"
                            "`/start` — Help\n"
                            "`go` — Start pushing now\n"
                            "`/stop` — Stop current job\n"
                            "`/status` — Check status\n\n"
                            "*Usage:*\n"
                            "1. Upload `.txt` file\n"
                            "   Format: `username|||password|||cookies`\n"
                            "2. Bot converts to site format\n"
                            "3. Pastes into textarea\n"
                            "4. Clicks **Convert** → **Push**\n"
                            "5. Results sent to you!",
                            chat_id
                        )
                    
                    elif cmd == '/stop':
                        conversion_running = False
                        send_tg(" Stopping...", chat_id)
                    
                    elif cmd == '/status':
                        s = f"📊 *Status*\n"
                        info = check_api_info()
                        if info:
                            locked = info.get("push_locked", False)
                            offline = info.get("api_offline_locked", False)
                            s += f"Server: {'✅' if not locked and not offline else '❌'}\n"
                        else:
                            s += "Server: ❌ (unreachable)\n"
                        s += f"Job: {' Running' if conversion_running else '⏸️ Idle'}\n"
                        s += f"Creds: {len(pending_creds)}"
                        send_tg(s, chat_id)
            
            time.sleep(1)
        except Exception as e:
            print(f"[!] Cmd error: {e}")
            time.sleep(3)


# ========== MAIN FUNCTION ==========

def main():
    print("""
    ==========================================
      Skysysx Auto-Push Bot v3.0
      Target: skysysx.net/e/thanatos
      Batch: 50 | Interval: 5s
      IDs: source, target, convert, push
    ==========================================
    """)
    
    # Init Chrome
    if not init_driver():
        print("[!] Installing chromium/chromium-driver...")
        # Try Termux first, then Debian/Ubuntu
        if os.path.exists("/data/data/com.termux/files/usr/bin/pkg"):
            os.system("pkg install -y chromium chromium-driver")
        else:
            os.system("sudo apt install -y chromium-driver")
        if not init_driver():
            print("[!] Failed. Install manually:")
            print("  Termux: pkg install chromium chromium-driver")
            print("  Linux:  sudo apt install chromium-driver")
            return
    
    print("[+] Browser ready")
    
    # Start handler
    try:
        handle_telegram_commands()
    except KeyboardInterrupt:
        print("\n[*] Stopping...")
        if driver:
            driver.quit()
        print("[*] Done.")

if __name__ == "__main__":
    main()
