"""Comprehensive test suite for Phase 12 Evaluation & Regression System."""

import pytest
import yaml
import tempfile
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import Mock, MagicMock, patch

from agent_engine.schemas import (
    Assertion,
    AssertionType,
    AssertionResult,
    EvaluationCase,
    EvaluationResult,
    EvaluationStatus,
    EvaluationSuite,
    ArtifactType,
)
from agent_engine.evaluation_loader import load_evaluations_manifest, parse_evaluations
from agent_engine.runtime.evaluator import Evaluator, _get_nested_value
from agent_engine.exceptions import ManifestLoadError


# ===== Schema Tests (5 tests) =====

class TestEvaluationSchema:
    """Test evaluation schema definitions."""

    def test_assertion_creation_with_all_types(self):
        """Test Assertion can be created with all assertion types."""
        for assertion_type in AssertionType:
            assertion = Assertion(
                type=assertion_type,
                expected="test_value",
                field_path="result.output",
                message="Test message"
            )
            assert assertion.type == assertion_type
            assert assertion.expected == "test_value"
            assert assertion.field_path == "result.output"
            assert assertion.message == "Test message"

    def test_evaluation_case_creation(self):
        """Test EvaluationCase can be created with all fields."""
        assertions = [
            Assertion(type=AssertionType.STATUS, expected="success"),
            Assertion(type=AssertionType.EQUALS, field_path="result", expected="expected")
        ]
        case = EvaluationCase(
            id="test_case_1",
            description="Test case description",
            input={"key": "value"},
            assertions=assertions,
            tags=["regression", "critical"],
            enabled=True
        )
        assert case.id == "test_case_1"
        assert case.description == "Test case description"
        assert case.input == {"key": "value"}
        assert len(case.assertions) == 2
        assert case.tags == ["regression", "critical"]
        assert case.enabled is True

    def test_evaluation_suite_creation(self):
        """Test EvaluationSuite can be created."""
        case1 = EvaluationCase(id="case1", description="Case 1", input={})
        case2 = EvaluationCase(id="case2", description="Case 2", input={})
        suite = EvaluationSuite(
            name="Test Suite",
            description="Suite description",
            cases=[case1, case2],
            tags=["regression"]
        )
        assert suite.name == "Test Suite"
        assert suite.description == "Suite description"
        assert len(suite.cases) == 2
        assert suite.tags == ["regression"]

    def test_evaluation_result_creation(self):
        """Test EvaluationResult can be created."""
        assertion = Assertion(type=AssertionType.STATUS, expected="success")
        assertion_result = AssertionResult(
            assertion=assertion,
            status=EvaluationStatus.PASSED
        )
        result = EvaluationResult(
            case_id="test_case",
            case_description="Test case description",
            status=EvaluationStatus.PASSED,
            task_id="task_1",
            task_status="success",
            task_output={"result": "success"},
            assertion_results=[assertion_result],
            execution_time_ms=100.5,
            timestamp="2025-01-01T00:00:00+00:00"
        )
        assert result.case_id == "test_case"
        assert result.status == EvaluationStatus.PASSED
        assert result.execution_time_ms == 100.5

    def test_assertion_result_creation(self):
        """Test AssertionResult can be created."""
        assertion = Assertion(type=AssertionType.EQUALS, expected="value")
        result = AssertionResult(
            assertion=assertion,
            status=EvaluationStatus.PASSED,
            actual_value="value",
            error_message=""
        )
        assert result.assertion == assertion
        assert result.status == EvaluationStatus.PASSED
        assert result.actual_value == "value"


# ===== Loader Tests (5 tests) =====

