"""Cliente assíncrono da API do Mercado Livre.

Autentica com client_credentials (token de aplicação), renova o token
automaticamente antes de expirar e expõe os endpoints usados pelo bot.

Com token de aplicação, /sites/{site}/search e /items/{id} retornam 403.
Por isso os produtos vêm do catálogo:
  /highlights/{site}/category/{cat}  -> IDs dos mais vendidos
  /products/{id}                     -> nome, fotos
  /products/{id}/items               -> anúncios com preço e preço original
"""

import asyncio
import logging
import time
from dataclasses import dataclass

import httpx

from .config import MLConfig

log = logging.getLogger(__name__)

API_URL = "https://api.mercadolibre.com"
TOKEN_URL = f"{API_URL}/oauth/token"
PRODUCT_PAGE_URL = "https://www.mercadolivre.com.br/p/{product_id}"
# Renova o token um pouco antes de expirar para evitar 401 no meio de uma requisição.
TOKEN_MARGIN_SECONDS = 300


def format_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class MLApiError(Exception):
    def __init__(self, status: int, url: str, body: str):
        super().__init__(f"HTTP {status} em {url}: {body[:300]}")
        self.status = status
        self.url = url


@dataclass
class Product:
    id: str
    title: str
    price: float
    original_price: float | None
    permalink: str
    image: str
    free_shipping: bool = False
    coupon: str | None = None  # ex.: "Cupom R$ 6,00 OFF"
    item_id: str | None = None  # anúncio (MLB-...), quando conhecido

    @property
    def discount_percent(self) -> int:
        if not self.original_price or self.original_price <= self.price:
            return 0
        return round((1 - self.price / self.original_price) * 100)


class MercadoLivreClient:
    def __init__(self, config: MLConfig):
        self.config = config
        self._http = httpx.AsyncClient(base_url=API_URL, timeout=20)
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()

    async def __aenter__(self) -> "MercadoLivreClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        await self._http.aclose()

    # ---------- autenticação ----------

    async def _get_token(self) -> str:
        async with self._token_lock:
            if self._token and time.time() < self._token_expires_at:
                return self._token

            log.info("Solicitando novo access token do Mercado Livre")
            resp = await self._http.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                },
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                raise MLApiError(resp.status_code, TOKEN_URL, resp.text)

            data = resp.json()
            self._token = data["access_token"]
            self._token_expires_at = time.time() + data.get("expires_in", 21600) - TOKEN_MARGIN_SECONDS
            return self._token

    async def _get(self, path: str, params: dict | None = None, retry_auth: bool = True) -> dict:
        token = await self._get_token()
        resp = await self._http.get(path, params=params, headers={"Authorization": f"Bearer {token}"})

        if resp.status_code == 401 and retry_auth:
            # Token revogado/expirado antes do previsto: força renovação e tenta de novo.
            self._token = None
            return await self._get(path, params, retry_auth=False)
        if resp.status_code != 200:
            raise MLApiError(resp.status_code, str(resp.url), resp.text)
        return resp.json()

    # ---------- endpoints ----------

    async def get_categories(self) -> list[dict]:
        return await self._get(f"/sites/{self.config.site_id}/categories")

    async def get_highlights(self, category_id: str) -> list[str]:
        """IDs de produtos de catálogo mais vendidos de uma categoria."""
        data = await self._get(f"/highlights/{self.config.site_id}/category/{category_id}")
        return [entry["id"] for entry in data.get("content", []) if entry.get("type") == "PRODUCT"]

    async def get_product(self, product_id: str) -> Product | None:
        """Monta o produto com a oferta mais barata (novo). None se não houver anúncios ativos."""
        info = await self._get(f"/products/{product_id}")
        try:
            listings = (await self._get(f"/products/{product_id}/items"))["results"]
        except MLApiError as e:
            if e.status == 404:  # produto sem anúncios ativos
                return None
            raise

        listings = [i for i in listings if i.get("condition") == "new"] or listings
        if not listings:
            return None
        best = min(listings, key=lambda i: i["price"])

        pictures = info.get("pictures") or []
        return Product(
            id=product_id,
            title=info["name"],
            price=float(best["price"]),
            original_price=best.get("original_price"),
            permalink=PRODUCT_PAGE_URL.format(product_id=product_id),
            image=pictures[0]["url"] if pictures else "",
            free_shipping=bool((best.get("shipping") or {}).get("free_shipping")),
        )
