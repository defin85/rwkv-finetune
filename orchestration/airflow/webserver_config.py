"""Project-level Airflow webserver overrides.

This file extends Airflow's default FAB config with local runtime tweaks:
- explicit RATELIMIT_STORAGE_URI to avoid noisy in-memory limiter warning;
- suppress Marshmallow v4 migration warnings emitted by Airflow 2.10 stack.
"""

from __future__ import annotations

import os
import warnings

from airflow.config_templates.default_webserver_config import *  # noqa: F401,F403

try:
    from marshmallow.warnings import ChangedInMarshmallow4Warning
except Exception:  # pragma: no cover - marshmallow API may differ across versions
    ChangedInMarshmallow4Warning = None

if ChangedInMarshmallow4Warning is not None:
    warnings.filterwarnings("ignore", category=ChangedInMarshmallow4Warning)

# Explicit storage URI removes Flask-Limiter startup warning.
RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
