"""Phase 14 Security & Policy Layer tests."""

import pytest
import tempfile
from pathlib import Path

from agent_engine.schemas import PolicyAction, PolicyTarget, PolicyRule, PolicySet
from agent_engine.policy_loader import load_policy_manifest, parse_policies
from agent_engine.runtime.policy_evaluator import PolicyEvaluator
from agent_engine.telemetry import TelemetryBus


# ============================================================================
# SCHEMA TESTS (3 tests)
# ============================================================================
class TestPolicySchemas:
    """Test policy schema definitions."""

    def test_policy_action_enum(self):
        """Test PolicyAction enum values."""
        assert PolicyAction.ALLOW.value == "allow"
        assert PolicyAction.DENY.value == "deny"
        assert len(PolicyAction) == 2

    def test_policy_target_enum(self):
        """Test PolicyTarget enum values."""
        assert PolicyTarget.TOOL.value == "tool"
        assert PolicyTarget.CONTEXT.value == "context"
        assert PolicyTarget.NODE.value == "node"
        assert len(PolicyTarget) == 3

    def test_policy_rule_creation(self):
        """Test PolicyRule creation and dict conversion."""
        rule = PolicyRule(
            target=PolicyTarget.TOOL,
            target_id="dangerous_tool",
            action=PolicyAction.DENY,
            reason="Tool is dangerous"
        )
        assert rule.target == PolicyTarget.TOOL
        assert rule.target_id == "dangerous_tool"
        assert rule.action == PolicyAction.DENY
        assert rule.reason == "Tool is dangerous"

        rule_dict = rule.dict()
        assert rule_dict["target"] == "tool"
        assert rule_dict["action"] == "deny"
        assert rule_dict["target_id"] == "dangerous_tool"

    def test_policy_set_creation(self):
        """Test PolicySet creation."""
        rules = [
            PolicyRule(PolicyTarget.TOOL, "tool1", PolicyAction.DENY, "Dangerous"),
            PolicyRule(PolicyTarget.TOOL, "tool2", PolicyAction.ALLOW),
        ]
        policy_set = PolicySet(
            name="restrictive",
            rules=rules,
            enabled=True
        )
        assert policy_set.name == "restrictive"
        assert len(policy_set.rules) == 2
        assert policy_set.enabled is True

        policy_dict = policy_set.dict()
        assert policy_dict["name"] == "restrictive"
        assert len(policy_dict["rules"]) == 2

    def test_policy_set_default_enabled(self):
        """Test PolicySet defaults enabled to True."""
        policy_set = PolicySet(name="default_policy")
        assert policy_set.enabled is True
        assert policy_set.rules == []


# ============================================================================
# LOADER TESTS (3 tests)
# ============================================================================
class TestPolicyLoader:
    """Test policy loader functionality."""

    def test_load_policy_manifest_with_valid_file(self):
        """Test loading policy manifest from valid YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            policy_path = Path(tmpdir) / "policy.yaml"
            policy_path.write_text("""
policies:
  - name: "default"
    enabled: true
    rules:
      - target: "tool"
        target_id: "dangerous_tool"
        action: "deny"
        reason: "Tool is restricted"
""")
            data = load_policy_manifest(tmpdir)
            assert data is not None
            assert "policies" in data
            assert len(data["policies"]) == 1
            assert data["policies"][0]["name"] == "default"

    def test_load_policy_manifest_with_missing_file(self):
        """Test loading policy manifest when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data = load_policy_manifest(tmpdir)
            assert data is None

    def test_parse_policies_with_valid_data(self):
        """Test parsing valid policy data."""
        data = {
            "policies": [
                {
                    "name": "restrictive",
                    "enabled": True,
                    "rules": [
                        {
                            "target": "tool",
                            "target_id": "tool1",
                            "action": "deny",
                            "reason": "Dangerous"
                        },
                        {
                            "target": "tool",
                            "target_id": "tool2",
                            "action": "allow",
                            "reason": ""
                        }
                    ]
                }
            ]
        }
        policy_sets = parse_policies(data)
        assert len(policy_sets) == 1
        assert policy_sets[0].name == "restrictive"
        assert len(policy_sets[0].rules) == 2

    def test_parse_policies_with_none_data(self):
        """Test parsing None data returns empty list."""
        policy_sets = parse_policies(None)
        assert policy_sets == []

    def test_parse_policies_with_missing_name(self):
        """Test parsing policy without name raises ValueError."""
        data = {
            "policies": [
                {
                    "enabled": True,
                    "rules": []
                }
            ]
        }
        with pytest.raises(ValueError, match="must have a 'name' field"):
            parse_policies(data)

    def test_parse_policies_with_invalid_fields(self):
        """Test parsing rule with missing required fields raises ValueError."""
        data = {
            "policies": [
                {
                    "name": "policy",
                    "rules": [
                        {
                            "target": "tool",
                            # Missing target_id and action
                        }
                    ]
                }
            ]
        }
        with pytest.raises(ValueError, match="must have"):
            parse_policies(data)

    def test_parse_policies_with_invalid_enum_values(self):
        """Test parsing with invalid enum values raises ValueError."""
        data = {
            "policies": [
                {
                    "name": "policy",
                    "rules": [
                        {
                            "target": "invalid_target",
                            "target_id": "tool1",
                            "action": "deny"
                        }
                    ]
                }
            ]
        }
        with pytest.raises(ValueError, match="Invalid policy field"):
            parse_policies(data)


