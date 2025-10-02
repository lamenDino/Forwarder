import os
import logging
import asyncio
from aiohttp import web
from telegram import Update, ChatMember, ChatMemberUpdated
from telegram.ext import (
    Application, ContextTypes, CommandHandler, ChatMemberHandler, MessageHandler, filters
)
import threading

# Caricamento env in locale (su Render non serve dotenv)
TOKEN = os.getenv("TELEGRAM_BOTTOKEN")
PORT = int(os.getenv("PORT", "10000"))

if not TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOTTOKEN non trovato nelle ENV")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Memoria canali per gruppo e last update
group_channels = {}
lastupdateid_per_channel = {}
CHECKINTERVAL = 30 * 60

# Handler bot (start, ask_channel, handle_channel_response, check_bot_added)...
# [Inserire qui le funzioni già definite in precedenza]

async def forwardloop(application: Application):
    while True:
        try:
            bot = application.bot
            for group_id, channel_username in group_channels.items():
                last_update_id = lastupdateid_per_channel.get(channel_username, 0)
                updates = await bot.get_updates(offset=last_update_id + 1, timeout=10)
                for u in updates:
                    lastupdateid_per_channel[channel_username] = u.update_id
                    if u.channel_post and u.channel_post.chat.username == channel_username:
                        await bot.forward_message(
                            chat_id=group_id,
                            from_chat_id=u.channel_post.chat.id,
                            message_id=u.channel_post.message_id
                        )
            await asyncio.sleep(CHECKINTERVAL)
        except Exception as e:
            logger.error(f"Errore nel loop forwarding: {e}")
            await asyncio.sleep(CHECKINTERVAL)

def start_forwarding(application):
    asyncio.run(forwardloop(application))

async def health(request):
    return web.Response(text="ok")

def main():
    application = Application.builder().token(TOKEN).build()

    # Registrazione handler (start, ChatMemberHandler, MessageHandler)...
    # [Come prima]

    # Avvio del loop di forwarding in thread
    threading.Thread(target=start_forwarding, args=(application,), daemon=True).start()

    # Configurazione server aiohttp per health check
    app = web.Application()
    app.add_routes([web.get('/healthz', health)])

    # Avvia insieme bot e HTTP server
    # il bot gira in polling in foreground
    runner = web.AppRunner(app)
    asyncio.get_event_loop().run_until_complete(runner.setup())
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    asyncio.get_event_loop().run_until_complete(site.start())

    logger.info(f"Health endpoint listening on 0.0.0.0:{PORT}")
    application.run_polling()

if __name__ == "__main__":
    main()
