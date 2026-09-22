"""Leitura de listas públicas de recomendação do Mercado Livre.

Não há API oficial para listas. A página pública
(mercadolivre.com.br/social/<usuario>/lists/<id>) embute os produtos num
JSON "polycards", que já traz título, preço, desconto, cupom e imagem.
Se o ML mudar o formato da página, é aqui que o ajuste deve ser feito.
"""

import json
import logging
from urllib.parse import urlsplit

import httpx

from .mercadolivre import PRODUCT_PAGE_URL, Product, format_brl

log = logging.getLogger(__name__)

IMAGE_URL = "https://http2.mlstatic.com/D_NQ_NP_{picture_id}-F.jpg"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


class ListParseError(Exception):
    pass


def _render_text(component: dict) -> str:
    """Substitui os placeholders {chave} de um texto do polycard (ícones viram vazio)."""
    text = component.get("text", "")
    for value in component.get("values", []):
        if value.get("type") == "price":
            replacement = format_brl(value["price"]["value"])
        elif value.get("type") == "icon":
            replacement = ""
        else:
            replacement = str(value.get("text", ""))
        text = text.replace("{" + value["key"] + "}", replacement)
    return " ".join(text.split())


def _parse_card(card: dict) -> Product | None:
    meta = card["metadata"]
    comps = {c["type"]: c.get(c["type"]) for c in card.get("components", [])}
    price = comps.get("price") or {}
    current = (price.get("current_price") or {}).get("value")
    if not current or "title" not in comps:
        return None  # item indisponível ou sem preço

    product_id = meta.get("product_id") or meta["id"]
    url = meta.get("url")
    pictures = (card.get("pictures") or {}).get("pictures") or []
    coupons = [p for p in comps.get("promotions") or [] if p.get("type") == "coupon"]
    shipping = comps.get("shipping") or {}

    return Product(
        id=product_id,
        title=comps["title"]["text"],
        price=float(current),
        original_price=(price.get("previous_price") or {}).get("value"),
        permalink=f"https://{url}" if url else PRODUCT_PAGE_URL.format(product_id=product_id),
        image=IMAGE_URL.format(picture_id=pictures[0]["id"]) if pictures else "",
        # "additional_text" indica condição (ex.: "por ser sua primeira compra"); nesse caso não anunciamos.
        free_shipping="grátis" in (shipping.get("text") or "").lower() and not shipping.get("additional_text"),
        coupon=_render_text(coupons[0]) if coupons else None,
        item_id=meta.get("id"),
        badge=(comps.get("highlight") or {}).get("text"),
        discount_label=(price.get("discount_label") or {}).get("text"),
    )


def parse_list_html(html: str) -> list[Product]:
    marker = '"polycards":'
    start = html.find(marker)
    if start == -1:
        raise ListParseError("JSON 'polycards' não encontrado — a lista é pública? O layout mudou?")
    cards, _ = json.JSONDecoder().raw_decode(html[start + len(marker) :])

    products = []
    for card in cards:
        try:
            if product := _parse_card(card):
                products.append(product)
        except (KeyError, TypeError, ValueError) as e:
            log.warning("Card ignorado (%r): %s", e, card.get("metadata"))
    return products


async def fetch_page(url: str) -> tuple[str, str]:
    """Baixa a página seguindo redirecionamentos. Retorna (url final, html)."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=20, headers=HEADERS) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    return str(resp.url), resp.text


async def fetch_list(url: str) -> list[Product]:
    """Baixa a lista (aceita o link curto meli.la) e retorna os produtos disponíveis."""
    _, html = await fetch_page(url)
    return parse_list_html(html)


def shared_product_from_page(final_url: str, html: str) -> Product | None:
    """Produto de um link "compartilhar" de afiliado (meli.la/...).

    Esse link abre o perfil social do afiliado (/social/<usuario>?ref=...), cujo
    primeiro bloco "polycards" contém só o produto compartilhado. Retorna None se
    a página não for um perfil social (ex.: página de produto ou lista).
    """
    path = urlsplit(final_url).path
    if not path.startswith("/social/") or "/lists/" in path:
        return None
    products = parse_list_html(html)
    return products[0] if products else None