class TestEvaluationLoader:
    """Test evaluation loader functionality."""

    def test_load_evaluations_manifest_with_valid_file(self):
        """Test loading valid evaluations.yaml file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            eval_data = {
                "suites": [
                    {
                        "name": "Test Suite",
                        "description": "Test suite description",
                        "cases": [
                            {
                                "id": "test_case",
                                "description": "Test case",
                                "input": {"key": "value"}
                            }
                        ]
                    }
                ]
            }
            eval_file = os.path.join(tmpdir, "evaluations.yaml")
            with open(eval_file, 'w') as f:
                yaml.dump(eval_data, f)

            loaded = load_evaluations_manifest(tmpdir)
            assert loaded is not None
            assert "suites" in loaded
            assert len(loaded["suites"]) == 1
            assert loaded["suites"][0]["name"] == "Test Suite"

    def test_load_evaluations_manifest_missing_file(self):
        """Test loading evaluations.yaml when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loaded = load_evaluations_manifest(tmpdir)
            assert loaded is None

    def test_parse_evaluations_with_complete_suite(self):
        """Test parsing complete evaluation suite."""
        data = {
            "suites": [
                {
                    "name": "Complete Suite",
                    "description": "Complete suite",
                    "tags": ["regression"],
                    "cases": [
                        {
                            "id": "case1",
                            "description": "Case 1",
                            "input": {"message": "hello"},
                            "assertions": [
                                {
                                    "type": "status",
                                    "expected": "success"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        suites = parse_evaluations(data)
        assert len(suites) == 1
        assert suites[0].name == "Complete Suite"
        assert len(suites[0].cases) == 1
        assert suites[0].cases[0].id == "case1"
        assert len(suites[0].cases[0].assertions) == 1

    def test_parse_evaluations_with_multiple_cases(self):
        """Test parsing multiple evaluation cases."""
        data = {
            "suites": [
                {
                    "name": "Multi-case Suite",
                    "cases": [
                        {
                            "id": "case1",
                            "description": "Case 1",
                            "input": {},
                            "enabled": True
                        },
                        {
                            "id": "case2",
                            "description": "Case 2",
                            "input": {"test": "data"},
                            "enabled": False
                        }
                    ]
                }
            ]
        }
        suites = parse_evaluations(data)
        assert len(suites[0].cases) == 2
        assert suites[0].cases[0].enabled is True
        assert suites[0].cases[1].enabled is False

    def test_parse_evaluations_with_assertions(self):
        """Test parsing assertions from YAML."""
        data = {
            "suites": [
                {
                    "name": "Suite with Assertions",
                    "cases": [
                        {
                            "id": "case1",
                            "description": "Case 1",
                            "input": {},
                            "assertions": [
                                {
                                    "type": "status",
                                    "expected": "success",
                                    "message": "Status check"
                                },
                                {
                                    "type": "equals",
                                    "field_path": "output.result",
                                    "expected": "test_result"
                                },
                                {
                                    "type": "contains",
                                    "field_path": "output.items",
                                    "expected": "item1"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        suites = parse_evaluations(data)
        case = suites[0].cases[0]
        assert len(case.assertions) == 3
        assert case.assertions[0].type == AssertionType.STATUS
        assert case.assertions[1].type == AssertionType.EQUALS
        assert case.assertions[2].type == AssertionType.CONTAINS


# ===== Evaluator Tests (10 tests) =====

class TestEvaluator:
    """Test Evaluator runtime functionality."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock engine."""
        engine = MagicMock()
        return engine

    @pytest.fixture
    def mock_artifact_store(self):
        """Create a mock artifact store."""
        store = MagicMock()
        return store

    @pytest.fixture
    def mock_telemetry(self):
        """Create a mock telemetry bus."""
        telemetry = MagicMock()
        return telemetry

    @pytest.fixture
    def evaluator(self, mock_engine, mock_artifact_store, mock_telemetry):
        """Create an evaluator with mocked dependencies."""
        return Evaluator(
            engine=mock_engine,
            artifact_store=mock_artifact_store,
            telemetry=mock_telemetry
        )

    def test_run_case_with_passing_assertions(self, evaluator, mock_engine):
        """Test running a case with all passing assertions."""
        mock_engine.run.return_value = {
            "task_id": "task_1",
            "status": "success",
            "output": {"result": "expected"}
        }

        case = EvaluationCase(
            id="case1",
            description="Test case",
            input={"test": "input"},
            assertions=[
                Assertion(type=AssertionType.STATUS, expected="success"),
                Assertion(type=AssertionType.EQUALS, field_path="result", expected="expected")
            ]
        )

        result = evaluator.run_case(case)
        assert result.status == EvaluationStatus.PASSED
        assert result.case_id == "case1"
        assert len(result.assertion_results) == 2
        assert all(ar.status == EvaluationStatus.PASSED for ar in result.assertion_results)

    def test_run_case_with_failing_assertions(self, evaluator, mock_engine):
        """Test running a case with failing assertions."""
        mock_engine.run.return_value = {
            "task_id": "task_1",
            "status": "failure",
            "output": {"result": "different"}
        }

        case = EvaluationCase(
            id="case1",
            description="Test case",
            input={"test": "input"},
            assertions=[
                Assertion(type=AssertionType.STATUS, expected="success"),
                Assertion(type=AssertionType.EQUALS, field_path="result", expected="expected")
            ]
        )

        result = evaluator.run_case(case)
        assert result.status == EvaluationStatus.FAILED
        assert result.assertion_results[0].status == EvaluationStatus.FAILED
        assert result.assertion_results[1].status == EvaluationStatus.FAILED

    def test_status_assertion_check(self, evaluator, mock_engine):
        """Test STATUS assertion type."""
        mock_engine.run.return_value = {
            "task_id": "task_1",
            "status": "success",
            "output": {}
        }

        case = EvaluationCase(
            id="case1",
            description="Status check",
            input={},
            assertions=[
                Assertion(type=AssertionType.STATUS, expected="success")
            ]
        )

        result = evaluator.run_case(case)
        assert result.assertion_results[0].status == EvaluationStatus.PASSED
        assert result.assertion_results[0].actual_value == "success"

    def test_equals_assertion_check(self, evaluator, mock_engine):
        """Test EQUALS assertion type."""
        mock_engine.run.return_value = {
            "task_id": "task_1",
            "status": "success",
            "output": {"result": "expected_value"}
        }

        case = EvaluationCase(
            id="case1",
            description="Equals check",
            input={},
            assertions=[
                Assertion(type=AssertionType.EQUALS, field_path="result", expected="expected_value")
            ]
        )

        result = evaluator.run_case(case)
        assert result.assertion_results[0].status == EvaluationStatus.PASSED

    def test_contains_assertion_check_string(self, evaluator, mock_engine):
        """Test CONTAINS assertion type with string."""
        mock_engine.run.return_value = {
            "task_id": "task_1",
            "status": "success",
            "output": {"message": "hello world"}
        }

        case = EvaluationCase(
            id="case1",
            description="Contains check",
            input={},
            assertions=[
                Assertion(type=AssertionType.CONTAINS, field_path="message", expected="world")
            ]
        )

        result = evaluator.run_case(case)
        assert result.assertion_results[0].status == EvaluationStatus.PASSED

    def test_contains_assertion_check_list(self, evaluator, mock_engine):
        """Test CONTAINS assertion type with list."""
        mock_engine.run.return_value = {
            "task_id": "task_1",
            "status": "success",
            "output": {"items": ["a", "b", "c"]}
        }

        case = EvaluationCase(
            id="case1",
            description="Contains check",
            input={},
            assertions=[
                Assertion(type=AssertionType.CONTAINS, field_path="items", expected="b")
            ]
        )

        result = evaluator.run_case(case)
        assert result.assertion_results[0].status == EvaluationStatus.PASSED

    def test_schema_valid_assertion_check(self, evaluator, mock_engine):
        """Test SCHEMA_VALID assertion type."""
        mock_engine.run.return_value = {
            "task_id": "task_1",
            "status": "success",
            "output": {"data": "value"}
        }

        case = EvaluationCase(
            id="case1",
            description="Schema check",
            input={},
            assertions=[
                Assertion(type=AssertionType.SCHEMA_VALID)
            ]
        )

        result = evaluator.run_case(case)
        assert result.assertion_results[0].status == EvaluationStatus.PASSED

    def test_nested_field_path_extraction(self, evaluator, mock_engine):
        """Test nested field path extraction."""
        mock_engine.run.return_value = {
            "task_id": "task_1",
            "status": "success",
            "output": {
                "result": {
                    "nested": {
                        "value": "deep"
                    }
                }
            }
        }

        case = EvaluationCase(
            id="case1",
            description="Nested field check",
            input={},
            assertions=[
                Assertion(type=AssertionType.EQUALS, field_path="result.nested.value", expected="deep")
            ]
        )

        result = evaluator.run_case(case)
        assert result.assertion_results[0].status == EvaluationStatus.PASSED

    def test_disabled_case_returns_skipped(self, evaluator):
        """Test disabled case returns SKIPPED status."""
        case = EvaluationCase(
            id="case1",
            description="Disabled case",
            input={},
            enabled=False
        )

        result = evaluator.run_case(case)
        assert result.status == EvaluationStatus.SKIPPED

    def test_error_handling_in_run_case(self, evaluator, mock_engine):
        """Test error handling returns ERROR status."""
        mock_engine.run.side_effect = Exception("Engine error")

        case = EvaluationCase(
            id="case1",
            description="Case with error",
            input={}
        )

        result = evaluator.run_case(case)
        assert result.status == EvaluationStatus.ERROR
        assert "Engine error" in result.error_message

    def test_execution_time_recording(self, evaluator, mock_engine):
        """Test execution time is recorded in milliseconds."""
        import time

        def slow_run(*args, **kwargs):
            time.sleep(0.05)  # 50ms
            return {"task_id": "task_1", "status": "success", "output": {}}

        mock_engine.run.side_effect = slow_run

        case = EvaluationCase(
            id="case1",
            description="Timed case",
            input={}
        )

        result = evaluator.run_case(case)
        assert result.execution_time_ms >= 50  # At least 50ms


# ===== Helper Function Tests =====

class TestHelperFunctions:
    """Test helper functions."""

    def test_get_nested_value_simple(self):
        """Test _get_nested_value with simple path."""
        obj = {"a": 1}
        assert _get_nested_value(obj, "a") == 1

    def test_get_nested_value_nested(self):
        """Test _get_nested_value with nested path."""
        obj = {"a": {"b": {"c": 3}}}
        assert _get_nested_value(obj, "a.b.c") == 3

    def test_get_nested_value_empty_path(self):
        """Test _get_nested_value with empty path returns object."""
        obj = {"a": 1}
        assert _get_nested_value(obj, "") == obj

    def test_get_nested_value_missing_key(self):
        """Test _get_nested_value with missing key returns None."""
        obj = {"a": 1}
        assert _get_nested_value(obj, "b") is None

    def test_get_nested_value_non_dict(self):
        """Test _get_nested_value with non-dict returns None."""
        obj = {"a": "string"}
        assert _get_nested_value(obj, "a.b") is None


# ===== Integration Tests (5+ tests) =====

class TestEvaluatorIntegration:
    """Test evaluator integration with engine."""

    @pytest.fixture
    def mock_engine_with_store(self):
        """Create a mock engine with artifact store."""
        engine = MagicMock()
        artifact_store = MagicMock()
        telemetry = MagicMock()
        return engine, artifact_store, telemetry

    def test_evaluation_result_stored_in_artifact_store(self, mock_engine_with_store):
        """Test evaluation result is stored in artifact store."""
        engine, artifact_store, telemetry = mock_engine_with_store
        engine.run.return_value = {
            "task_id": "task_1",
            "status": "success",
            "output": {}
        }

        evaluator = Evaluator(
            engine=engine,
            artifact_store=artifact_store,
            telemetry=telemetry
        )

        case = EvaluationCase(
            id="case1",
            description="Test case",
            input={}
        )

        evaluator.run_case(case)
        artifact_store.store_artifact.assert_called_once()
        call_args = artifact_store.store_artifact.call_args
        assert call_args[1]["artifact_type"] == ArtifactType.TELEMETRY_SNAPSHOT

    def test_telemetry_event_emitted_on_completion(self, mock_engine_with_store):
        """Test telemetry event is emitted on evaluation completion."""
        engine, artifact_store, telemetry = mock_engine_with_store
        engine.run.return_value = {
            "task_id": "task_1",
            "status": "success",
            "output": {}
        }

        evaluator = Evaluator(
            engine=engine,
            artifact_store=artifact_store,
            telemetry=telemetry
        )

        case = EvaluationCase(
            id="case1",
            description="Test case",
            input={}
        )

        evaluator.run_case(case)
        telemetry.emit_event.assert_called_once()
        call_args = telemetry.emit_event.call_args
        assert call_args[0][0] == "evaluation_completed"

    def test_run_suite_with_multiple_cases(self, mock_engine_with_store):
        """Test run_suite executes multiple cases."""
        engine, artifact_store, telemetry = mock_engine_with_store
        engine.run.return_value = {
            "task_id": "task_1",
            "status": "success",
            "output": {}
        }

        evaluator = Evaluator(
            engine=engine,
            artifact_store=artifact_store,
            telemetry=telemetry
        )

        cases = [
            EvaluationCase(id=f"case{i}", description=f"Case {i}", input={})
            for i in range(3)
        ]

        results = evaluator.run_suite(cases)
        assert len(results) == 3
        assert all(r.status == EvaluationStatus.PASSED for r in results)

    def test_engine_load_evaluations(self):
        """Test Engine.load_evaluations() loads suites from config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            eval_data = {
                "suites": [
                    {
                        "name": "Test Suite",
                        "cases": [
                            {
                                "id": "case1",
                                "description": "Test case",
                                "input": {}
                            }
                        ]
                    }
                ]
            }
            eval_file = os.path.join(tmpdir, "evaluations.yaml")
            with open(eval_file, 'w') as f:
                yaml.dump(eval_data, f)

            # Mock Engine to test load_evaluations method
            from agent_engine.engine import Engine
            with patch.object(Engine, '__init__', lambda x, **kwargs: None):
                engine = Engine()
                engine.config_dir = tmpdir

                suites = engine.load_evaluations()
                assert len(suites) == 1
                assert suites[0].name == "Test Suite"

    def test_engine_create_evaluator(self):
        """Test Engine.create_evaluator() creates evaluator instance."""
        from agent_engine.engine import Engine
        with patch.object(Engine, '__init__', lambda x, **kwargs: None):
            engine = Engine()
            engine.artifact_store = MagicMock()
            engine.telemetry = MagicMock()

            evaluator = engine.create_evaluator()
            assert isinstance(evaluator, Evaluator)
            assert evaluator.engine == engine
            assert evaluator.artifact_store == engine.artifact_store
            assert evaluator.telemetry == engine.telemetry

    def test_evaluation_timestamp_is_utc(self, mock_engine_with_store):
        """Test evaluation result timestamp is UTC ISO-8601."""
        engine, artifact_store, telemetry = mock_engine_with_store
        engine.run.return_value = {
            "task_id": "task_1",
            "status": "success",
            "output": {}
        }

        evaluator = Evaluator(engine=engine)

        case = EvaluationCase(id="case1", description="Test case", input={})
        result = evaluator.run_case(case)

        # Verify timestamp format
        assert result.timestamp
        # Try to parse as ISO format
        datetime.fromisoformat(result.timestamp.replace('Z', '+00:00'))

    def test_contains_assertion_with_dict(self, mock_engine_with_store):
        """Test CONTAINS assertion with dict."""
        engine, artifact_store, telemetry = mock_engine_with_store
        engine.run.return_value = {
            "task_id": "task_1",
            "status": "success",
            "output": {"data": {"key1": "value1", "key2": "value2"}}
        }

        evaluator = Evaluator(engine=engine)

        case = EvaluationCase(
            id="case1",
            description="Dict contains check",
            input={},
            assertions=[
                Assertion(type=AssertionType.CONTAINS, field_path="data", expected="key1")
            ]
        )

        result = evaluator.run_case(case)
        assert result.assertion_results[0].status == EvaluationStatus.PASSED

    def test_multiple_assertions_one_fails(self, mock_engine_with_store):
        """Test case with multiple assertions where one fails."""
        engine, artifact_store, telemetry = mock_engine_with_store
        engine.run.return_value = {
            "task_id": "task_1",
            "status": "success",
            "output": {"result": "actual"}
        }

        evaluator = Evaluator(engine=engine)

        case = EvaluationCase(
            id="case1",
            description="Mixed assertions",
            input={},
            assertions=[
                Assertion(type=AssertionType.STATUS, expected="success"),
                Assertion(type=AssertionType.EQUALS, field_path="result", expected="expected")
            ]
        )

        result = evaluator.run_case(case)
        assert result.status == EvaluationStatus.FAILED
        assert result.assertion_results[0].status == EvaluationStatus.PASSED
        assert result.assertion_results[1].status == EvaluationStatus.FAILED
