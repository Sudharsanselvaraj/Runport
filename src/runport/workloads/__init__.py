"""Workloads package for Runport evaluation suites."""

from typing import Dict, Type

from runport.workloads.base import BaseWorkload
from runport.workloads.classification import ClassificationWorkload
from runport.workloads.extraction import ExtractionWorkload
from runport.workloads.generation import GenerationWorkload
from runport.workloads.rag import RAGWorkload

_WORKLOAD_REGISTRY: Dict[str, Type[BaseWorkload]] = {
    "classification": ClassificationWorkload,
    "extraction": ExtractionWorkload,
    "generation": GenerationWorkload,
    "rag": RAGWorkload,
}


def get_workload(name: str, **kwargs) -> BaseWorkload:
    """Retrieve an instantiated workload by task name."""
    clean = name.strip().lower()
    if clean not in _WORKLOAD_REGISTRY:
        raise KeyError(f"Unknown workload '{name}'. Available: {list(_WORKLOAD_REGISTRY.keys())}")
    return _WORKLOAD_REGISTRY[clean](**kwargs)


__all__ = [
    "BaseWorkload",
    "ClassificationWorkload",
    "ExtractionWorkload",
    "GenerationWorkload",
    "RAGWorkload",
    "get_workload",
]
