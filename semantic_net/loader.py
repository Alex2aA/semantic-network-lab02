"""Загрузка данных семантической сети из файлов хранилища."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

REQUIRED_FILES = ("nodes.json", "relations.json", "triples.json", "sources.json")


def load_json(path: Path):
    """Читает JSON-файл и возвращает его содержимое."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_raw(data_dir: Path = DATA_DIR) -> Dict[str, List]:
    """Возвращает «сырые» списки узлов, отношений, фактов и источников."""
    data_dir = Path(data_dir)
    missing = [f for f in REQUIRED_FILES if not (data_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            "Не найдены файлы данных: " + ", ".join(missing) + f" (каталог: {data_dir})"
        )
    return {
        "nodes": load_json(data_dir / "nodes.json"),
        "relations": load_json(data_dir / "relations.json"),
        "triples": load_json(data_dir / "triples.json"),
        "sources": load_json(data_dir / "sources.json"),
    }


def load_network(data_dir: Path = DATA_DIR):
    """Загружает семантическую сеть из файлов хранилища data/."""
    from .network import SemanticNetwork

    raw = load_raw(data_dir)
    return SemanticNetwork(
        nodes=raw["nodes"],
        relations=raw["relations"],
        triples=raw["triples"],
        sources=raw["sources"],
    )
