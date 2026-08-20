
import os
import asyncio
import logging
from dotenv import load_dotenv
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

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
COOKIE_FILE = "cookies.txt"

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🎬 YouTube", callback_data="menu_yt"), InlineKeyboardButton("🎵 TikTok", callback_data="menu_tt")],
        [InlineKeyboardButton("📘 Facebook", callback_data="menu_fb"), InlineKeyboardButton("🔍 Music Search", callback_data="menu_search")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_quality_menu():
    keyboard = [
        [InlineKeyboardButton("🎵 MP3 (Audio)", callback_data="quality_mp3")],
        [InlineKeyboardButton("360p", callback_data="quality_360"), InlineKeyboardButton("480p", callback_data="quality_480")],
        [InlineKeyboardButton("720p", callback_data="quality_720"), InlineKeyboardButton("1080p", callback_data="quality_1080")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "မမရေ💖🍓 မမကြိုက်တဲ့ Videoလေးတွေ Download ရပြီနော်။"
        "လောလောဆယ်တော့ Tiktok, Facebookပဲရအူးမယ်နော်။"
        "မောင်ကြိုးစားပြီးပြင်ပေးမယ်။ချစ်တယ်နော်🍓💖 အာဘွားမွကျိ😘🍓"
    )
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_menu()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("menu_"):
        if data == "menu_search":
            context.user_data["awaiting_search"] = True
            await query.edit_message_text("🔍 ရှာဖွေချင်သည့် သီချင်း အမည်ကို ရိုက်ပို့ပေးပါ:")
        else:
            platform = data.split("_")[1].upper()
            await query.edit_message_text(f"📥 {platform} Link ကို ပေးပို့ပေးပါ။")

    elif data.startswith("quality_"):
        quality = data.split("_")[1]
        url = context.user_data.get("pending_url")
        if not url:
            await query.edit_message_text("❌ Link မရှိတော့ပါ။ Link ပြန်ပို့ပေးပါ။")
            return

        await query.edit_message_text("⏳ Download ပြုလုပ်နေပါသည်... ခေတ္တစောင့်ပေးပါ။")
        asyncio.create_task(process_download(query, context, url, quality))

    elif data.startswith("select_search_"):
        idx = int(data.split("_")[2])
        results = context.user_data.get("search_results", [])
        if 0 <= idx < len(results):
            selected = results[idx]
            url = f"https://www.youtube.com/watch?v={selected['id']}"
            await query.edit_message_text(f"🎵 **{selected['title']}** ကို ဒေါင်းလုဒ်ဆွဲနေပါသည်...")
            asyncio.create_task(process_download(query, context, url, "mp3"))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if context.user_data.get("awaiting_search"):
        context.user_data["awaiting_search"] = False
        msg = await update.message.reply_text(f"🔍 '{text}' ကို ရှာဖွေနေပါသည်...")
        
        ydl_opts = {
            'extract_flat': True, 
            'quiet': True,
        }
        if os.path.exists(COOKIE_FILE):
            ydl_opts['cookiefile'] = COOKIE_FILE

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
                
                await msg.edit_text("👇 ဒေါင်းလုဒ်ဆွဲလိုသည့် သီချင်းကို ရွေးပါ:", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"Search error: {e}")
            await msg.edit_text("❌ ရှာဖွေရာတွင် အမှားအယွင်း ရှိနေပါသည်။")
        return

    if text.startswith("http://") or text.startswith("https://"):
        context.user_data["pending_url"] = text
        await update.message.reply_text("🎬 Quality သို့မဟုတ် Format ရွေးချယ်ပါ:", reply_markup=get_quality_menu())
    else:
        await update.message.reply_text("❌ မှန်ကန်သော Link ပေးပို့ပါ။", reply_markup=get_main_menu())

async def process_download(query, context, url, quality):
    chat_id = query.message.chat_id
    loop = asyncio.get_running_loop()
    output_filename = f"dl_{query.message.message_id}"

    if quality == "mp3":
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'outtmpl': f'{output_filename}.%(ext)s',
            'quiet': True,
        }
    else:
        ydl_opts = {
            'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best',
            'outtmpl': f'{output_filename}.%(ext)s',
            'merge_output_format': 'mp4',
            'quiet': True,
        }

    if os.path.exists(COOKIE_FILE):
        ydl_opts['cookiefile'] = COOKIE_FILE

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
            await context.bot.send_message(chat_id=chat_id, text="❌ ဖိုင်ဆိုဒ် 50MB ထက်ကြီးသဖြင့် Telegram တွင် တင်၍ မရပါ။")
        else:
            await context.bot.send_message(chat_id=chat_id, text="📤 Telegram သို့ တင်ပို့နေပါသည်...")
            with open(file_path, 'rb') as file:
                if quality == "mp3":
                    await context.bot.send_audio(chat_id=chat_id, audio=file, title=info.get('title', 'Audio'))
                else:
                    await context.bot.send_video(chat_id=chat_id, video=file, caption=info.get('title', 'Video'))

    except Exception as e:
        logger.error(f"Download Error: {e}")
        await context.bot.send_message(chat_id=chat_id, text="❌ ဒေါင်းလုဒ်ဆွဲရာတွင် အမှားအယွင်း ဖြစ်ပေါ်ခဲ့ပါသည်။")
    finally:
        for f in os.listdir('.'):
            if f.startswith(output_filename):
                try:
                    os.remove(f)
                except Exception:
                    pass

def main():
    if not TOKEN:
        logger.error("BOT_TOKEN မရှိသေးပါ။ Environment Variable ကို စစ်ဆေးပါ။")
        return
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

if __name__ == "__main__":
    main()
