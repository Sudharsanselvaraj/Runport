"""Unit tests for plugin discovery and entry-points."""

from runport.core.plugins import discover_plugins, load_plugin_scorers, load_plugin_targets


def test_plugin_discovery_graceful_on_missing_or_empty():
    """Plugin discovery handles empty or missing entry point groups gracefully."""
    plugins = discover_plugins("nonexistent.group.12345")
    assert isinstance(plugins, dict)
    assert len(plugins) == 0


def test_load_plugin_targets_and_scorers():
    """Plugin targets and scorers query the entry points without crashing."""
    targets = load_plugin_targets()
    scorers = load_plugin_scorers()
    assert isinstance(targets, dict)
    assert isinstance(scorers, dict)

