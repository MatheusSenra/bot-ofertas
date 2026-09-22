"""Escolhe o próximo produto a postar.

Ordem de prioridade:
1. Produto das suas listas que nunca foi postado (maior desconto primeiro).
2. Produto das listas postado há REPOST_AFTER_DAYS+ dias cujo preço caiu
   pelo menos REPOST_MIN_DROP_PERCENT desde o último post.
3. Mais vendido de uma categoria (alternando entre as categorias), nunca
   postado, preferindo os que têm desconto.
"""

import logging
from dataclasses import dataclass
from urllib.parse import unquote

from .affiliate import extract_item_id, is_short_link, unwrap_verification
from .config import BotConfig, MLConfig
from .lista import fetch_list, fetch_page, shared_product_from_page
from .mercadolivre import MercadoLivreClient, MLApiError, Product
from .storage import PostHistory

log = logging.getLogger(__name__)

SOURCE_LIST = "lista"
SOURCE_HIGHLIGHTS = "destaques"
SOURCE_MANUAL = "manual"
# Quantos mais vendidos avaliar por categoria (cada um custa 2 chamadas à API).
HIGHLIGHTS_SCAN_LIMIT = 10


@dataclass
class Offer:
    product: Product
    source: str
    previous_price: float | None = None  # preenchido quando é repost por queda de preço


async def _list_products(ml_config: MLConfig) -> list[Product]:
    products: list[Product] = []
    for url in ml_config.list_urls:
        try:
            products += await fetch_list(url)
        except Exception:
            log.exception("Falha ao ler a lista %s", url)
    return products


async def _from_lists(ml_config: MLConfig, bot_config: BotConfig, history: PostHistory) -> Offer | None:
    new, drops = [], []
    for p in await _list_products(ml_config):
        last = history.last_post(p.id)
        if last is None:
            new.append(p)
        elif last.age_days >= bot_config.repost_after_days:
            drop = (1 - p.price / last.price) * 100
            if drop >= bot_config.repost_min_drop_percent:
                drops.append((drop, p, last.price))

    if new:
        return Offer(max(new, key=lambda p: p.discount_percent), SOURCE_LIST)
    if drops:
        _, product, previous = max(drops, key=lambda d: d[0])
        return Offer(product, SOURCE_LIST, previous_price=previous)
    return None


async def _from_highlights(ml: MercadoLivreClient, ml_config: MLConfig, history: PostHistory) -> Offer | None:
    categories = ml_config.categories
    if not categories:
        return None
    # Alterna a categoria inicial a cada post para variar o conteúdo do canal.
    start = history.count_by_source(SOURCE_HIGHLIGHTS) % len(categories)

    for category in categories[start:] + categories[:start]:
        try:
            product_ids = await ml.get_highlights(category)
        except MLApiError as e:
            log.warning("Mais vendidos de %s indisponíveis: %s", category, e)
            continue

        fallback = None
        checked = 0
        for product_id in product_ids:
            if history.last_post(product_id) is not None:
                continue
            if checked >= HIGHLIGHTS_SCAN_LIMIT:
                break
            checked += 1
            try:
                product = await ml.get_product(product_id)
            except MLApiError as e:
                log.warning("Produto %s ignorado: %s", product_id, e)
                continue
            if product is None:
                continue
            if product.discount_percent:
                return Offer(product, SOURCE_HIGHLIGHTS)
            fallback = fallback or product
        if fallback:
            return Offer(fallback, SOURCE_HIGHLIGHTS)
    return None


async def next_offer(
    ml: MercadoLivreClient, ml_config: MLConfig, bot_config: BotConfig, history: PostHistory
) -> Offer | None:
    return await _from_lists(ml_config, bot_config, history) or await _from_highlights(ml, ml_config, history)


async def find_product_by_link(ml: MercadoLivreClient, ml_config: MLConfig, url: str) -> Product | None:
    """Produto de um link enviado pelo usuário (usado no /postar <link>).

    1. Link "compartilhar" de afiliado (meli.la): lê o produto do perfil social.
    2. Produto que está nas suas listas: usa os dados da lista.
    3. Link de catálogo (/p/MLB...): busca na API.
    """
    if is_short_link(url) or "/social/" in url:
        final_url, html = await fetch_page(url)
        if product := shared_product_from_page(final_url, html):
            return product
        url = unwrap_verification(final_url)

    item_id = extract_item_id(url)
    if not item_id:
        return None
    for product in await _list_products(ml_config):
        if item_id in (product.id, product.item_id):
            return product
    if "/p/" in unquote(url):
        return await ml.get_product(item_id)
    return None


async def affiliate_target(url: str) -> str:
    """Destino real de um link, para conversão em link de afiliado.

    Links curtos de afiliado (inclusive de outras pessoas) levam ao perfil social
    de quem compartilhou; nesse caso usamos o link do próprio produto.
    """
    if not (is_short_link(url) or "/social/" in url):
        return url
    final_url, html = await fetch_page(url)
    if product := shared_product_from_page(final_url, html):
        return product.permalink
    return unwrap_verification(final_url)
