"""
Manifest hygiene system for King Arthur's agent manifests.

Audits agent manifests to ensure:
- Prompts align with tool restrictions
- Constraints reflect allowed/denied tools
- Role matches capabilities
- Model selection is appropriate for task complexity
- Consent expectations are documented
- All required fields are present and valid

This system helps maintain consistency as new agents are added and existing
agents evolve, preventing drift between manifest declarations and actual behavior.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json
import re

from king_arthur_orchestrator.toolkit.manifest_utils import (
    load_all,
    AgentDescriptor,
    MANIFESTS_DIR,
    validate_manifest_schema
)


@dataclass
class HygieneIssue:
    """A single hygiene issue found during audit."""
    severity: str  # "error", "warning", "info"
    category: str  # "prompt_tool_mismatch", "constraint_missing", etc.
    agent_name: str
    message: str
    fix_suggestion: Optional[str] = None


@dataclass
class HygieneReport:
    """Comprehensive hygiene audit report for all manifests."""
    total_manifests: int = 0
    manifests_checked: int = 0
    errors: List[HygieneIssue] = field(default_factory=list)
    warnings: List[HygieneIssue] = field(default_factory=list)
    info: List[HygieneIssue] = field(default_factory=list)
    clean_manifests: List[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        """True if no errors or warnings found."""
        return len(self.errors) == 0 and len(self.warnings) == 0

    @property
    def summary(self) -> str:
        """One-line summary of audit results."""
        if self.is_clean:
            return f"✅ All {self.manifests_checked} manifests passed hygiene checks"
        else:
            return f"⚠️ {len(self.errors)} errors, {len(self.warnings)} warnings across {self.manifests_checked} manifests"


class ManifestHygieneAuditor:
    """Automated hygiene auditor for agent manifests."""

    def __init__(self, manifests_dir: Optional[Path] = None):
        """Initialize auditor with manifest directory.

        Args:
            manifests_dir: Path to manifests directory (defaults to MANIFESTS_DIR)
        """
        self.manifests_dir = manifests_dir or MANIFESTS_DIR

    def audit_all(self) -> HygieneReport:
        """Run comprehensive hygiene audit on all manifests.

        Returns:
            HygieneReport with all issues found
        """
        report = HygieneReport()

        # Load all manifests
        manifests, load_warnings = load_all(self.manifests_dir)
        report.total_manifests = len(list(self.manifests_dir.glob("*.json")))
        report.manifests_checked = len(manifests)

        # Check each manifest
        for desc in manifests.values():
            agent_issues = self._audit_single_manifest(desc)

            if not agent_issues:
                report.clean_manifests.append(desc.name)

            for issue in agent_issues:
                if issue.severity == "error":
                    report.errors.append(issue)
                elif issue.severity == "warning":
                    report.warnings.append(issue)
                else:
                    report.info.append(issue)

        return report

    def _audit_single_manifest(self, desc: AgentDescriptor) -> List[HygieneIssue]:
        """Audit a single manifest for hygiene issues.

        Args:
            desc: Agent descriptor to audit

        Returns:
            List of hygiene issues found
        """
        issues = []

        # Run all audit checks
        issues.extend(self._check_prompt_tool_alignment(desc))
        issues.extend(self._check_constraint_tool_alignment(desc))
        issues.extend(self._check_role_consistency(desc))
        issues.extend(self._check_model_appropriateness(desc))
        issues.extend(self._check_consent_documentation(desc))
        issues.extend(self._check_required_fields(desc))
        issues.extend(self._check_tool_namespace_consistency(desc))

        return issues

    def _check_prompt_tool_alignment(self, desc: AgentDescriptor) -> List[HygieneIssue]:
        """Check if system prompt mentions tool restrictions."""
        issues = []
        system_prompt = desc.prompts.get("system", "").lower()

        # If agent has denied execution tools, prompt should mention it
        execution_denied = any("execution" in t for t in desc.tools_denied)
        if execution_denied:
            # More lenient keywords - accept broader phrasing
            execution_keywords = [
                "not execute", "no execution", "don't execute", "do not execute",
                "just plan", "only plan", "planning", "plan only", "create a plan",
                "no code", "no commands", "readonly", "read-only", "read only"
            ]
            if not any(kw in system_prompt for kw in execution_keywords):
                issues.append(HygieneIssue(
                    severity="info",  # Downgraded from "warning" to "info"
                    category="prompt_tool_mismatch",
                    agent_name=desc.name,
                    message="Manifest denies execution.* but prompt doesn't explicitly mention 'no execution' or similar",
                    fix_suggestion="Consider adding phrase like 'Do not execute commands' to system prompt for clarity"
                ))

        # If agent has denied file write, prompt should mention it
        write_denied = any("write" in t or "edit" in t for t in desc.tools_denied)
        if write_denied:
            write_keywords = ["no file", "not modify", "don't modify", "do not modify", "read-only", "read only"]
            if not any(kw in system_prompt for kw in write_keywords):
                issues.append(HygieneIssue(
                    severity="warning",
                    category="prompt_tool_mismatch",
                    agent_name=desc.name,
                    message="Manifest denies file modification but prompt doesn't mention read-only restriction",
                    fix_suggestion="Add phrase like 'Do not modify files' to system prompt"
                ))

        # If agent has tool restrictions, prompt should acknowledge them
        if (desc.tools_allowed or desc.tools_denied):
            tool_keywords = ["tools allowed", "use only", "available tools", "tools you can use"]
            if not any(kw in system_prompt for kw in tool_keywords):
                issues.append(HygieneIssue(
                    severity="info",
                    category="prompt_tool_mention",
                    agent_name=desc.name,
                    message="Manifest has tool restrictions but prompt doesn't explicitly mention available tools",
                    fix_suggestion="Consider adding 'Use only the tools allowed to you' to system prompt"
                ))

        return issues

    def _check_constraint_tool_alignment(self, desc: AgentDescriptor) -> List[HygieneIssue]:
        """Check if constraints align with tool restrictions."""
        issues = []

        constraints_text = " ".join(desc.constraints).lower()

        # If constraints mention "no execution", should be in denied list
        if "no execution" in constraints_text or "no code execution" in constraints_text:
            if not any("execution" in t for t in desc.tools_denied):
                issues.append(HygieneIssue(
                    severity="warning",
                    category="constraint_tool_mismatch",
                    agent_name=desc.name,
                    message="Constraints mention 'no execution' but execution.* not in denied list",
                    fix_suggestion="Add 'execution.*' to tools.denied"
                ))

        # If constraints mention "no file mutation/modification", should deny write/edit
        if "no file mutation" in constraints_text or "no file modification" in constraints_text:
            write_edit_denied = any(t in ["file_write", "file_edit"] or "write" in t or "edit" in t for t in desc.tools_denied)
            if not write_edit_denied:
                issues.append(HygieneIssue(
                    severity="warning",
                    category="constraint_tool_mismatch",
                    agent_name=desc.name,
                    message="Constraints mention no file modification but file_write/edit not denied",
                    fix_suggestion="Add 'file_write' and 'file_edit' to tools.denied"
                ))

        # If constraints mention "valid JSON", check role
        if "valid json" in constraints_text or "produce json" in constraints_text:
            if desc.role not in ["planning", "interpretation", "todo", "analysis"]:
                issues.append(HygieneIssue(
                    severity="info",
                    category="constraint_role_mismatch",
                    agent_name=desc.name,
                    message=f"Constraints require JSON output but role is '{desc.role}' (expected planning/interpretation/analysis)",
                    fix_suggestion=None
                ))

        return issues

    def _check_role_tool_capabilities(self, desc: AgentDescriptor) -> List[HygieneIssue]:
        """Check if role matches tool capabilities (helper for _check_role_consistency)."""
        issues = []

        # Research/analysis roles shouldn't have execution or write tools
        if desc.role in ["research", "analysis", "planning"]:
            has_execution = any("execution.bash" in t or t == "execution.*" for t in desc.tools_allowed)
            has_write = any("file_write" in t or "file_edit" in t for t in desc.tools_allowed)

            if has_execution:
                issues.append(HygieneIssue(
                    severity="error",
                    category="role_capability_mismatch",
                    agent_name=desc.name,
                    message=f"Role '{desc.role}' should not have execution capabilities",
                    fix_suggestion="Remove execution.* from tools.allowed or change role"
                ))

            if has_write:
                issues.append(HygieneIssue(
                    severity="warning",
                    category="role_capability_mismatch",
                    agent_name=desc.name,
                    message=f"Role '{desc.role}' should typically not have write capabilities",
                    fix_suggestion="Consider removing file_write/edit from tools.allowed"
                ))

        # Execution role should have execution tools
        if desc.role == "execution":
            has_execution = any("execution" in t for t in desc.tools_allowed)
            if not has_execution:
                issues.append(HygieneIssue(
                    severity="error",
                    category="role_capability_mismatch",
                    agent_name=desc.name,
                    message="Role 'execution' but no execution.* tools in allowlist",
                    fix_suggestion="Add 'execution.bash' or 'execution.*' to tools.allowed"
                ))

        return issues

    def _check_model_appropriateness(self, desc: AgentDescriptor) -> List[HygieneIssue]:
        """Check if model selection is appropriate for role."""
        issues = []

        # Map roles to recommended models
        role_model_recommendations = {
            "research": ["claude-sonnet", "claude-opus"],  # Complex analysis needs strong model
            "execution": ["claude-haiku", "claude-sonnet"],  # Simple execution can use Haiku
            "planning": ["claude-haiku", "claude-sonnet"],  # Planning can use Haiku
            "trivial": ["claude-haiku"],  # Trivial tasks should use Haiku
            "analysis": ["claude-sonnet", "claude-opus"],  # Analysis needs strong model
        }

        model_lower = desc.model.lower()
        role = desc.role

        if role in role_model_recommendations:
            recommended = role_model_recommendations[role]
            is_appropriate = any(rec in model_lower for rec in recommended)

            if not is_appropriate:
                # Check if using expensive model for simple task
                if "opus" in model_lower and role in ["execution", "trivial"]:
                    issues.append(HygieneIssue(
                        severity="warning",
                        category="model_overprovisioned",
                        agent_name=desc.name,
                        message=f"Role '{role}' using Opus model (expensive for simple tasks)",
                        fix_suggestion=f"Consider using Haiku or Sonnet for {role} role"
                    ))
                # Check if using cheap model for complex task
                elif "haiku" in model_lower and role in ["research", "analysis"]:
                    issues.append(HygieneIssue(
                        severity="info",
                        category="model_underprovisioned",
                        agent_name=desc.name,
                        message=f"Role '{role}' using Haiku model (may need Sonnet for complex analysis)",
                        fix_suggestion="Consider using Sonnet for more robust research/analysis"
                    ))

        return issues

    def _check_consent_documentation(self, desc: AgentDescriptor) -> List[HygieneIssue]:
        """Check if agents with destructive tools document consent expectations."""
        issues = []

        system_prompt = desc.prompts.get("system", "").lower()
        constraints_text = " ".join(desc.constraints).lower()

        # Check if agent has potentially destructive tools
        has_execution = any("execution.bash" in t or t == "execution.*" for t in desc.tools_allowed)
        has_write = any("file_write" in t or "file_edit" in t for t in desc.tools_allowed)
        has_hardware = any("hardware" in t for t in desc.tools_allowed)

        needs_consent = has_execution or has_write or has_hardware

        if needs_consent:
            consent_keywords = ["consent", "permission", "authorization", "approval"]
            mentions_consent = any(kw in system_prompt or kw in constraints_text for kw in consent_keywords)

            if not mentions_consent:
                issues.append(HygieneIssue(
                    severity="info",
                    category="consent_undocumented",
                    agent_name=desc.name,
                    message="Agent has destructive capabilities but doesn't mention consent/permission requirements",
                    fix_suggestion="Add 'Respect consent prompts' to constraints or mention in system prompt"
                ))

        return issues

    def _check_required_fields(self, desc: AgentDescriptor) -> List[HygieneIssue]:
        """Check if all required fields are present and valid."""
        issues = []

        # Check name
        if not desc.name or desc.name == "Unknown":
            issues.append(HygieneIssue(
                severity="error",
                category="missing_required_field",
                agent_name=desc.name,
                message="Missing or invalid 'name' field",
                fix_suggestion="Add unique, descriptive name to manifest"
            ))

        # Check system prompt exists and is non-empty
        system_prompt = desc.prompts.get("system", "")
        if not system_prompt or len(system_prompt.strip()) < 10:
            issues.append(HygieneIssue(
                severity="error",
                category="missing_required_field",
                agent_name=desc.name,
                message="System prompt is missing or too short (< 10 chars)",
                fix_suggestion="Add descriptive system prompt defining agent's role and behavior"
            ))

        # Check version format
        if desc.version:
            try:
                parts = desc.version.split(".")
                if len(parts) != 3 or not all(p.isdigit() for p in parts):
                    issues.append(HygieneIssue(
                        severity="warning",
                        category="invalid_version",
                        agent_name=desc.name,
                        message=f"Version '{desc.version}' doesn't follow semantic versioning (expected X.Y.Z)",
                        fix_suggestion="Use semantic version format like '1.0.0'"
                    ))
            except Exception:
                pass

        return issues

    def _check_tool_namespace_consistency(self, desc: AgentDescriptor) -> List[HygieneIssue]:
        """Check if tools use consistent namespace conventions."""
        issues = []

        all_tools = desc.tools_allowed + desc.tools_denied

        # Check for old namespace patterns (legacy file_* style)
        old_patterns = ["file_read", "file_write", "file_edit", "file_*"]
        uses_old_namespace = any(t in old_patterns for t in all_tools)

        if uses_old_namespace:
            issues.append(HygieneIssue(
                severity="warning",
                category="namespace_inconsistency",
                agent_name=desc.name,
                message="Uses old namespace (file_*) instead of new (filesystem.*)",
                fix_suggestion="Update to use filesystem.read/write/edit"
            ))

        # Check for mixed namespaces
        has_filesystem_namespace = any(t.startswith("filesystem.") for t in all_tools)
        has_file_namespace = any(t.startswith("file_") for t in all_tools)

        if has_filesystem_namespace and has_file_namespace:
            issues.append(HygieneIssue(
                severity="warning",
                category="namespace_inconsistency",
                agent_name=desc.name,
                message="Mixes new (filesystem.*) and legacy (file_*) namespaces",
                fix_suggestion="Use only filesystem.* namespace for consistency"
            ))

        # Check for unnamespaced tools (should have category prefix)
        for tool in all_tools:
            if "." not in tool and "*" not in tool:
                issues.append(HygieneIssue(
                    severity="info",
                    category="tool_naming",
                    agent_name=desc.name,
                    message=f"Tool '{tool}' lacks namespace prefix (expected category.*)",
                    fix_suggestion=f"Consider using namespaced form like 'filesystem.{tool}' or 'execution.{tool}'"
                ))

        return issues

    def _check_role_consistency(self, desc: AgentDescriptor) -> List[HygieneIssue]:
        """Check if role field matches agent_type, prompt keywords, and tool capabilities."""
        issues = []

        # Check role-tool capability alignment (errors/warnings for mismatches)
        issues.extend(self._check_role_tool_capabilities(desc))

        # Check role vs agent_type consistency
        if hasattr(desc, 'agent_type') and desc.agent_type:
            if desc.role != desc.agent_type and desc.agent_type != "task_runner":
                issues.append(HygieneIssue(
                    severity="info",
                    category="role_type_mismatch",
                    agent_name=desc.name,
                    message=f"role='{desc.role}' but agent_type='{desc.agent_type}' (usually should match)",
                    fix_suggestion="Align role and agent_type fields for clarity"
                ))

        # Check if role matches prompt
        system_prompt = desc.prompts.get("system", "").lower()
        role_lower = desc.role.lower()

        # Map roles to expected prompt keywords
        role_keywords = {
            "planning": ["plan", "task_knight", "analyze"],
            "execution": ["execute", "task_runner", "run"],
            "research": ["research", "scholar", "analyze", "merlin"],
            "trivial": ["answer", "respond", "guinevere"],
            "analysis": ["analyze", "review", "assess", "analyst"],
        }

        if role_lower in role_keywords:
            expected_keywords = role_keywords[role_lower]
            has_role_keyword = any(kw in system_prompt for kw in expected_keywords)

            if not has_role_keyword:
                issues.append(HygieneIssue(
                    severity="info",
                    category="role_prompt_mismatch",
                    agent_name=desc.name,
                    message=f"Role '{desc.role}' but prompt doesn't mention {'/'.join(expected_keywords[:2])}",
                    fix_suggestion=f"Add role-specific keywords to prompt for clarity"
                ))

        return issues

    def format_report(self, report: HygieneReport, verbose: bool = False) -> str:
        """Format hygiene report as human-readable text.

        Args:
            report: The hygiene report to format
            verbose: If True, include info-level issues

        Returns:
            Formatted report string
        """
        lines = []

        lines.append("=" * 70)
        lines.append("MANIFEST HYGIENE AUDIT REPORT")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"Manifests checked: {report.manifests_checked}/{report.total_manifests}")
        lines.append(f"Clean manifests: {len(report.clean_manifests)}")
        lines.append(f"Errors: {len(report.errors)}")
        lines.append(f"Warnings: {len(report.warnings)}")
        lines.append(f"Info: {len(report.info)}")
        lines.append("")
        lines.append(report.summary)
        lines.append("")

        # Show clean manifests
        if report.clean_manifests:
            lines.append("✅ CLEAN MANIFESTS:")
            for name in sorted(report.clean_manifests):
                lines.append(f"   - {name}")
            lines.append("")

        # Show errors
        if report.errors:
            lines.append("❌ ERRORS:")
            for issue in sorted(report.errors, key=lambda x: x.agent_name):
                lines.append(f"   [{issue.agent_name}] {issue.message}")
                if issue.fix_suggestion:
                    lines.append(f"      Fix: {issue.fix_suggestion}")
            lines.append("")

        # Show warnings
        if report.warnings:
            lines.append("⚠️ WARNINGS:")
            for issue in sorted(report.warnings, key=lambda x: x.agent_name):
                lines.append(f"   [{issue.agent_name}] {issue.message}")
                if issue.fix_suggestion:
                    lines.append(f"      Fix: {issue.fix_suggestion}")
            lines.append("")

        # Show info only if verbose
        if verbose and report.info:
            lines.append("ℹ️ INFO:")
            for issue in sorted(report.info, key=lambda x: x.agent_name):
                lines.append(f"   [{issue.agent_name}] {issue.message}")
                if issue.fix_suggestion:
                    lines.append(f"      Fix: {issue.fix_suggestion}")
            lines.append("")

        # Summary by category
        lines.append("ISSUES BY CATEGORY:")
        all_issues = report.errors + report.warnings + (report.info if verbose else [])
        categories = {}
        for issue in all_issues:
            categories[issue.category] = categories.get(issue.category, 0) + 1

        for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"   {category}: {count}")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)

    def export_report_json(self, report: HygieneReport, output_path: Path) -> None:
        """Export hygiene report as JSON file.

        Args:
            report: The hygiene report to export
            output_path: Path to write JSON report
        """
        data = {
            "total_manifests": report.total_manifests,
            "manifests_checked": report.manifests_checked,
            "clean_manifests": report.clean_manifests,
            "summary": report.summary,
            "errors": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "agent_name": i.agent_name,
                    "message": i.message,
                    "fix_suggestion": i.fix_suggestion
                }
                for i in report.errors
            ],
            "warnings": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "agent_name": i.agent_name,
                    "message": i.message,
                    "fix_suggestion": i.fix_suggestion
                }
                for i in report.warnings
            ],
            "info": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "agent_name": i.agent_name,
                    "message": i.message,
                    "fix_suggestion": i.fix_suggestion
                }
                for i in report.info
            ]
        }

        with output_path.open("w") as f:
            json.dump(data, f, indent=2)


def run_hygiene_audit(manifests_dir: Optional[Path] = None, verbose: bool = False) -> HygieneReport:
    """Run a comprehensive hygiene audit on all manifests.

    Args:
        manifests_dir: Directory containing manifests (defaults to MANIFESTS_DIR)
        verbose: Include info-level issues in output

    Returns:
        HygieneReport with all issues found
    """
    auditor = ManifestHygieneAuditor(manifests_dir)
    return auditor.audit_all()


def print_hygiene_report(manifests_dir: Optional[Path] = None, verbose: bool = False) -> bool:
    """Run hygiene audit and print formatted report.

    Args:
        manifests_dir: Directory containing manifests (defaults to MANIFESTS_DIR)
        verbose: Include info-level issues in output

    Returns:
        True if audit passed (no errors/warnings), False otherwise
    """
    auditor = ManifestHygieneAuditor(manifests_dir)
    report = auditor.audit_all()

    print(auditor.format_report(report, verbose=verbose))

    return report.is_clean
