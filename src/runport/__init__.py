"""Runport: Universal open-source LLM, prompt, and workflow benchmarking platform."""

__version__ = "0.1.0"


def __getattr__(name: str):  # lazy, so importing runport stays cheap
    if name in ("benchmark", "plan", "execute", "approve_interactively", "approve_with_ci_token"):
        from runport import sdk

        return getattr(sdk, name)
    raise AttributeError(name)
