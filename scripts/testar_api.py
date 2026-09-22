"""Diagnóstico da conexão com a API do Mercado Livre.

Uso:  python -m scripts.testar_api [CATEGORIA]   (padrão: MLB1051 = Celulares)

Testa autenticação e os endpoints de catálogo usados pelo bot, e mostra
alguns produtos já com preço, desconto e link de afiliado.
"""

import asyncio
import sys

from bot_ofertas.affiliate import build_affiliate_link
from bot_ofertas.config import MLConfig
from bot_ofertas.mercadolivre import MercadoLivreClient, MLApiError

DEFAULT_CATEGORY = "MLB1051"
SAMPLE_SIZE = 3


async def check(name: str, coro):
    try:
        result = await coro
        print(f"[OK]   {name}")
        return result
    except MLApiError as e:
        print(f"[FAIL] {name} -> HTTP {e.status}")
    except Exception as e:  # noqa: BLE001 - diagnóstico: queremos ver qualquer erro
        print(f"[FAIL] {name} -> {e!r}")
    return None


async def main() -> None:
    config = MLConfig.from_env()
    category = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CATEGORY

    async with MercadoLivreClient(config) as ml:
        if not await check("Autenticação (client_credentials)", ml._get_token()):
            print("\nSem token não dá para seguir. Confira ML_CLIENT_ID e ML_CLIENT_SECRET.")
            return

        await check("Categorias do site", ml.get_categories())
        product_ids = await check(f"Mais vendidos ({category})", ml.get_highlights(category))
        if not product_ids:
            return

        for product_id in product_ids[:SAMPLE_SIZE]:
            product = await check(f"Produto de catálogo ({product_id})", ml.get_product(product_id))
            if not product:
                continue
            print(f"  {product.title}")
            price = f"  R$ {product.price:.2f}"
            if product.discount_percent:
                price += f"  (de R$ {product.original_price:.2f}, -{product.discount_percent}%)"
            if product.free_shipping:
                price += "  | frete grátis"
            print(price)
            print(f"  Imagem: {product.image}")
            if config.affiliate_tool and config.affiliate_word:
                print(f"  Link: {build_affiliate_link(product.permalink, config.affiliate_tool, config.affiliate_word)}")
            else:
                print(f"  Link (sem afiliado — defina ML_AFFILIATE_TOOL/WORD): {product.permalink}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
