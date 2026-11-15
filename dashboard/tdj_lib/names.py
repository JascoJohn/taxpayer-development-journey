"""Names of the six stage tools and of the platform, read from config.yaml `names:` (Editing Pass 1, 2026-11-13): the single source of truth.

    from tdj_lib.names import N
    N.entry.swahili   -> "Ujumuishaji wa Kikodi"
    N.entry.english   -> "Taxpayer Targeting and Registration Tool"
    N.entry.full      -> "Ujumuishaji wa Kikodi (Taxpayer Targeting and Registration Tool)"
    N.platform.full   -> "Ngazi Platform (Jukwaa la Ngazi)"

The dashboard sits inside the repository (config.yaml is two folders up); nothing is typed here.
"""

import os
from types import SimpleNamespace

import yaml

_CONFIG = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "config.yaml"))


def _load():
    with open(_CONFIG, encoding="utf-8") as f:
        raw = yaml.safe_load(f)["names"]
    return SimpleNamespace(**{k: SimpleNamespace(**v) for k, v in raw.items()})


N = _load()
