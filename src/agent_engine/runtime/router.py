"""Router handles pipeline and stage transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from agent_engine.schemas import Stage, StageType, Pipeline, TaskSpec, WorkflowGraph


@dataclass
class Router:
    workflow: WorkflowGraph
    pipelines: Dict[str, Pipeline]
    stages: Dict[str, Stage]

    def choose_pipeline(self, task_spec: TaskSpec) -> Pipeline:
        # Simple heuristic: first pipeline supporting mode or first available
        for pipeline in self.pipelines.values():
            if not pipeline.allowed_modes or task_spec.mode.value in pipeline.allowed_modes:
                return pipeline
        return list(self.pipelines.values())[0]

    def next_stage(self, current_stage_id: Optional[str], pipeline: Pipeline, decision: Optional[dict] = None) -> Optional[str]:
        if current_stage_id is None:
            return pipeline.start_stage_ids[0] if pipeline.start_stage_ids else None
        outgoing = [e for e in self.workflow.edges if e.from_stage_id == current_stage_id]
        if not outgoing:
            return None

        # decision-based routing
        if decision:
            condition = decision.get("condition") or decision.get("route") or decision.get("next")
            if condition:
                for edge in outgoing:
                    if edge.condition == condition or edge.to_stage_id == condition:
                        return edge.to_stage_id
        # default: single edge or first
        return outgoing[0].to_stage_id

    def workflow_stage_lookup(self, stage_id: str) -> Stage:
        return self.stages[stage_id]