# ============================================================================
# EVALUATOR TESTS (6 tests)
# ============================================================================
class TestPolicyEvaluator:
    """Test policy evaluator functionality."""

    def test_evaluator_allows_tool_with_no_rules(self):
        """Test evaluator allows tool when no deny rules exist."""
        evaluator = PolicyEvaluator([])
        allowed, reason = evaluator.check_tool_allowed("any_tool")
        assert allowed is True
        assert reason == ""

    def test_evaluator_denies_tool_with_deny_rule(self):
        """Test evaluator denies tool when deny rule matches."""
        rule = PolicyRule(
            target=PolicyTarget.TOOL,
            target_id="dangerous_tool",
            action=PolicyAction.DENY,
            reason="Too dangerous"
        )
        policy_set = PolicySet(name="restrictive", rules=[rule])
        evaluator = PolicyEvaluator([policy_set])

        allowed, reason = evaluator.check_tool_allowed("dangerous_tool")
        assert allowed is False
        assert "Too dangerous" in reason

    def test_evaluator_allows_tool_not_in_rules(self):
        """Test evaluator allows tool not mentioned in rules."""
        rule = PolicyRule(
            target=PolicyTarget.TOOL,
            target_id="restricted_tool",
            action=PolicyAction.DENY
        )
        policy_set = PolicySet(name="policy", rules=[rule])
        evaluator = PolicyEvaluator([policy_set])

        allowed, reason = evaluator.check_tool_allowed("allowed_tool")
        assert allowed is True

    def test_evaluator_with_multiple_rules(self):
        """Test evaluator with multiple rules in same policy."""
        rules = [
            PolicyRule(PolicyTarget.TOOL, "tool1", PolicyAction.DENY, "Dangerous"),
            PolicyRule(PolicyTarget.TOOL, "tool2", PolicyAction.DENY, "Unsafe"),
            PolicyRule(PolicyTarget.TOOL, "tool3", PolicyAction.ALLOW),  # Allow rule (not used)
        ]
        policy_set = PolicySet(name="multi_rule", rules=rules)
        evaluator = PolicyEvaluator([policy_set])

        # Check denied tools
        allowed1, _ = evaluator.check_tool_allowed("tool1")
        assert allowed1 is False

        allowed2, _ = evaluator.check_tool_allowed("tool2")
        assert allowed2 is False

        # Check allowed tool
        allowed3, _ = evaluator.check_tool_allowed("other_tool")
        assert allowed3 is True

    def test_evaluator_with_multiple_policy_sets(self):
        """Test evaluator with multiple policy sets."""
        set1 = PolicySet(
            name="policy1",
            rules=[PolicyRule(PolicyTarget.TOOL, "tool1", PolicyAction.DENY)]
        )
        set2 = PolicySet(
            name="policy2",
            rules=[PolicyRule(PolicyTarget.TOOL, "tool2", PolicyAction.DENY)]
        )
        evaluator = PolicyEvaluator([set1, set2])

        # Both rules should be checked
        allowed1, _ = evaluator.check_tool_allowed("tool1")
        allowed2, _ = evaluator.check_tool_allowed("tool2")
        allowed3, _ = evaluator.check_tool_allowed("tool3")

        assert allowed1 is False
        assert allowed2 is False
        assert allowed3 is True

    def test_evaluator_ignores_disabled_policies(self):
        """Test evaluator ignores disabled policy sets."""
        rule = PolicyRule(
            target=PolicyTarget.TOOL,
            target_id="restricted_tool",
            action=PolicyAction.DENY
        )
        # Create disabled policy
        policy_set = PolicySet(name="disabled", rules=[rule], enabled=False)
        evaluator = PolicyEvaluator([policy_set])

        # Tool should be allowed since policy is disabled
        allowed, reason = evaluator.check_tool_allowed("restricted_tool")
        assert allowed is True

    def test_evaluator_default_deny_reason(self):
        """Test evaluator provides default reason when none specified."""
        rule = PolicyRule(
            target=PolicyTarget.TOOL,
            target_id="tool1",
            action=PolicyAction.DENY
            # No reason provided
        )
        policy_set = PolicySet(name="policy", rules=[rule])
        evaluator = PolicyEvaluator([policy_set])

        allowed, reason = evaluator.check_tool_allowed("tool1")
        assert allowed is False
        assert "tool1" in reason
        assert "denied by policy" in reason.lower()


