"""Formatação das mensagens do canal (HTML do Telegram)."""

from html import escape

from .mercadolivre import format_brl
from .ofertas import Offer

# Legenda de foto no Telegram aceita no máximo 1024 caracteres.
MAX_TITLE_LENGTH = 200
# Selos do Mercado Livre -> emoji. Selos desconhecidos usam 🏷️.
BADGE_EMOJIS = {"RELÂMPAGO": "⚡", "OFERTA DO DIA": "📅", "MAIS VENDIDO": "🏆", "NOVIDADE": "🆕"}
# Selos de ofertas que expiram: avisamos que o preço é temporário.
TEMPORARY_BADGES = ("RELÂMPAGO", "OFERTA DO DIA")


def _badge_line(badge: str) -> str:
    upper = badge.upper()
    emoji = next((e for key, e in BADGE_EMOJIS.items() if key in upper), "🏷️")
    line = f"{emoji} <b>{escape(upper)}</b>"
    if any(key in upper for key in TEMPORARY_BADGES):
        line += "  ⏳ por tempo limitado"
    return line


def format_offer(offer: Offer, link: str) -> str:
    p = offer.product
    title = p.title if len(p.title) <= MAX_TITLE_LENGTH else p.title[: MAX_TITLE_LENGTH - 1] + "…"

    header = []
    if offer.previous_price:
        header.append("📉 <b>BAIXOU DE PREÇO!</b>")
    if p.badge:
        header.append(_badge_line(p.badge))
    lines = [*(header or ["🔥 <b>OFERTA</b>"]), "", f"<b>{escape(title)}</b>", ""]

    if p.discount_percent:
        # Prefere o texto do ML, que diz quando o desconto é só no Pix.
        discount = p.discount_label or f"{p.discount_percent}% OFF"
        lines.append(f"<s>{format_brl(p.original_price)}</s>")
        lines.append(f"💰 <b>{format_brl(p.price)}</b>  ({escape(discount)})")
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
