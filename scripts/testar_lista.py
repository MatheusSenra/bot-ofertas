"""Testa a leitura de listas de recomendação do Mercado Livre.

Uso:  python -m scripts.testar_lista [URL ...]   (padrão: ML_LIST_URLS do .env)
"""

import asyncio
import sys

from bot_ofertas.affiliate import build_affiliate_link
from bot_ofertas.config import MLConfig
from bot_ofertas.lista import fetch_list


async def main() -> None:
    config = MLConfig.from_env()
    urls = sys.argv[1:] or config.list_urls
    if not urls:
        print("Passe a URL da lista ou defina ML_LIST_URLS no .env")
        return

    for url in urls:
        products = await fetch_list(url)
        print(f"{url} -> {len(products)} produtos\n")
        for p in products:
            print(f"  {p.title}")
            line = f"  R$ {p.price:.2f}"
            if p.discount_percent:
                line += f"  (de R$ {p.original_price:.2f}, -{p.discount_percent}%)"
            if p.free_shipping:
                line += "  | frete grátis"
            if p.coupon:
                line += f"  | {p.coupon}"
            print(line)
            print(f"  Imagem: {p.image}")
            print(f"  Link: {build_affiliate_link(p.permalink, config.affiliate_tool, config.affiliate_word)}\n")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
