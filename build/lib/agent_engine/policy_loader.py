"""Policy loader for loading and parsing policy.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import yaml

from agent_engine.schemas.policy import PolicyAction, PolicyRule, PolicySet, PolicyTarget


def load_policy_manifest(config_dir: str) -> Optional[Dict]:
    """Load optional policy.yaml manifest from config directory.

    Args:
        config_dir: Path to configuration directory

    Returns:
        Parsed YAML as dict, or None if file doesn't exist
    """
    policy_path = Path(config_dir) / "policy.yaml"
    if not policy_path.exists():
        return None

    with open(policy_path, "r") as f:
        data = yaml.safe_load(f)
    return data if data else None


def parse_policies(data: Optional[Dict]) -> List[PolicySet]:
    """Parse policy YAML data into PolicySet objects.

    Args:
        data: Parsed YAML dict or None

    Returns:
        List of PolicySet objects (empty list if no data)

    Raises:
        ValueError: If policy data is malformed
    """
    if not data:
        return []

    policy_sets = []
    policy_list = data.get("policies", [])

    for policy_data in policy_list:
        name = policy_data.get("name")
        if not name:
            raise ValueError("Policy must have a 'name' field")

        enabled = policy_data.get("enabled", True)
        rules = []

        for rule_data in policy_data.get("rules", []):
            target_str = rule_data.get("target")
            target_id = rule_data.get("target_id")
            action_str = rule_data.get("action")
            reason = rule_data.get("reason", "")

            if not target_str or not target_id or not action_str:
                raise ValueError(
                    "Rule must have 'target', 'target_id', and 'action' fields"
                )

            try:
                target = PolicyTarget(target_str)
                action = PolicyAction(action_str)
            except ValueError as e:
                raise ValueError(f"Invalid policy field: {e}")

            rule = PolicyRule(target=target, target_id=target_id, action=action, reason=reason)
            rules.append(rule)

        policy_set = PolicySet(name=name, rules=rules, enabled=enabled)
        policy_sets.append(policy_set)

    return policy_sets
