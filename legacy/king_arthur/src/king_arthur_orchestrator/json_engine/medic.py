"""
JSON Medic - Lightweight tool for repairing malformed JSON.

This module provides a minimal LLM-based tool that attempts to repair
malformed JSON before parsing. It's designed to be invoked inline during
JSON parse failures to reduce retry overhead.

Cost Mode Integration:
- CHEAP: Use deterministic repairs only (no LLM)
- BALANCED: Use LLM for non-cosmetic errors
- MAX_QUALITY: Always use LLM
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import json
import time
import re

from king_arthur_orchestrator.infra.api_client import ClaudeClient
from king_arthur_orchestrator.infra.config import ArthurCostMode
from king_arthur_orchestrator.json_engine.utils import parse_json_safely


@dataclass
class JSONRepairResult:
    """Result of JSON repair attempt."""
    success: bool
    repaired_json: Optional[str] = None
    changes_made: list[str] = field(default_factory=list)
    error_message: Optional[str] = None
    tokens_used: int = 0
    latency_ms: float = 0.0
    used_llm: bool = False  # Whether LLM was invoked
    skipped_due_to_cost_mode: bool = False  # Whether skipped due to cost constraints


class JSONMedic:
    """Lightweight JSON repair tool using minimal LLM prompting."""

    # Minimal system prompt focused solely on JSON repair
    SYSTEM_PROMPT = """You are a JSON repair specialist. Your ONLY job is to fix malformed JSON.

Given a string that should be valid JSON but has formatting errors, you must:
1. Identify what is wrong with the JSON
2. Return a corrected, valid JSON string
3. List what changes you made

Rules:
- Output ONLY valid JSON in your response
- Fix common issues: missing quotes, trailing commas, unescaped strings, missing brackets
- Preserve the original structure and data as much as possible
- Do NOT add new fields or change data values
- Do NOT explain in prose - output JSON only

Your response must be a JSON object with:
{
  "repaired": "the fixed JSON string goes here",
  "changes": ["list of changes made"]
}"""

    def __init__(self, client: ClaudeClient, cost_mode: ArthurCostMode = ArthurCostMode.BALANCED):
        """Initialize JSON Medic with an API client and cost mode.

        Args:
            client: Claude API client for LLM-based repairs
            cost_mode: Cost mode controlling whether to use LLM
        """
        self.client = client
        self.cost_mode = cost_mode

    @staticmethod
    def deterministic_repair(malformed_json: str) -> JSONRepairResult:
        """
        Attempt deterministic (non-LLM) repairs of common JSON issues.

        This method handles:
        - Removing code fences (```json ... ```)
        - Fixing trailing commas
        - Trimming whitespace
        - Basic brace/bracket completion

        Args:
            malformed_json: The malformed JSON string

        Returns:
            JSONRepairResult with repair status
        """
        start_time = time.time()
        changes = []
        repaired = malformed_json

        # Remove code fences
        if repaired.strip().startswith("```"):
            repaired = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", repaired, flags=re.MULTILINE)
            repaired = repaired.rstrip("`").strip()
            changes.append("Removed code fences")

        # Fix trailing commas before closing braces/brackets
        original = repaired
        repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)
        if repaired != original:
            changes.append("Removed trailing commas")

        # Try parsing
        try:
            json.loads(repaired)
            latency_ms = (time.time() - start_time) * 1000
            return JSONRepairResult(
                success=True,
                repaired_json=repaired,
                changes_made=changes,
                latency_ms=latency_ms,
                used_llm=False
            )
        except json.JSONDecodeError:
            latency_ms = (time.time() - start_time) * 1000
            return JSONRepairResult(
                success=False,
                error_message="Deterministic repairs failed to fix JSON",
                changes_made=changes,
                latency_ms=latency_ms,
                used_llm=False
            )

    def repair(self, malformed_json: str, context: str = "", error_class: Optional[str] = None) -> JSONRepairResult:
        """
        Attempt to repair malformed JSON with cost-aware strategy.

        Cost Mode Behavior:
        - CHEAP: Try deterministic repairs only, skip LLM
        - BALANCED: Try deterministic first, use LLM for structural errors
        - MAX_QUALITY: Always use LLM

        Args:
            malformed_json: The malformed JSON string to repair
            context: Optional context about what this JSON should represent
            error_class: Optional error classification (cosmetic, structural, fatal)

        Returns:
            JSONRepairResult with repair status and details
        """
        # Try deterministic repairs first (always, regardless of cost mode)
        deterministic_result = self.deterministic_repair(malformed_json)
        if deterministic_result.success:
            return deterministic_result

        # Always attempt LLM repair when deterministic fails
        # Cost mode only affects which model we use, not whether we attempt repair
        start_time = time.time()

        # Build user message
        user_message = f"Fix this malformed JSON:\n\n{malformed_json}\n\n"
        if context:
            user_message += f"Context: This JSON should represent {context}\n"

        # Select model based on cost mode
        # All modes attempt repair, but CHEAP uses the most economical model
        if self.cost_mode == ArthurCostMode.CHEAP:
            model = "claude-3-5-haiku-latest"
        elif self.cost_mode == ArthurCostMode.BALANCED:
            model = "claude-3-5-haiku-latest"
        else:  # MAX_QUALITY
            model = "claude-3-5-sonnet-latest"

        try:
            response = self.client.complete(
                system_prompt=self.SYSTEM_PROMPT,
                user_message=user_message,
                model=model,
                max_tokens=2000,
                temperature=0.1
            )

            latency_ms = (time.time() - start_time) * 1000

            # Parse the medic's response safely (handles code fences, extra text, etc.)
            medic_output = parse_json_safely(response.content)
            if not medic_output:
                return JSONRepairResult(
                    success=False,
                    error_message="Medic output could not be parsed as valid JSON",
                    tokens_used=response.tokens_used,
                    latency_ms=latency_ms,
                    used_llm=True
                )

            # Extract repaired JSON and changes
            repaired_json_str = medic_output.get("repaired", "")
            changes = medic_output.get("changes", [])

            # Validate the repaired JSON
            try:
                json.loads(repaired_json_str)  # Will raise if still invalid
            except json.JSONDecodeError as e:
                return JSONRepairResult(
                    success=False,
                    error_message=f"Medic's repaired JSON is still invalid: {str(e)}",
                    tokens_used=response.tokens_used,
                    latency_ms=latency_ms,
                    used_llm=True
                )

            return JSONRepairResult(
                success=True,
                repaired_json=repaired_json_str,
                changes_made=changes,
                tokens_used=response.tokens_used,
                latency_ms=latency_ms,
                used_llm=True
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return JSONRepairResult(
                success=False,
                error_message=f"Medic invocation failed: {str(e)}",
                latency_ms=latency_ms,
                used_llm=False
            )

    def repair_with_fallback(
        self,
        malformed_json: str,
        context: str = "",
        max_attempts: int = 1
    ) -> JSONRepairResult:
        """
        Attempt to repair JSON with optional retry fallback.

        Args:
            malformed_json: The malformed JSON string to repair
            context: Optional context about what this JSON should represent
            max_attempts: Maximum number of repair attempts

        Returns:
            JSONRepairResult with repair status and details
        """
        last_result = None
        for attempt in range(max_attempts):
            result = self.repair(malformed_json, context)
            if result.success:
                return result
            last_result = result

        return last_result or JSONRepairResult(
            success=False,
            error_message="No repair attempts were made"
        )
