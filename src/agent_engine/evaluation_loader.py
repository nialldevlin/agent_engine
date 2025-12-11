"""Evaluation loader for Phase 12 evaluation framework."""

import os
import yaml
from typing import Dict, List
from agent_engine.schemas import EvaluationSuite, EvaluationCase, Assertion, AssertionType
from agent_engine.exceptions import ManifestLoadError


def load_evaluations_manifest(config_dir: str) -> Dict:
    """Load evaluations.yaml (optional).

    Returns:
        Dict with loaded evaluations, or None if file doesn't exist
    """
    path = os.path.join(config_dir, "evaluations.yaml")
    if not os.path.exists(path):
        return None

    try:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return data if data else None
    except yaml.YAMLError as e:
        raise ManifestLoadError("evaluations.yaml", f"Invalid YAML: {e}")
    except Exception as e:
        raise ManifestLoadError("evaluations.yaml", str(e))


def parse_evaluations(data: Dict) -> List[EvaluationSuite]:
    """Parse loaded evaluations YAML into EvaluationSuite objects.

    Expected format:
    suites:
      - name: "Basic Workflows"
        description: "Test basic workflow execution"
        tags: ["regression"]
        cases:
          - id: "simple_linear"
            description: "Simple linear workflow"
            input: {"message": "hello"}
            assertions:
              - type: "status"
                expected: "success"
              - type: "equals"
                field_path: "output.result"
                expected: "processed hello"
    """
    if not data or "suites" not in data:
        return []

    suites = []
    for suite_data in data["suites"]:
        cases = []
        for case_data in suite_data.get("cases", []):
            assertions = []
            for assertion_data in case_data.get("assertions", []):
                assertion = Assertion(
                    type=AssertionType(assertion_data["type"]),
                    expected=assertion_data.get("expected"),
                    field_path=assertion_data.get("field_path"),
                    custom_function=assertion_data.get("custom_function"),
                    message=assertion_data.get("message", "")
                )
                assertions.append(assertion)

            case = EvaluationCase(
                id=case_data["id"],
                description=case_data.get("description", ""),
                input=case_data["input"],
                start_node_id=case_data.get("start_node_id"),
                assertions=assertions,
                tags=case_data.get("tags", []),
                enabled=case_data.get("enabled", True)
            )
            cases.append(case)

        suite = EvaluationSuite(
            name=suite_data["name"],
            description=suite_data.get("description", ""),
            cases=cases,
            tags=suite_data.get("tags", [])
        )
        suites.append(suite)

    return suites
