"""Versioned deterministic score aggregation.

Exact port of AgentSystem tools/src/agent_system_tools/scorecard/weights.py
(plan V2 §14.1): six dimensions, integer scores 1..5, verification_burden
inverted during aggregation, prior-weighted posterior for routing advice.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

RUBRIC_VERSION = "score-v1"
WEIGHT_VERSION = "score-v1"
PRIOR_MEAN = 3.0
PRIOR_WEIGHT = 20
WEIGHTS = {
    "correctness": 0.25,
    "usefulness": 0.20,
    "instruction_adherence": 0.15,
    "reliability": 0.15,
    "efficiency": 0.15,
    "verification_burden": 0.10,
}
SCORE_NAMES = tuple(WEIGHTS)


class ScoreValidationError(ValueError):
    pass


def validate_scores(scores: Mapping[str, object]) -> dict[str, int]:
    if set(scores) != set(SCORE_NAMES):
        raise ScoreValidationError("SCORE_FIELDS_INVALID")
    validated: dict[str, int] = {}
    for name in SCORE_NAMES:
        value = scores[name]
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
            raise ScoreValidationError(f"SCORE_OUT_OF_RANGE {name}")
        validated[name] = value
    return validated


def weighted_score(scores: Mapping[str, object]) -> float:
    validated = validate_scores(scores)
    total = 0.0
    for name, weight in WEIGHTS.items():
        value = validated[name]
        if name == "verification_burden":
            value = 6 - value
        total += value * weight
    return round(total, 6)


def posterior_score(
    observations: Iterable[float],
    *,
    prior_mean: float = PRIOR_MEAN,
    prior_weight: int = PRIOR_WEIGHT,
) -> float:
    values = list(observations)
    return (prior_mean * prior_weight + sum(values)) / (prior_weight + len(values))
