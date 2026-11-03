"""Plugin discovery and registration via Python packaging entry-points."""

import importlib.metadata
import logging
from typing import Any, Callable, Dict, List

logger = logging.getLogger("runport.plugins")

PLUGIN_GROUP = "runport.plugins"
TARGET_GROUP = "runport.targets"
SCORER_GROUP = "runport.scorers"


def discover_plugins(group: str = PLUGIN_GROUP) -> Dict[str, Any]:
    """Discover installed plugins registered under the given entry-point group."""
    discovered: Dict[str, Any] = {}
    try:
        eps = importlib.metadata.entry_points()
        # Python 3.12+ / 3.10+ entry_points select API
        if hasattr(eps, "select"):
            matches = eps.select(group=group)
        else:
            matches = eps.get(group, [])

        for ep in matches:
            try:
                plugin = ep.load()
                discovered[ep.name] = plugin
            except Exception as e:
                logger.warning(f"Failed to load entry-point plugin '{ep.name}': {e}")
    except Exception as e:
        logger.warning(f"Error querying entry points for group '{group}': {e}")
    return discovered


def load_plugin_targets() -> Dict[str, Any]:
    """Load targets provided by external plugins."""
    return discover_plugins(TARGET_GROUP)


def load_plugin_scorers() -> Dict[str, Any]:
    """Load custom statistical or heuristic scorers provided by external plugins."""
    return discover_plugins(SCORER_GROUP)

