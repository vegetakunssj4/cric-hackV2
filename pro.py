import os
import logging
import asyncio
import random
from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait
from pyrogram.types import Message
from Mukund import Mukund
from flask import Flask

# Configure Logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Initialize Databases
storage_vegeta = Mukund("Vegeta")
storage_goku = Mukund("Goku")

db_vegeta = storage_vegeta.database("players")
db_goku = storage_goku.database("players")

# Track active database
current_db = db_vegeta  # Default database
current_db_name = "Vegeta"  # Track the name for response messages

# In-memory cache for quick lookups
player_cache = {}

def preload_players():
    """Load players into cache from the active database."""
    global player_cache
    logging.info(f"Preloading players from {current_db_name}...")
    try:
        all_players = current_db.all()
        if isinstance(all_players, dict):
            player_cache = all_players
            logging.info(f"Loaded {len(player_cache)} players from {current_db_name}.")
        else:
            logging.error("Database returned unexpected data format!")
    except Exception as e:
        logging.error(f"Failed to preload database: {e}")

# Flask health check
web_app = Flask(__name__)

@web_app.route('/health')
def health_check():
    return "OK", 200

async def run_flask():
    """ Runs Flask server for health checks """
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    config = Config()
    config.bind = ["0.0.0.0:8000"]
    await serve(web_app, config)

# Environment variables
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION")

assert API_ID, "Missing API_ID!"
assert API_HASH, "Missing API_HASH!"
assert SESSION_STRING, "Missing SESSION!"

bot = Client(
    "pro",
    api_id=int(API_ID),
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    workers=20,
    max_concurrent_transmissions=10
)

TARGET_GROUP_ID = -1002395952299
FORWARD_CHANNEL_ID = -1002370254875
RARITIES_TO_FORWARD = ["Cosmic", "Limited Edition", "Exclusive", "Ultimate"]
collect_running = False

@bot.on_message(filters.command("switchdb") & filters.chat(TARGET_GROUP_ID) & filters.user([7508462500, 1710597756, 6895497681, 7435756663]))
async def switch_database(_, message: Message):
    """Switch between Vegeta and Goku databases."""
    global current_db, current_db_name, player_cache

    new_db_name = message.text.split(maxsplit=1)[1].strip().lower() if len(message.text.split()) > 1 else ""
    
    if new_db_name == "goku":
        current_db = db_goku
        current_db_name = "Goku"
    elif new_db_name == "vegeta":
        current_db = db_vegeta
        current_db_name = "Vegeta"
    else:
        await message.reply("⚠ Invalid database! Use: `/switchdb vegeta` or `/switchdb goku`")
        return

    preload_players()  # Reload cache with new database
    await message.reply(f"✅ Switched to **{current_db_name}** database.")

@bot.on_message(filters.command("startcollect") & filters.chat(TARGET_GROUP_ID) & filters.user([7508462500, 1710597756, 6895497681, 7435756663]))
async def start_collect(_, message: Message):
    global collect_running
    if not collect_running:
        collect_running = True
        await message.reply(f"✅ Collect function started using `{current_db_name}` database!")
    else:
        await message.reply("⚠ Collect function is already running!")

@bot.on_message(filters.command("stopcollect") & filters.chat(TARGET_GROUP_ID) & filters.user([7508462500, 1710597756, 6895497681, 7435756663]))
async def stop_collect(_, message: Message):
    global collect_running
    collect_running = False
    await message.reply("🛑 Collect function stopped!")

@bot.on_message(filters.photo & filters.chat(TARGET_GROUP_ID) & filters.user([7522153272, 7946198415, 7742832624, 1710597756, 7828242164, 7957490622]))
async def hacke(c: Client, m: Message):
    """Handles image messages and collects OG players."""
    global collect_running
    if not collect_running:
        return

    try:
        await asyncio.sleep(random.uniform(0.2, 0.6))  # More randomized delay

        if not m.caption:
            return  # Ignore messages without captions

        logging.debug(f"Received caption: {m.caption}")

        if "🔥 ʟᴏᴏᴋ ᴀɴ ᴏɢ ᴘʟᴀʏᴇʀ" not in m.caption:
            return  # Ignore non-player messages

        file_id = m.photo.file_unique_id

        # Use cache for quick lookup
        if file_id in player_cache:
            player_name = player_cache[file_id]['name']
        else:
            file_data = current_db.get(file_id)  # Query database only if not in cache
            if file_data:
                player_name = file_data['name']
                player_cache[file_id] = file_data  # Cache result
            else:
                logging.warning(f"Image ID {file_id} not found in {current_db_name}!")
                return

        logging.info(f"Collecting player: {player_name} from {current_db_name}")
        sent_message = await bot.send_message(m.chat.id, f"/collect {player_name}")

        # Wait for bot's reply
        await asyncio.sleep(1)

        async for reply in bot.iter_history(m.chat.id, limit=5):
            if reply.reply_to_message and reply.reply_to_message.message_id == sent_message.message_id:
                if should_forward_message(reply.text):
                    await reply.forward(FORWARD_CHANNEL_ID)
                    logging.info(f"Forwarded message: {reply.text}")

    except FloodWait as e:
        wait_time = e.value + random.randint(1, 5)
        logging.warning(f"Rate limit hit! Waiting for {wait_time} seconds...")
        await asyncio.sleep(wait_time)
    except Exception as e:
        logging.error(f"Error processing message: {e}")

@bot.on_message(filters.chat(TARGET_GROUP_ID))
async def check_rarity_and_forward(_, message: Message):
    if not message.text:
        return  

    if "🎯 Look You Collected A" in message.text:
        logging.info(f"Checking message for rarity:\n{message.text}")

        for rarity in RARITIES_TO_FORWARD:
            if f"Rarity : {rarity}" in message.text:
                logging.info(f"Detected {rarity} celebrity! Forwarding...")
                await bot.send_message(FORWARD_CHANNEL_ID, message.text)
                break  

@bot.on_message(filters.command("fileid") & filters.chat(TARGET_GROUP_ID) & filters.reply & filters.user([7508462500, 1710597756, 6895497681, 7435756663]))
async def extract_file_id(_, message: Message):
    """Extracts and sends the unique file ID of a replied photo."""
    if not message.reply_to_message or not message.reply_to_message.photo:
        await message.reply("⚠ Please reply to a photo to extract the file ID.")
        return
    
    file_unique_id = message.reply_to_message.photo.file_unique_id
    await message.reply(f"📂 **File Unique ID:** `{file_unique_id}`")

async def main():
    """ Runs Pyrogram bot and Flask server concurrently """
    preload_players()  # Load players into memory before starting
    await bot.start()
    logging.info("Bot started successfully!")
    await asyncio.gather(run_flask(), idle())
    await bot.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
