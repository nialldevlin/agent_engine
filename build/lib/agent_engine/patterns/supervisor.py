"""Supervisor pattern utilities."""

from __future__ import annotations

from typing import Callable, Iterable, Any, Dict


def run_supervisor(
    tasks: Iterable[Any],
    worker_fn: Callable[[Any], Any],
    supervisor_fn: Callable[[Iterable[Any]], Dict[str, Any]],
) -> Dict[str, Any]:
    """Collect worker outputs and let supervisor adjudicate."""
    worker_outputs = [worker_fn(t) for t in tasks]
    return supervisor_fn(worker_outputs)
