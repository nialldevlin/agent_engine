"""
Lightweight natural-language override parsing for Phase 6.

Currently only supports "remember/keep in mind" directives so the pipeline
can persist preferences or facts at either project or global scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import re


@dataclass
class RememberDirective:
    scope: str  # "project" or "global"
    text: str
    is_preference: bool = False


def _split_sentences(prompt: str) -> List[str]:
    """Split a prompt into coarse sentences for parsing."""
    pieces = re.split(r"(?<=[.!?])\s+", prompt)
    return [p.strip() for p in pieces if p.strip()]


def _contains_any(text: str, phrases: List[str]) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def parse_remember_directives(prompt: str, config: Dict) -> List[RememberDirective]:
    """
    Parse "remember/keep in mind" directives out of a prompt.

    Args:
        prompt: Raw user prompt.
        config: Conversational/override config dictionary.
    """
    remember_cfg = config.get("remember", {})
    command_phrases = [p.lower() for p in remember_cfg.get("command_phrases", [])]
    global_keywords = [p.lower() for p in remember_cfg.get("global_keywords", [])]
    project_keywords = [p.lower() for p in remember_cfg.get("project_keywords", [])]
    preference_keywords = [p.lower() for p in remember_cfg.get("preference_keywords", [])]
    max_chars = remember_cfg.get("max_capture_chars", 200)

    if not command_phrases:
        return []

    directives: List[RememberDirective] = []
    for sentence in _split_sentences(prompt):
        sentence_lower = sentence.lower()
        if not _contains_any(sentence_lower, command_phrases):
            continue

        trimmed = sentence.strip()
        if len(trimmed) > max_chars:
            trimmed = trimmed[:max_chars].rstrip() + "…"

        is_preference = _contains_any(sentence_lower, preference_keywords)
        has_project_hint = _contains_any(sentence_lower, project_keywords)
        has_global_hint = _contains_any(sentence_lower, global_keywords)

        scope = "project"
        if has_global_hint:
            scope = "global"
        elif not has_project_hint and is_preference:
            # Preferences default to global in absence of explicit scope.
            scope = "global"

        directives.append(RememberDirective(scope=scope, text=trimmed, is_preference=is_preference))

    return directives


# ---------------------------------------------------------------------------
# Intent detection for overrides/help/config queries
# ---------------------------------------------------------------------------

@dataclass
class FeedbackIntent:
    text: str
    severity_hint: Optional[str] = None
    numeric_delta: Optional[int] = None
    target: Optional[str] = None

    def as_dict(self) -> Dict[str, Optional[str]]:
        return {
            "text": self.text,
            "severity": self.severity_hint,
            "numeric_delta": self.numeric_delta,
            "target": self.target,
        }

POSITIVE_FEEDBACK_HINTS = [
    "good job",
    "great job",
    "well done",
    "nice work",
    "reward",
    "promote",
    "increase score",
    "raise score",
    "add points",
    "bonus",
]

NEGATIVE_FEEDBACK_HINTS = [
    "bad job",
    "poor job",
    "terrible",
    "awful",
    "messed up",
    "reduce score",
    "lower score",
    "penalize",
    "punish",
    "demote",
    "remove points",
]

SEVERITY_DELTA_MAP = {
    "minor_positive": 1,
    "minor_negative": -1,
    "moderate_positive": 2,
    "moderate_negative": -2,
    "major_positive": 5,
    "major_negative": -5,
    "critical_positive": 5,
    "critical_negative": -5,
}


def map_feedback_intent_to_severity(intent: FeedbackIntent) -> tuple[Optional[str], Optional[int]]:
    """Convert a parsed FeedbackIntent into a ScoringEngine severity label."""
    bucket = _determine_feedback_bucket(intent)
    if not bucket:
        return None, None

    positive = _is_positive_feedback(intent)
    label = f"{bucket}_{'positive' if positive else 'negative'}"
    delta_hint = SEVERITY_DELTA_MAP.get(label)
    return label, delta_hint


def _determine_feedback_bucket(intent: FeedbackIntent) -> Optional[str]:
    if intent.numeric_delta is not None:
        magnitude = abs(intent.numeric_delta)
        if magnitude <= 1:
            return "minor"
        if magnitude <= 3:
            return "moderate"
        if magnitude <= 5:
            return "major"
        return "critical"
    if intent.severity_hint in {"minor", "moderate", "major", "critical"}:
        return intent.severity_hint
    return "moderate"


def _is_positive_feedback(intent: FeedbackIntent) -> bool:
    if intent.numeric_delta is not None:
        return intent.numeric_delta > 0
    text = intent.text.lower()
    if any(hint in text for hint in POSITIVE_FEEDBACK_HINTS):
        return True
    if any(hint in text for hint in NEGATIVE_FEEDBACK_HINTS):
        return False
    # Default to negative unless explicitly positive
    return False


@dataclass
class SummonIntent:
    target_mode: str
    phrase: str

    def as_dict(self) -> Dict[str, str]:
        return {"mode": self.target_mode, "phrase": self.phrase}


@dataclass
class PipelineOverrideIntent:
    force_full_pipeline: bool = False
    skip_stages: List[str] = field(default_factory=list)

    def has_overrides(self) -> bool:
        return self.force_full_pipeline or bool(self.skip_stages)

    def as_dict(self) -> Dict[str, object]:
        return {
            "force_full_pipeline": self.force_full_pipeline,
            "skip_stages": list(dict.fromkeys(self.skip_stages)),  # preserve order, drop dupes
        }


@dataclass
class HelpIntent:
    keyword: str
    raw_text: str

    def as_dict(self) -> Dict[str, str]:
        return {"keyword": self.keyword, "text": self.raw_text}

    @property
    def text(self) -> str:
        return self.raw_text


@dataclass
class ConfigQueryIntent:
    keyword: str
    raw_text: str

    def as_dict(self) -> Dict[str, str]:
        return {"keyword": self.keyword, "text": self.raw_text}

    @property
    def text(self) -> str:
        return self.raw_text


@dataclass
class ConfigChangeIntent:
    parameter: str
    value: str
    raw_text: str
    source: str

    def as_dict(self) -> Dict[str, str]:
        return {
            "parameter": self.parameter,
            "value": self.value,
            "text": self.raw_text,
            "source": self.source,
        }

    @property
    def text(self) -> str:
        return self.raw_text


@dataclass
class ContextResolutionIntent:
    phrase: str
    reason: str

    def as_dict(self) -> Dict[str, str]:
        return {"phrase": self.phrase, "reason": self.reason}


@dataclass
class IntentDetection:
    feedback: List[FeedbackIntent] = field(default_factory=list)
    summon: List[SummonIntent] = field(default_factory=list)
    pipeline: PipelineOverrideIntent = field(default_factory=PipelineOverrideIntent)
    help_queries: List[HelpIntent] = field(default_factory=list)
    config_queries: List[ConfigQueryIntent] = field(default_factory=list)
    config_changes: List[ConfigChangeIntent] = field(default_factory=list)
    context_requests: List[ContextResolutionIntent] = field(default_factory=list)

    def has_matches(self) -> bool:
        return any([
            self.feedback,
            self.summon,
            self.pipeline.has_overrides(),
            self.help_queries,
            self.config_queries,
            self.config_changes,
            self.context_requests,
        ])

    def to_metadata(self) -> Dict[str, object]:
        data: Dict[str, object] = {}
        if self.feedback:
            data["feedback"] = [item.as_dict() for item in self.feedback]
        if self.summon:
            data["summon"] = [item.as_dict() for item in self.summon]
        if self.pipeline.has_overrides():
            data["pipeline_overrides"] = self.pipeline.as_dict()
        if self.help_queries:
            data["help_queries"] = [item.as_dict() for item in self.help_queries]
        if self.config_queries:
            data["config_queries"] = [item.as_dict() for item in self.config_queries]
        if self.config_changes:
            data["config_changes"] = [item.as_dict() for item in self.config_changes]
        if self.context_requests:
            data["context_requests"] = [item.as_dict() for item in self.context_requests]
        return data


def detect_user_intents(prompt: str, config: Dict, fast_path_map: Dict[str, List[str]]) -> IntentDetection:
    """Detect high-level override/help intents for a user prompt."""
    lowered = prompt.lower()
    intent_cfg = (config or {}).get("intent_detection", {})
    detection = IntentDetection()

    detection.feedback = _detect_feedback(prompt, lowered, intent_cfg.get("feedback", {}))
    detection.summon = _detect_summon(lowered, fast_path_map or {})
    detection.pipeline = _detect_force(lowered, intent_cfg.get("force", {}))
    detection.help_queries = _detect_keyword_intents(prompt, lowered, intent_cfg.get("help", {}).get("keywords", []), HelpIntent)
    detection.config_queries = _detect_keyword_intents(prompt, lowered, intent_cfg.get("config_query", {}).get("keywords", []), ConfigQueryIntent)
    detection.config_changes = _detect_config_changes(prompt, intent_cfg.get("config_change", {}))
    detection.context_requests = _detect_context_requests(prompt, lowered, intent_cfg.get("context_resolution", {}))
    return detection


def _detect_feedback(prompt: str, lowered: str, cfg: Dict) -> List[FeedbackIntent]:
    results: List[FeedbackIntent] = []
    keywords = [kw.lower() for kw in cfg.get("keywords", [])]
    if not keywords:
        return results

    sentences = _split_sentences(prompt)
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if not any(keyword in sentence_lower for keyword in keywords):
            continue

        severity = _match_severity(sentence_lower, cfg.get("severity_phrases", {}))
        numeric_delta = _extract_numeric_delta(sentence_lower, cfg.get("numeric_pattern"))
        target = _match_first(sentence_lower, cfg.get("agent_terms", []))

        results.append(FeedbackIntent(
            text=sentence.strip(),
            severity_hint=severity,
            numeric_delta=numeric_delta,
            target=target,
        ))

    return results


def _match_severity(text: str, severity_map: Dict[str, List[str]]) -> Optional[str]:
    for label, phrases in severity_map.items():
        for phrase in phrases:
            if phrase.lower() in text:
                return label
    return None


def _extract_numeric_delta(text: str, pattern: Optional[str]) -> Optional[int]:
    if not pattern:
        return None
    try:
        compiled = re.compile(pattern)
    except re.error:
        return None
    match = compiled.search(text)
    if match:
        try:
            return int(match.group(1))
        except (IndexError, ValueError):
            return None
    return None


def _match_first(text: str, phrases: List[str]) -> Optional[str]:
    for phrase in phrases:
        if phrase.lower() in text:
            return phrase.lower()
    return None


def _detect_summon(lowered: str, fast_path_map: Dict[str, List[str]]) -> List[SummonIntent]:
    summon_modes = {
        "guinevere_only",
        "merlin_only",
        "plan_only",
        "analysis_only",
        "diff_preview",
        "research_only",
        "quick_knight",
        "arthur_only",
    }
    results: List[SummonIntent] = []
    for mode, phrases in fast_path_map.items():
        if mode not in summon_modes:
            continue
        for phrase in phrases:
            if phrase in lowered:
                results.append(SummonIntent(target_mode=mode, phrase=phrase))
                break
    return results


def _detect_force(lowered: str, cfg: Dict) -> PipelineOverrideIntent:
    intent = PipelineOverrideIntent()
    for phrase in cfg.get("force_full", []) or []:
        if phrase.lower() in lowered:
            intent.force_full_pipeline = True
            break

    skip_map = cfg.get("skip_map", {}) or {}
    for stage, phrases in skip_map.items():
        for phrase in phrases:
            if phrase.lower() in lowered:
                intent.skip_stages.append(stage)
                break

    return intent


def _detect_keyword_intents(prompt: str, lowered: str, keywords: List[str], intent_cls):
    results = []
    for keyword in keywords:
        key_lower = keyword.lower()
        if key_lower in lowered:
            results.append(intent_cls(keyword=keyword, raw_text=prompt))
            break
    return results


def _detect_config_changes(prompt: str, cfg: Dict) -> List[ConfigChangeIntent]:
    results: List[ConfigChangeIntent] = []
    aliases = cfg.get("aliases", {}) or {}
    lowered = prompt.lower()
    for phrase, mapping in aliases.items():
        if phrase.lower() in lowered:
            parameter, value = _parse_alias_mapping(mapping)
            results.append(ConfigChangeIntent(parameter=parameter, value=value, raw_text=phrase, source="alias"))

    patterns = [
        ("set", cfg.get("set_patterns", []), None),
        ("enable", cfg.get("enable_patterns", []), "true"),
        ("disable", cfg.get("disable_patterns", []), "false"),
    ]
    for label, pattern_list, default_value in patterns:
        for pattern in pattern_list or []:
            try:
                regex = re.compile(pattern, flags=re.IGNORECASE)
            except re.error:
                continue
            match = regex.search(prompt)
            if not match:
                continue
            key = (match.group("key") or "").strip().lower()
            if not key:
                continue
            value = default_value
            if "value" in match.groupdict():
                value = match.group("value").strip().lower()
            if value is None:
                value = "true"
            parameter = key.replace(" ", "_")
            results.append(ConfigChangeIntent(parameter=parameter, value=value, raw_text=match.group(0).strip(), source=label))

    return results


def _parse_alias_mapping(mapping: str) -> tuple[str, str]:
    if "=" in mapping:
        key, value = mapping.split("=", 1)
        return key.strip(), value.strip()
    return mapping.strip(), "true"


def _detect_context_requests(prompt: str, lowered: str, cfg: Dict) -> List[ContextResolutionIntent]:
    results: List[ContextResolutionIntent] = []
    lead_phrases = [phrase.lower() for phrase in cfg.get("lead_phrases", [])]
    pronouns = [word.lower() for word in cfg.get("pronouns", [])]
    max_tokens = cfg.get("max_tokens", 60)

    for phrase in lead_phrases:
        if phrase and phrase in lowered:
            results.append(ContextResolutionIntent(phrase=phrase, reason="lead"))

    token_count = len(prompt.split())
    if token_count <= max_tokens and any(pronoun in lowered for pronoun in pronouns):
        if lowered.endswith("?") or lowered.startswith("what"):
            results.append(ContextResolutionIntent(phrase="pronoun_question", reason="short_reference"))

    return results
