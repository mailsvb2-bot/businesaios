from __future__ import annotations

import os

# Repository test runs disable third-party plugin autoload for hermeticity.
# Load only the required async plugin in that mode. With normal autoload enabled,
# leave registration to pytest so the plugin is not registered twice.
pytest_plugins = (
    ("pytest_asyncio.plugin",)
    if os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") == "1"
    else ()
)
