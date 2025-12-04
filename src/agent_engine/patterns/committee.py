"""Committee pattern utilities."""

from __future__ import annotations

from typing import Callable, Iterable, List, Any


def run_committee(work_items: Iterable[Any], worker_fn: Callable[[Any], Any], merge_fn: Callable[[List[Any]], Any]) -> Any:
    """Run multiple workers and merge outputs."""
    outputs = [worker_fn(item) for item in work_items]
    return merge_fn(outputs)
