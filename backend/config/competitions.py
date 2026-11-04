"""Validated competition rules shared by ingestion, ML and serving."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from zoneinfo import ZoneInfo


DEFAULT_PATH = Path(__file__).with_name("leagues.json")


@dataclass(frozen=True)
class Competition:
    slug: str
    name: str
    country: str
    timezone: str
    season_format: str
    rounds: int
    season_count: int
    early_fraction: float
    late_fraction: float
    winter_months: tuple[int, ...]
    providers: dict[str, int]

    def __post_init__(self):
        if not isinstance(self.slug, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,49}", self.slug):
            raise ValueError("Invalid competition slug")
        if self.season_format not in {"calendar_year", "cross_year"}:
            raise ValueError("Invalid season format")
        if any(type(value) is not int or value < 1 for value in (self.rounds, self.season_count)):
            raise ValueError("rounds and season_count must be positive integers")
        if not 0 < self.early_fraction < self.late_fraction < 1:
            raise ValueError("Invalid season-stage fractions")
        ZoneInfo(self.timezone)

    def as_dict(self) -> dict:
        return asdict(self)

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.feature_rules, sort_keys=True).encode()).hexdigest()

    @property
    def feature_rules(self) -> dict:
        return {key: value for key, value in self.as_dict().items() if key not in {"name", "country", "providers", "season_count"}}

    def season(self, value: str) -> tuple[str, int, int]:
        """Normalize provider season labels without assuming every season crosses years."""
        match = re.fullmatch(r"(\d{4}|\d{2})(?:[/-](\d{2}|\d{4}))?", str(value).strip())
        if not match:
            raise ValueError(f"Invalid season label: {value!r}")
        start = int(match[1])
        if len(match[1]) == 2:
            start += 2000 if start < 90 else 1900
        end = start if self.season_format == "calendar_year" else start + 1
        if match[2]:
            given_end = int(match[2])
            if len(match[2]) == 2:
                given_end += (end // 100) * 100
            if given_end != end:
                raise ValueError(f"Season {value!r} does not match {self.season_format}")
        name = str(start) if start == end else f"{start}/{end}"
        return name, start, end


def competitions(path: str | Path | None = None) -> dict[str, Competition]:
    data = json.loads(Path(path or os.getenv("LEAGUE_CONFIG_PATH") or DEFAULT_PATH).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise ValueError("Competition configuration must be a nonempty mapping")
    result = {}
    for slug, fields in data.items():
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,49}", slug):
            raise ValueError("Competition slugs must use lowercase letters, digits and underscores")
        if not isinstance(fields, dict):
            raise ValueError(f"Competition {slug} must be a mapping")
        item = Competition(slug=slug, **fields)
        ZoneInfo(item.timezone)
        if not item.name.strip() or not item.country.strip():
            raise ValueError(f"Competition {slug} requires name and country")
        if item.season_format not in {"calendar_year", "cross_year"}:
            raise ValueError(f"Invalid season format for {slug}")
        if any(type(n) is not int or n < 1 for n in (item.rounds, item.season_count)):
            raise ValueError("rounds and season_count must be positive integers")
        if not 0 < item.early_fraction < item.late_fraction < 1:
            raise ValueError("Season stage fractions must satisfy 0 < early < late < 1")
        if any(type(n) is not int or not 1 <= n <= 12 for n in item.winter_months):
            raise ValueError("Winter months must be integers in [1, 12]")
        if not isinstance(item.providers, dict) or any(
            not isinstance(name, str) or type(identifier) is not int or identifier <= 0
            for name, identifier in item.providers.items()
        ):
            raise ValueError("Provider tournament IDs must be positive integers")
        result[slug] = item
    return result


def get_competition(slug: str | None = None, path: str | Path | None = None) -> Competition:
    key = slug or os.getenv("LEAGUE", "epl")
    available = competitions(path)
    if key not in available:
        raise ValueError(f"Unknown competition {key!r}; configured: {', '.join(available)}")
    return available[key]


def competition_id(session, competition: Competition) -> int:
    from sqlalchemy import text

    value = session.execute(text('SELECT id FROM "Leagues" WHERE slug = :slug'), {"slug": competition.slug}).scalar_one_or_none()
    if value is None:
        raise ValueError(f"No data has been ingested for competition {competition.slug}")
    return int(value)
