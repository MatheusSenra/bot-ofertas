"""Geração de links de afiliado do Mercado Livre.

O ML não tem API para criar links de afiliado: o rastreamento é feito pelos
parâmetros matt_tool e matt_word (obtidos no portal de afiliados) anexados
ao link do produto.
"""

import re
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

# Captura MLB-1234567890 (anúncio) e MLB1234567890 (anúncio ou produto de catálogo em /p/).
ITEM_ID_RE = re.compile(r"\b(MLB)-?(\d{6,})\b", re.IGNORECASE)
SHORT_LINK_HOSTS = ("meli.la", "mercadolivre.com/sec/", "mercadolibre.com/sec/")
ML_DOMAINS = ("mercadolivre.com.br", "mercadolivre.com", "mercadolibre.com", "meli.la")
# Parâmetros de rastreamento de terceiros que removemos ao gerar o link.
TRACKING_PARAMS = {"matt_tool", "matt_word", "matt_source", "matt_campaign", "forceInApp", "ref", "tracking_id"}


def is_ml_url(url: str) -> bool:
    host = urlsplit(url).netloc.lower()
    return any(host == d or host.endswith("." + d) for d in ML_DOMAINS)


def is_short_link(url: str) -> bool:
    return any(host in url for host in SHORT_LINK_HOSTS)


def unwrap_verification(url: str) -> str:
    """O ML às vezes redireciona para /gz/account-verification?go=<url original>."""
    parts = urlsplit(url)
    if "account-verification" in parts.path:
        return dict(parse_qsl(parts.query)).get("go", url)
    return url


def extract_item_id(url: str) -> str | None:
    match = ITEM_ID_RE.search(unquote(url))
    return f"{match.group(1).upper()}{match.group(2)}" if match else None


def build_affiliate_link(url: str, tool: str, word: str) -> str:
    """Anexa matt_tool/matt_word ao link, removendo rastreamentos anteriores."""
    if not tool or not word:
        raise ValueError("Defina ML_AFFILIATE_TOOL e ML_AFFILIATE_WORD no .env")

    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k not in TRACKING_PARAMS]
    query += [("matt_tool", tool), ("matt_word", word)]
    # Remove o fragmento (#...) que costuma carregar dados de busca/posição.
    return urlunsplit((parts.scheme or "https", parts.netloc, parts.path, urlencode(query), ""))
