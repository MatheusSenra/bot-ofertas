"""Formatação das mensagens do canal (HTML do Telegram)."""

from html import escape

from .mercadolivre import format_brl
from .ofertas import Offer

# Legenda de foto no Telegram aceita no máximo 1024 caracteres.
MAX_TITLE_LENGTH = 200


def format_offer(offer: Offer, link: str) -> str:
    p = offer.product
    title = p.title if len(p.title) <= MAX_TITLE_LENGTH else p.title[: MAX_TITLE_LENGTH - 1] + "…"

    header = "📉 <b>BAIXOU DE PREÇO!</b>" if offer.previous_price else "🔥 <b>OFERTA</b>"
    lines = [header, "", f"<b>{escape(title)}</b>", ""]

    if p.discount_percent:
        lines.append(f"<s>{format_brl(p.original_price)}</s>")
        lines.append(f"💰 <b>{format_brl(p.price)}</b>  ({p.discount_percent}% OFF)")
    else:
        lines.append(f"💰 <b>{format_brl(p.price)}</b>")
    if offer.previous_price:
        lines.append(f"📊 Da última vez que postamos: {format_brl(offer.previous_price)}")
    if p.coupon:
        lines.append(f"🎟️ {escape(p.coupon)}")
    if p.free_shipping:
        lines.append("🚚 Frete grátis")

    lines += ["", f'🛒 <a href="{escape(link)}">Comprar no Mercado Livre</a>']
    return "\n".join(lines)
