import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import yt_dlp

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment Variable မှ BOT_TOKEN ကို ဖတ်ယူခြင်း
TOKEN = os.getenv("BOT_TOKEN")

# Main Menu Keyboard
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🎬 YouTube", callback_data="menu_yt"), InlineKeyboardButton("🎵 TikTok", callback_data="menu_tt")],
        [InlineKeyboardButton("📘 Facebook", callback_data="menu_fb"), InlineKeyboardButton("🔍 Music Search", callback_data="menu_search")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Quality Selection Keyboard
def get_quality_menu():
    keyboard = [
        [InlineKeyboardButton("🎵 MP3 (Audio)", callback_data="quality_mp3")],
        [InlineKeyboardButton("360p", callback_data="quality_360"), InlineKeyboardButton("480p", callback_data="quality_480")],
        [InlineKeyboardButton("720p", callback_data="quality_720"), InlineKeyboardButton("1080p", callback_data="quality_1080")],
        [InlineKeyboardButton("2K", callback_data="quality_1440"), InlineKeyboardButton("4K", callback_data="quality_2160")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Command Handler: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name
    await update.message.reply_text(
        f"မင်္ဂလာပါ {user_first_name}! 🤖\n\n"
        "မမရေ💖🍓 မမကြိုက်တဲ့ Videoလေးတွေ Download ရပြီနော်။လောလောဆယ်တော့ Tiktok, Facebookပဲရအူးမယ်နော်။မောင်ကြိုးစားပြီးပြင်ပေးမယ်။ချစ်တယ်နော်🍓💖 အာဘွားမွကျိ😘🍓",
        reply_markup=get_main_menu()
    )

# Callback Query Handler (Buttons)
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("menu_"):
        if data == "menu_search":
            context.user_data["awaiting_search"] = True
            await query.edit_message_text("🔍 ရှာဖွေချင်သည့် သီချင်း အမည် သို့မဟုတ် အနုပညာရှင် ရိုက်ပို့ပေးပါ:")
        else:
            platform = data.split("_")[1].upper()
            await query.edit_message_text(f"📥 {platform} Link ကို Telegram သို့ ပေးပို့ပေးပါ။")

    elif data.startswith("quality_"):
        quality = data.split("_")[1]
        url = context.user_data.get("pending_url")
        if not url:
            await query.edit_message_text("❌ Link မရှိတော့ပါ။ Link ပြန်ပို့ပေးပါ။")
            return

        await query.edit_message_text("⏳ Download ပြုလုပ်နေပါသည်... ခေတ္တစောင့်ဆိုင်းပေးပါ။")
        asyncio.create_task(process_download(query, context, url, quality))

    elif data.startswith("select_search_"):
        idx = int(data.split("_")[2])
        results = context.user_data.get("search_results", [])
        if 0 <= idx < len(results):
            selected = results[idx]
            url = f"https://www.youtube.com/watch?v={selected['id']}"
            await query.edit_message_text(f"🎵 **{selected['title']}** ကို MP3 အဖြစ် ဒေါင်းလုဒ်ဆွဲနေပါသည်...")
            asyncio.create_task(process_download(query, context, url, "mp3"))

# Text Message Handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # Search Mode
    if context.user_data.get("awaiting_search"):
        context.user_data["awaiting_search"] = False
        msg = await update.message.reply_text(f"🔍 '{text}' ကို ရှာဖွေနေပါသည်...")
        ydl_opts = {
            'extract_flat': True,
            'quiet': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
        }
        loop = asyncio.get_running_loop()
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(f"ytsearch5:{text}", download=False))
                entries = info.get('entries', [])
                if not entries:
                    await msg.edit_text("❌ မည်သည့် သီချင်းမျှ ရှာမတွေ့ပါ။")
                    return

                context.user_data["search_results"] = entries
                keyboard = []
                for idx, entry in enumerate(entries):
                    title = entry.get('title', 'Unknown')[:35]
                    keyboard.append([InlineKeyboardButton(f"🎵 {title}", callback_data=f"select_search_{idx}")])
                
                await msg.edit_text("👇 ဒေါင်းလုဒ်ဆွဲလိုသည့် သီချင်းကို ရွေးချယ်ပါ:", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"Search error: {e}")
            await msg.edit_text("❌ ရှာဖွေရာတွင် အမှားအယွင်း ရှိနေပါသည်။")
        return

    # Link Processing
    if text.startswith("http://") or text.startswith("https://"):
        context.user_data["pending_url"] = text
        await update.message.reply_text("🎬 Quality သို့မဟုတ် Format ရွေးချယ်ပါ:", reply_markup=get_quality_menu())
    else:
        await update.message.reply_text("❌ မှန်ကန်သော Link ပေးပို့ပေးပါ သို့မဟုတ် /start ကို နှိပ်ပါ။", reply_markup=get_main_menu())

# Download Processing Logic
async def process_download(query, context, url, quality):
    chat_id = query.message.chat_id
    loop = asyncio.get_running_loop()
    output_filename = f"dl_{query.message.message_id}"

    # YouTube အပါအဝင် အခြား Platform များအတွက် Anti-Bot Bypass Options
    common_ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    }

    if quality == "mp3":
        ydl_opts = {
            **common_ydl_opts,
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'outtmpl': f'{output_filename}.%(ext)s',
        }
    else:
        ydl_opts = {
            **common_ydl_opts,
            'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best',
            'outtmpl': f'{output_filename}.%(ext)s',
            'merge_output_format': 'mp4',
        }

    try:
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)

        info = await loop.run_in_executor(None, download)
        file_path = f"{output_filename}.mp3" if quality == "mp3" else f"{output_filename}.mp4"
        
        if not os.path.exists(file_path):
            for f in os.listdir('.'):
                if f.startswith(output_filename):
                    file_path = f
                    break

        file_size = os.path.getsize(file_path) / (1024 * 1024)

        if file_size > 50:
            await context.bot.send_message(chat_id=chat_id, text="❌ ဖိုင်ဆိုဒ် 50MB ထက်ကြီးသဖြင့် Telegram API Limit ကြောင့် တင်၍ မရပါ။")
        else:
            await context.bot.send_message(chat_id=chat_id, text="📤 Telegram သို့ တင်ပို့နေပါသည်...")
            with open(file_path, 'rb') as file:
                if quality == "mp3":
                    await context.bot.send_audio(chat_id=chat_id, audio=file, title=info.get('title', 'Audio'))
                else:
                    await context.bot.send_video(chat_id=chat_id, video=file, caption=info.get('title', 'Video'))

        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        logger.error(f"Download Error: {e}")
        await context.bot.send_message(chat_id=chat_id, text="❌ ဒေါင်းလုဒ်ဆွဲရာတွင် အမှားအယွင်း ဖြစ်ပေါ်ခဲ့ပါသည်။ (Link မမှန်ပါ သို့မဟုတ် Server Limit ဖြစ်နိုင်ပါသည်)")

def main():
    if not TOKEN:
        logger.error("ERROR: BOT_TOKEN Environment Variable ကို တွေ့ရှိခြင်း မရှိပါ။")
        return

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
