"""Loading config.json, with and without COO's campaign list.

Split out of ``helpers_pkg/config.py`` on 2026-11-17 to keep it under the
200-line limit. ``helpers_pkg.config`` re-exports all three functions.
"""

import json

from helpers_pkg.constants import CONFIG_PATH


def load_raw_config(path=None) -> dict:
    """config.json exactly as written, with no COO overlay.

    ⛔ Anything that writes config.json back MUST read it with this, or
    COO's campaign names and topic ids would be baked into the file.
    """
    with open(path or CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def with_coo_campaigns(config: dict) -> dict:
    """``config`` with COO's campaign list laid over ``topic_pairs``.

    COO is fetched once per process (``coo_campaigns.coo_campaigns``); any
    failure returns ``config`` unchanged. Imported here, not at the top,
    because ``coo_campaigns`` pulls in ``combat`` and ``helpers_pkg.config``
    imports this module.
    """
    from helpers_pkg import coo_campaigns
    from helpers_pkg.config import validate_config
    return coo_campaigns.apply(config, validate_config)


def load_config() -> dict:
    """The config every run uses: config.json plus COO's campaign list.

    COO is the source of truth for which campaigns exist and their
    Telegram topics (2026-11-17). See ``helpers_pkg/coo_campaigns.py``.
    """
    return with_coo_campaigns(load_raw_config())
