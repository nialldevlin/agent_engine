"""Evolution and scoring hooks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class FitnessScore:
    successes: int = 0
    failures: int = 0

    @property
    def fitness(self) -> float:
        total = self.successes + self.failures
        return self.successes / total if total else 0.0


class EvolutionTracker:
    def __init__(self) -> None:
        self.scores: Dict[str, FitnessScore] = {}

    def record_success(self, agent_id: str) -> None:
        self.scores.setdefault(agent_id, FitnessScore()).successes += 1

    def record_failure(self, agent_id: str) -> None:
        self.scores.setdefault(agent_id, FitnessScore()).failures += 1

    def get_score(self, agent_id: str) -> float:
        return self.scores.get(agent_id, FitnessScore()).fitness