# ============================================================================
# INTEGRATION TESTS (3 tests)
# ============================================================================
class TestPolicyIntegration:
    """Test policy integration with telemetry."""

    def test_policy_evaluator_emits_denial_event(self):
        """Test policy evaluator emits telemetry event on denial."""
        telemetry = TelemetryBus()
        rule = PolicyRule(
            target=PolicyTarget.TOOL,
            target_id="bad_tool",
            action=PolicyAction.DENY,
            reason="Security risk"
        )
        policy_set = PolicySet(name="security", rules=[rule])
        evaluator = PolicyEvaluator([policy_set], telemetry)

        allowed, _ = evaluator.check_tool_allowed("bad_tool", task_id="task-1")

        assert allowed is False
        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.payload["event"] == "policy_denied"
        assert event.payload["target"] == "bad_tool"
        assert "Security risk" in event.payload["reason"]

    def test_policy_evaluator_no_event_on_allow(self):
        """Test policy evaluator doesn't emit event on allow."""
        telemetry = TelemetryBus()
        evaluator = PolicyEvaluator([], telemetry)

        allowed, _ = evaluator.check_tool_allowed("good_tool")

        assert allowed is True
        assert len(telemetry.events) == 0

    def test_policy_yaml_integration(self):
        """Test full integration: load YAML, parse, evaluate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            policy_path = Path(tmpdir) / "policy.yaml"
            policy_path.write_text("""
policies:
  - name: "restricted"
    enabled: true
    rules:
      - target: "tool"
        target_id: "rm"
        action: "deny"
        reason: "Dangerous file operation"
      - target: "tool"
        target_id: "dangerous_exec"
        action: "deny"
        reason: "Code execution risk"
""")

            # Load and parse
            data = load_policy_manifest(tmpdir)
            policy_sets = parse_policies(data)

            # Evaluate
            telemetry = TelemetryBus()
            evaluator = PolicyEvaluator(policy_sets, telemetry)

            # Check restricted tools
            allowed_rm, reason_rm = evaluator.check_tool_allowed("rm")
            assert allowed_rm is False
            assert "Dangerous file operation" in reason_rm

            allowed_exec, reason_exec = evaluator.check_tool_allowed("dangerous_exec")
            assert allowed_exec is False
            assert "Code execution risk" in reason_exec

            # Check allowed tool
            allowed_safe, _ = evaluator.check_tool_allowed("safe_tool")
            assert allowed_safe is True

            # Check telemetry events
            assert len(telemetry.events) == 2


# ============================================================================
# EDGE CASES AND ROBUSTNESS TESTS (3+ tests)
# ============================================================================
class TestPolicyEdgeCases:
    """Test edge cases and robustness."""

    def test_policy_with_empty_rules_list(self):
        """Test policy set with empty rules list."""
        policy_set = PolicySet(name="empty", rules=[])
        evaluator = PolicyEvaluator([policy_set])

        # Should allow anything with empty rules
        allowed, _ = evaluator.check_tool_allowed("any_tool")
        assert allowed is True

    def test_policy_rule_with_non_tool_target_ignored(self):
        """Test evaluator ignores non-TOOL target rules."""
        rule = PolicyRule(
            target=PolicyTarget.CONTEXT,  # Not TOOL
            target_id="context1",
            action=PolicyAction.DENY
        )
        policy_set = PolicySet(name="context_policy", rules=[rule])
        evaluator = PolicyEvaluator([policy_set])

        # Tool should be allowed since the rule is for CONTEXT, not TOOL
        allowed, _ = evaluator.check_tool_allowed("any_tool")
        assert allowed is True

    def test_policy_check_with_empty_task_id(self):
        """Test policy check works with empty task ID."""
        rule = PolicyRule(
            target=PolicyTarget.TOOL,
            target_id="denied_tool",
            action=PolicyAction.DENY,
            reason="Testing"
        )
        policy_set = PolicySet(name="test", rules=[rule])
        evaluator = PolicyEvaluator([policy_set])

        # Empty task ID should work fine
        allowed, _ = evaluator.check_tool_allowed("denied_tool", task_id="")
        assert allowed is False

    def test_policy_evaluator_with_none_telemetry(self):
        """Test policy evaluator works with None telemetry."""
        rule = PolicyRule(
            target=PolicyTarget.TOOL,
            target_id="tool1",
            action=PolicyAction.DENY
        )
        policy_set = PolicySet(name="policy", rules=[rule])
        # No telemetry provided
        evaluator = PolicyEvaluator([policy_set], telemetry=None)

        allowed, _ = evaluator.check_tool_allowed("tool1")
        assert allowed is False

    def test_multiple_policies_first_deny_wins(self):
        """Test that first matching deny rule is used."""
        set1 = PolicySet(
            name="first",
            rules=[PolicyRule(
                PolicyTarget.TOOL,
                "tool1",
                PolicyAction.DENY,
                "First reason"
            )]
        )
        set2 = PolicySet(
            name="second",
            rules=[PolicyRule(
                PolicyTarget.TOOL,
                "tool1",
                PolicyAction.DENY,
                "Second reason"
            )]
        )
        evaluator = PolicyEvaluator([set1, set2])

        allowed, reason = evaluator.check_tool_allowed("tool1")
        assert allowed is False
        # Should have first reason since first policy set is checked first
        assert "First reason" in reason
