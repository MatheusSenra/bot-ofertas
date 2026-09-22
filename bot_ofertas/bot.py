"""Bot do Telegram: posta ofertas no canal em intervalos e converte links no privado.

Uso:  python -m bot_ofertas.bot
"""

import logging
import time
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .affiliate import build_affiliate_link, is_ml_url
from .config import DATA_DIR, BotConfig, MLConfig
from .formatter import format_offer
from .mercadolivre import MercadoLivreClient
from .ofertas import SOURCE_MANUAL, Offer, affiliate_target, find_product_by_link, next_offer
from .storage import PostHistory

log = logging.getLogger(__name__)

# ---------- postagem no canal ----------


async def publish(context: ContextTypes.DEFAULT_TYPE, offer: Offer) -> None:
    ml_config: MLConfig = context.bot_data["ml_config"]
    bot_config: BotConfig = context.bot_data["bot_config"]

    p = offer.product
    link = build_affiliate_link(p.permalink, ml_config.affiliate_tool, ml_config.affiliate_word)
    caption = format_offer(offer, link)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Ver oferta", url=link)]])

    try:
        await context.bot.send_photo(
            bot_config.channel_id, photo=p.image, caption=caption, parse_mode=ParseMode.HTML, reply_markup=keyboard
        )
    except TelegramError as e:
        # O Telegram às vezes não consegue baixar a imagem; posta só o texto.
        log.warning("Falha ao enviar foto (%s); enviando só texto", e)
        await context.bot.send_message(
            bot_config.channel_id, caption, parse_mode=ParseMode.HTML, reply_markup=keyboard
        )

    context.bot_data["history"].record(p, offer.source)
    log.info("Postado [%s]: %s — R$ %.2f", offer.source, p.title, p.price)


async def post_offer(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Posta a próxima oferta no canal. Retorna False se não houver o que postar."""
    data = context.bot_data
    offer = await next_offer(data["ml"], data["ml_config"], data["bot_config"], data["history"])
    if offer is None:
        log.info("Nenhuma oferta nova para postar")
        return False
    await publish(context, offer)
    return True


async def scheduled_post(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await post_offer(context)
    except Exception:
        # Não deixa um erro (API fora do ar, layout mudou...) derrubar o loop.
        log.exception("Erro ao postar oferta")


# ---------- comandos ----------


def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    return update.effective_user.id in context.bot_data["bot_config"].admin_ids


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Olá! Me envie um link do Mercado Livre que eu devolvo com o link de afiliado.\n\n"
        f"Seu ID do Telegram: {update.effective_user.id}"
    )


async def cmd_postar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update, context):
        return
    if context.args:
        await _postar_link(update, context, context.args[0])
        return

    await update.message.reply_text("Buscando oferta…")
    try:
        posted = await post_offer(context)
    except Exception as e:
        log.exception("Erro no /postar")
        await update.message.reply_text(f"Erro: {e}")
        return
    await update.message.reply_text("Postado no canal ✅" if posted else "Nenhuma oferta nova encontrada.")


async def _postar_link(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    url = url if url.startswith("http") else f"https://{url}"
    if not is_ml_url(url):
        await update.message.reply_text("Esse não é um link do Mercado Livre.")
        return

    await update.message.reply_text("Lendo o produto…")
    try:
        product = await find_product_by_link(context.bot_data["ml"], context.bot_data["ml_config"], url)
        if product is None:
            await update.message.reply_text(
                "Não consegui ler esse produto. Use o link de compartilhar de afiliado "
                "(meli.la/...), ou adicione o produto à sua lista e mande o link de novo."
            )
            return
        await publish(context, Offer(product, SOURCE_MANUAL))
    except Exception as e:
        log.exception("Erro no /postar %s", url)
        await update.message.reply_text(f"Erro: {e}")
        return
    await update.message.reply_text(f"Postado no canal ✅\n{product.title}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update, context):
        return
    history: PostHistory = context.bot_data["history"]
    jobs = context.job_queue.get_jobs_by_name("postagem")
    next_run = jobs[0].next_t.astimezone().strftime("%d/%m %H:%M") if jobs and jobs[0].next_t else "?"

    lines = [f"Próxima postagem: {next_run}", "", "Últimos posts:"]
    for title, price, source, posted_at in history.recent(5):
        when = datetime.fromtimestamp(posted_at).strftime("%d/%m %H:%M")
        lines.append(f"• {when} [{source}] R$ {price:.2f} — {title[:50]}")
    if len(lines) == 3:
        lines.append("(nenhum ainda)")
    await update.message.reply_text("\n".join(lines))


# ---------- conversão de links no privado ----------


async def convert_links(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    ml_config: MLConfig = context.bot_data["ml_config"]

    urls = []
    for entity, text in message.parse_entities([MessageEntity.URL, MessageEntity.TEXT_LINK]).items():
        url = entity.url if entity.type == MessageEntity.TEXT_LINK else text
        urls.append(url if url.startswith("http") else f"https://{url}")

    ml_urls = [u for u in urls if is_ml_url(u)]
    if not ml_urls:
        await message.reply_text("Não encontrei nenhum link do Mercado Livre nessa mensagem.")
        return

    converted = []
    for url in ml_urls:
        try:
            url = await affiliate_target(url)
            converted.append(build_affiliate_link(url, ml_config.affiliate_tool, ml_config.affiliate_word))
        except Exception as e:
            log.warning("Falha ao converter %s: %s", url, e)
            converted.append(f"❌ Não consegui converter: {url}")

    await message.reply_text("\n\n".join(converted), disable_web_page_preview=len(converted) > 1)


# ---------- inicialização ----------


async def on_startup(app: Application) -> None:
    app.bot_data["ml"] = MercadoLivreClient(app.bot_data["ml_config"])
    me = await app.bot.get_me()
    log.info("Bot @%s iniciado. Postando em %s", me.username, app.bot_data["bot_config"].channel_id)


async def on_shutdown(app: Application) -> None:
    await app.bot_data["ml"].close()
    app.bot_data["history"].close()


def main() -> None:
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # evita logar a URL com o token do bot

    ml_config = MLConfig.from_env()
    bot_config = BotConfig.from_env()
    if not ml_config.affiliate_tool or not ml_config.affiliate_word:
        raise RuntimeError("Defina ML_AFFILIATE_TOOL e ML_AFFILIATE_WORD no .env")

    app = Application.builder().token(bot_config.token).post_init(on_startup).post_shutdown(on_shutdown).build()
    history = PostHistory(DATA_DIR / "historico.db")
    app.bot_data.update(ml_config=ml_config, bot_config=bot_config, history=history)

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("postar", cmd_postar))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, convert_links))

    # Retoma o ritmo a partir do último post, para que reiniciar o bot não gere post extra.
    interval = bot_config.interval_minutes * 60
    last = history.last_posted_at()
    first = max(10, interval - (time.time() - last)) if last else 10
    log.info("Próxima postagem em %.0f minutos", first / 60)
    app.job_queue.run_repeating(scheduled_post, interval=interval, first=first, name="postagem")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
