"""Evaluation runtime for Phase 12 Evaluation & Regression System."""

from datetime import datetime
from zoneinfo import ZoneInfo
import time
from typing import Any, List, Optional

from agent_engine.schemas import (
    EvaluationCase,
    EvaluationResult,
    EvaluationStatus,
    AssertionResult,
    Assertion,
    AssertionType,
    ArtifactType,
    UniversalStatus
)


def _get_nested_value(obj: Any, path: str) -> Any:
    """Get value from nested object using dot-separated path.

    Example: _get_nested_value({"a": {"b": 5}}, "a.b") -> 5
    """
    if not path:
        return obj

    parts = path.split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


class Evaluator:
    """Runs evaluation cases against the engine and records results."""

    def __init__(self, engine, artifact_store=None, telemetry=None):
        """Initialize evaluator.

        Args:
            engine: Engine instance to run evaluations against
            artifact_store: Optional artifact store for recording results
            telemetry: Optional telemetry bus for event emission
        """
        self.engine = engine
        self.artifact_store = artifact_store
        self.telemetry = telemetry

    def run_case(self, case: EvaluationCase) -> EvaluationResult:
        """Run a single evaluation case.

        Args:
            case: Evaluation case to run

        Returns:
            EvaluationResult with pass/fail status
        """
        if not case.enabled:
            return EvaluationResult(
                case_id=case.id,
                case_description=case.description,
                status=EvaluationStatus.SKIPPED,
                timestamp=datetime.now(ZoneInfo("UTC")).isoformat()
            )

        start_time = time.time()

        try:
            # Run the workflow through the engine
            result = self.engine.run(case.input, start_node_id=case.start_node_id)

            execution_time_ms = (time.time() - start_time) * 1000

            # Extract task information
            task_id = result.get("task_id", "")
            task_status = result.get("status", "")
            task_output = result.get("output")

            # Run all assertions
            assertion_results = []
            overall_status = EvaluationStatus.PASSED

            for assertion in case.assertions:
                assertion_result = self._check_assertion(
                    assertion,
                    task_output,
                    task_status
                )
                assertion_results.append(assertion_result)

                if assertion_result.status == EvaluationStatus.FAILED:
                    overall_status = EvaluationStatus.FAILED

            eval_result = EvaluationResult(
                case_id=case.id,
                case_description=case.description,
                status=overall_status,
                task_id=task_id,
                task_status=task_status,
                task_output=task_output,
                assertion_results=assertion_results,
                execution_time_ms=execution_time_ms,
                timestamp=datetime.now(ZoneInfo("UTC")).isoformat()
            )

            # Store result in artifact store
            if self.artifact_store:
                self._store_result(eval_result)

            # Emit telemetry
            if self.telemetry:
                self._emit_telemetry(eval_result)

            return eval_result

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return EvaluationResult(
                case_id=case.id,
                case_description=case.description,
                status=EvaluationStatus.ERROR,
                error_message=str(e),
                execution_time_ms=execution_time_ms,
                timestamp=datetime.now(ZoneInfo("UTC")).isoformat()
            )

    def _check_assertion(
        self,
        assertion: Assertion,
        task_output: Any,
        task_status: str
    ) -> AssertionResult:
        """Check a single assertion against task output/status."""

        try:
            if assertion.type == AssertionType.STATUS:
                # Check task status
                actual_value = task_status
                passed = (actual_value == assertion.expected)

                return AssertionResult(
                    assertion=assertion,
                    status=EvaluationStatus.PASSED if passed else EvaluationStatus.FAILED,
                    actual_value=actual_value,
                    error_message="" if passed else f"Expected status '{assertion.expected}', got '{actual_value}'"
                )

            elif assertion.type == AssertionType.EQUALS:
                # Get value at field path
                actual_value = _get_nested_value(task_output, assertion.field_path or "")
                passed = (actual_value == assertion.expected)

                return AssertionResult(
                    assertion=assertion,
                    status=EvaluationStatus.PASSED if passed else EvaluationStatus.FAILED,
                    actual_value=actual_value,
                    error_message="" if passed else f"Expected {assertion.expected}, got {actual_value}"
                )

            elif assertion.type == AssertionType.CONTAINS:
                # Check if value contains expected
                actual_value = _get_nested_value(task_output, assertion.field_path or "")

                if isinstance(actual_value, str):
                    passed = (assertion.expected in actual_value)
                elif isinstance(actual_value, (list, tuple)):
                    passed = (assertion.expected in actual_value)
                elif isinstance(actual_value, dict):
                    passed = (assertion.expected in actual_value)
                else:
                    passed = False

                return AssertionResult(
                    assertion=assertion,
                    status=EvaluationStatus.PASSED if passed else EvaluationStatus.FAILED,
                    actual_value=actual_value,
                    error_message="" if passed else f"Expected value to contain {assertion.expected}"
                )

            elif assertion.type == AssertionType.SCHEMA_VALID:
                # For Phase 12, just check that output exists
                # Future phases can add actual schema validation
                actual_value = task_output
                passed = (task_output is not None)

                return AssertionResult(
                    assertion=assertion,
                    status=EvaluationStatus.PASSED if passed else EvaluationStatus.FAILED,
                    actual_value=actual_value,
                    error_message="" if passed else "Output is None"
                )

            else:
                # Unsupported assertion type
                return AssertionResult(
                    assertion=assertion,
                    status=EvaluationStatus.ERROR,
                    error_message=f"Unsupported assertion type: {assertion.type}"
                )

        except Exception as e:
            return AssertionResult(
                assertion=assertion,
                status=EvaluationStatus.ERROR,
                error_message=f"Assertion check failed: {str(e)}"
            )

    def _store_result(self, result: EvaluationResult):
        """Store evaluation result in artifact store."""
        self.artifact_store.store_artifact(
            task_id=result.task_id or f"eval_{result.case_id}",
            artifact_type=ArtifactType.TELEMETRY_SNAPSHOT,  # Use telemetry type for eval results
            payload={
                "case_id": result.case_id,
                "case_description": result.case_description,
                "status": result.status.value,
                "task_status": result.task_status,
                "task_output": result.task_output,
                "assertion_results": [
                    {
                        "type": ar.assertion.type.value,
                        "status": ar.status.value,
                        "actual_value": ar.actual_value,
                        "error_message": ar.error_message
                    }
                    for ar in result.assertion_results
                ],
                "execution_time_ms": result.execution_time_ms,
                "timestamp": result.timestamp
            },
            node_id=None,
            schema_ref=None,
            additional_metadata={
                "evaluation_case": result.case_id,
                "evaluation_status": result.status.value
            }
        )

    def _emit_telemetry(self, result: EvaluationResult):
        """Emit telemetry event for evaluation result."""
        self.telemetry.emit_event(
            "evaluation_completed",
            {
                "case_id": result.case_id,
                "status": result.status.value,
                "execution_time_ms": result.execution_time_ms
            }
        )

    def run_suite(self, cases: List[EvaluationCase]) -> List[EvaluationResult]:
        """Run multiple evaluation cases.

        Args:
            cases: List of evaluation cases to run

        Returns:
            List of evaluation results
        """
        results = []
        for case in cases:
            result = self.run_case(case)
            results.append(result)
        return results
