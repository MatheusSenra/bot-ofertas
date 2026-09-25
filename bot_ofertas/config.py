"""Carrega configurações do arquivo .env."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
load_dotenv(ROOT_DIR / ".env")

# Informática, Games, Brinquedos e Hobbies, Eletrônicos, Celulares
DEFAULT_CATEGORIES = "MLB1648,MLB1144,MLB1132,MLB1000,MLB1051"


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Variável {name} não definida no .env")
    return value


def _list(name: str, default: str = "") -> list[str]:
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


def _number(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    return float(value) if value else default


@dataclass(frozen=True)
class MLConfig:
    client_id: str
    client_secret: str
    site_id: str
    affiliate_tool: str
    affiliate_word: str
    list_urls: list[str]
    categories: list[str]

    @classmethod
    def from_env(cls) -> "MLConfig":
        return cls(
            client_id=_required("ML_CLIENT_ID"),
            client_secret=_required("ML_CLIENT_SECRET"),
            site_id=os.getenv("ML_SITE_ID", "MLB").strip() or "MLB",
            affiliate_tool=os.getenv("ML_AFFILIATE_TOOL", "").strip(),
            affiliate_word=os.getenv("ML_AFFILIATE_WORD", "").strip(),
            list_urls=_list("ML_LIST_URLS"),
            categories=_list("ML_CATEGORIES", DEFAULT_CATEGORIES),
        )


@dataclass(frozen=True)
class BotConfig:
    token: str
    channel_id: str
    admin_ids: set[int]
    interval_minutes: float
    repost_after_days: float
    repost_min_drop_percent: float
    repost_highlights_after_days: float

    @classmethod
    def from_env(cls) -> "BotConfig":
        return cls(
            token=_required("TELEGRAM_BOT_TOKEN"),
            channel_id=_required("TELEGRAM_CHANNEL_ID"),
            admin_ids={int(i) for i in _list("TELEGRAM_ADMIN_IDS")},
            interval_minutes=_number("POST_INTERVAL_MINUTES", 120),
            repost_after_days=_number("REPOST_AFTER_DAYS", 3),
            repost_min_drop_percent=_number("REPOST_MIN_DROP_PERCENT", 5),
            repost_highlights_after_days=_number("REPOST_HIGHLIGHTS_AFTER_DAYS", 7),
        )
