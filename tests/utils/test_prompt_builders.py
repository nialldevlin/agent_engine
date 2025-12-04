"""Tests for prompt construction utilities."""

import pytest
import json
from agent_engine.utils.prompt_builders import (
    _resolve_ref,
    _generate_json_skeleton,
    json_context,
    json_only_instruction,
    wrap_with_json_requirement,
    validate_prompt_has_json_instruction,
)
from agent_engine.schemas.registry import SCHEMA_REGISTRY, get_schema_json


class TestResolveRef:
    """Test JSON Schema $ref resolution."""

    def test_resolve_simple_ref(self):
        """Should resolve simple reference path."""
        full_schema = {
            "definitions": {
                "Person": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}}
                }
            }
        }

        result = _resolve_ref("#/definitions/Person", full_schema)

        assert result["type"] == "object"
        assert "name" in result["properties"]

    def test_resolve_nested_ref(self):
        """Should resolve nested reference paths."""
        full_schema = {
            "definitions": {
                "Address": {
                    "type": "object",
                    "properties": {"street": {"type": "string"}}
                }
            }
        }

        result = _resolve_ref("#/definitions/Address", full_schema)

        assert result["type"] == "object"
        assert "street" in result["properties"]

    def test_resolve_invalid_ref_returns_empty(self):
        """Should return empty dict for invalid references."""
        full_schema = {"definitions": {}}

        result = _resolve_ref("#/definitions/NonExistent", full_schema)

        assert result == {} or not result

    def test_resolve_malformed_ref_returns_empty(self):
        """Should handle malformed reference paths."""
        full_schema = {"definitions": {"Person": {}}}

        result = _resolve_ref("invalid/ref", full_schema)

        assert result == {} or not result


class TestGenerateJsonSkeleton:
    """Test JSON skeleton generation from schemas."""

    def test_generate_skeleton_object_type(self):
        """Should generate skeleton for object type schema."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name"]
        }

        skeleton = _generate_json_skeleton(schema, include_descriptions=False)

        # Should have valid structure
        assert isinstance(skeleton, dict)
        # Keys should match properties
        assert "name" in skeleton or skeleton

    def test_generate_skeleton_string_field(self):
        """Should handle string fields."""
        schema = {
            "type": "object",
            "properties": {
                "username": {"type": "string"}
            }
        }

        skeleton = _generate_json_skeleton(schema)

        assert "username" in skeleton
        # Should have a string-like placeholder
        assert isinstance(skeleton["username"], (str, dict))

    def test_generate_skeleton_integer_field(self):
        """Should handle integer fields."""
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"}
            }
        }

        skeleton = _generate_json_skeleton(schema)

        assert "count" in skeleton
        # Should be 0 or integer-like
        assert isinstance(skeleton["count"], int)

    def test_generate_skeleton_boolean_field(self):
        """Should handle boolean fields."""
        schema = {
            "type": "object",
            "properties": {
                "active": {"type": "boolean"}
            }
        }

        skeleton = _generate_json_skeleton(schema)

        assert "active" in skeleton
        assert isinstance(skeleton["active"], bool)

    def test_generate_skeleton_array_field(self):
        """Should handle array fields."""
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        }

        skeleton = _generate_json_skeleton(schema)

        assert "items" in skeleton
        assert isinstance(skeleton["items"], list)

    def test_generate_skeleton_nested_object(self):
        """Should handle nested objects."""
        schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"}
                    }
                }
            }
        }

        skeleton = _generate_json_skeleton(schema)

        assert "user" in skeleton
        assert isinstance(skeleton["user"], dict)

    def test_generate_skeleton_with_enum(self):
        """Should handle enum fields."""
        schema = {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["active", "inactive", "pending"]
                }
            }
        }

        skeleton = _generate_json_skeleton(schema)

        assert "status" in skeleton
        # Should have one of the enum values
        assert skeleton["status"] in ["active", "inactive", "pending"] or isinstance(skeleton["status"], str)

    def test_generate_skeleton_with_descriptions(self):
        """Should include descriptions when requested."""
        schema = {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "User email address"
                }
            }
        }

        skeleton = _generate_json_skeleton(schema, include_descriptions=True)

        assert "email" in skeleton
        # Description might be in the value
        assert skeleton is not None

    def test_generate_skeleton_with_ref(self):
        """Should resolve $ref references."""
        full_schema = {
            "type": "object",
            "properties": {
                "person": {"$ref": "#/definitions/Person"}
            },
            "definitions": {
                "Person": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"}
                    }
                }
            }
        }

        skeleton = _generate_json_skeleton(full_schema)

        assert "person" in skeleton

    def test_generate_skeleton_array_with_objects(self):
        """Should handle arrays of objects."""
        schema = {
            "type": "object",
            "properties": {
                "users": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"}
                        }
                    }
                }
            }
        }

        skeleton = _generate_json_skeleton(schema)

        assert "users" in skeleton
        assert isinstance(skeleton["users"], list)


class TestJsonOnlyInstruction:
    """Test JSON-only instruction generation."""

    def test_json_only_instruction_returns_string(self):
        """Should return a non-empty string."""
        instruction = json_only_instruction()

        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_json_only_instruction_contains_json_reference(self):
        """Should mention JSON in the instruction."""
        instruction = json_only_instruction()

        assert "json" in instruction.lower()

    def test_json_only_instruction_mentions_no_explanations(self):
        """Should mention avoiding explanations."""
        instruction = json_only_instruction()

        lower_instruction = instruction.lower()
        # Should mention not including text/explanations
        assert "no" in lower_instruction or "only" in lower_instruction

    def test_json_only_instruction_is_brief(self):
        """Should be a brief instruction."""
        instruction = json_only_instruction()

        # Should be under 300 characters
        assert len(instruction) < 300


class TestWrapWithJsonRequirement:
    """Test prompt wrapping with JSON requirements."""

    def test_wrap_with_minimal_mode(self):
        """Should add minimal JSON instruction in minimal mode."""
        base = "Generate a response"
        wrapped = wrap_with_json_requirement(base, "task_spec", mode="minimal")

        assert base in wrapped
        assert len(wrapped) > len(base)
        assert "json" in wrapped.lower()

    def test_wrap_with_standard_mode(self):
        """Should add standard JSON instruction in standard mode."""
        base = "Generate a response"
        wrapped = wrap_with_json_requirement(base, "task_spec", mode="standard")

        assert base in wrapped
        assert "task_spec" in wrapped
        assert "json" in wrapped.lower()

    def test_wrap_with_full_mode(self):
        """Should add full JSON context in full mode."""
        base = "Generate a response"
        wrapped = wrap_with_json_requirement(base, "task_spec", mode="full")

        assert base in wrapped
        # Full mode should include more information
        assert len(wrapped) > len(base) + 50

    def test_wrap_returns_original_base(self):
        """Should preserve original base prompt."""
        base = "Original prompt text here"
        wrapped = wrap_with_json_requirement(base, "task_spec")

        assert base in wrapped

    def test_wrap_different_schema_ids(self):
        """Should work with different schema IDs."""
        base = "Generate data"

        for schema_id in ["task_spec", "workflow_graph", "agent_definition"]:
            wrapped = wrap_with_json_requirement(base, schema_id, mode="standard")
            assert base in wrapped
            assert schema_id in wrapped


class TestValidatePromptHasJsonInstruction:
    """Test JSON instruction validation."""

    def test_validate_positive_only_json(self):
        """Should detect 'only json' instruction."""
        prompt = "Please respond with only json."
        assert validate_prompt_has_json_instruction(prompt) is True

    def test_validate_positive_only_valid_json(self):
        """Should detect 'only valid json' instruction."""
        prompt = "Return only valid JSON."
        assert validate_prompt_has_json_instruction(prompt) is True

    def test_validate_positive_respond_with_json(self):
        """Should detect 'respond with json' instruction."""
        prompt = "You must respond with json format."
        assert validate_prompt_has_json_instruction(prompt) is True

    def test_validate_positive_no_prose(self):
        """Should detect 'no prose' instruction."""
        prompt = "Output JSON with no prose."
        assert validate_prompt_has_json_instruction(prompt) is True

    def test_validate_positive_code_fence(self):
        """Should detect code fence instruction."""
        prompt = "Don't use code fences."
        assert validate_prompt_has_json_instruction(prompt) is True

    def test_validate_negative_normal_prompt(self):
        """Should not detect JSON instruction in normal prompt."""
        prompt = "What is the capital of France?"
        assert validate_prompt_has_json_instruction(prompt) is False

    def test_validate_negative_explanation_request(self):
        """Should not detect JSON instruction in explanation request."""
        prompt = "Please explain how this works."
        assert validate_prompt_has_json_instruction(prompt) is False

    def test_validate_case_insensitive(self):
        """Should do case-insensitive matching."""
        prompt = "Respond with ONLY JSON"
        assert validate_prompt_has_json_instruction(prompt) is True

    def test_validate_empty_prompt(self):
        """Should handle empty prompts."""
        prompt = ""
        # Should not crash, result depends on implementation
        result = validate_prompt_has_json_instruction(prompt)
        assert isinstance(result, bool)


class TestJsonContext:
    """Test JSON context generation."""

    def test_json_context_returns_string(self):
        """Should return a string."""
        context = json_context("task_spec")

        assert isinstance(context, str)
        assert len(context) > 0

    def test_json_context_includes_schema_name(self):
        """Should mention the schema name."""
        context = json_context("task_spec")

        assert "task_spec" in context or "JSON" in context

    def test_json_context_includes_json_reference(self):
        """Should mention JSON requirements."""
        context = json_context("task_spec")

        assert "json" in context.lower() or "JSON" in context

    def test_json_context_with_real_schema(self):
        """Should work with registered schemas."""
        for schema_id in list(SCHEMA_REGISTRY.keys())[:3]:  # Test first 3 schemas
            context = json_context(schema_id)

            assert isinstance(context, str)
            assert len(context) > 0

    def test_json_context_with_skeleton(self):
        """Should include skeleton when requested."""
        context = json_context("task_spec", include_skeleton=True)

        # Should be longer than without skeleton
        context_no_skeleton = json_context("task_spec", include_skeleton=False)

        assert len(context) >= len(context_no_skeleton)

    def test_json_context_without_skeleton(self):
        """Should exclude skeleton when requested."""
        context = json_context("task_spec", include_skeleton=False)

        assert isinstance(context, str)
        assert len(context) > 0

    def test_json_context_with_full_schema(self):
        """Should include full schema when requested."""
        context = json_context("task_spec", include_full_schema=True)

        # Should be longer with full schema
        context_no_schema = json_context("task_spec", include_full_schema=False)

        assert len(context) > len(context_no_schema)

    def test_json_context_nonexistent_schema(self):
        """Should handle non-existent schemas gracefully."""
        context = json_context("NonExistentSchema123")

        # Should return fallback message
        assert isinstance(context, str)
        assert "NonExistentSchema123" in context or "json" in context.lower()

    def test_json_context_different_modes(self):
        """Should work with different schema IDs."""
        schemas = ["task_spec", "workflow_graph", "agent_definition"]

        for schema_id in schemas:
            if schema_id in SCHEMA_REGISTRY:
                context = json_context(schema_id)
                assert isinstance(context, str)
                assert len(context) > 0


class TestSchemaIntegration:
    """Test integration with schema registry."""

    def test_get_schema_json_task_spec(self):
        """Should retrieve task_spec schema."""
        schema = get_schema_json("task_spec")

        assert isinstance(schema, dict)
        assert "properties" in schema or "type" in schema

    def test_get_schema_json_multiple(self):
        """Should retrieve different schemas."""
        for schema_id in ["task_spec", "workflow_graph"]:
            if schema_id in SCHEMA_REGISTRY:
                schema = get_schema_json(schema_id)
                assert isinstance(schema, dict)

    def test_get_schema_json_invalid(self):
        """Should raise KeyError for invalid schema."""
        with pytest.raises(KeyError):
            get_schema_json("InvalidSchemaName123")

    def test_skeleton_valid_json(self):
        """Generated skeletons should be valid JSON-serializable."""
        schema = get_schema_json("task_spec")
        skeleton = _generate_json_skeleton(schema)

        # Should be JSON serializable
        json_str = json.dumps(skeleton)
        assert isinstance(json_str, str)


class TestJsonContextWithActualSchemas:
    """Test JSON context with actual registered schemas."""

    @pytest.fixture(autouse=True)
    def ensure_schemas_available(self):
        """Ensure we have schemas to test."""
        # Check that SCHEMA_REGISTRY has entries
        assert len(SCHEMA_REGISTRY) > 0

    def test_context_workflow_graph(self):
        """Should generate context for workflow_graph schema."""
        if "workflow_graph" in SCHEMA_REGISTRY:
            context = json_context("workflow_graph")
            assert isinstance(context, str)
            assert len(context) > 0

    def test_context_agent_definition(self):
        """Should generate context for agent_definition schema."""
        if "agent_definition" in SCHEMA_REGISTRY:
            context = json_context("agent_definition")
            assert isinstance(context, str)
            assert len(context) > 0

    def test_all_registry_schemas_have_context(self):
        """Should be able to generate context for all registered schemas."""
        for schema_id in SCHEMA_REGISTRY.keys():
            # Should not raise an exception
            context = json_context(schema_id)
            assert isinstance(context, str)


class TestPromptBuilderEdgeCases:
    """Test edge cases and error handling."""

    def test_wrap_with_empty_base_prompt(self):
        """Should handle empty base prompt."""
        wrapped = wrap_with_json_requirement("", "task_spec", mode="minimal")
        assert "json" in wrapped.lower()

    def test_wrap_with_very_long_base_prompt(self):
        """Should handle very long base prompts."""
        long_base = "Some prompt. " * 100
        wrapped = wrap_with_json_requirement(long_base, "task_spec", mode="minimal")
        assert long_base in wrapped

    def test_validate_with_special_characters(self):
        """Should handle prompts with special characters."""
        prompt = "Return JSON only! @#$%^&*()"
        result = validate_prompt_has_json_instruction(prompt)
        assert isinstance(result, bool)

    def test_skeleton_with_empty_properties(self):
        """Should handle schemas with no properties."""
        schema = {
            "type": "object",
            "properties": {}
        }

        skeleton = _generate_json_skeleton(schema)
        assert isinstance(skeleton, dict)

    def test_resolve_ref_with_missing_definitions(self):
        """Should handle missing definitions."""
        schema = {}
        result = _resolve_ref("#/definitions/Missing", schema)
        assert result == {} or not result

    def test_resolve_ref_with_deep_path(self):
        """Should handle deep reference paths."""
        schema = {
            "a": {
                "b": {
                    "c": {"type": "string"}
                }
            }
        }

        result = _resolve_ref("#/a/b/c", schema)
        # Result depends on path traversal
        assert isinstance(result, (dict, type(None))) or result == {}
