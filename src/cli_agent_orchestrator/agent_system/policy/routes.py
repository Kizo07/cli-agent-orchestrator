"""Model route policy loading (plan V2 §10.2).

CAO stores only provider IDs and model aliases; exact allowlisted model
identifiers resolve here. CAO never reads, copies, logs, or writes provider
API keys — credentials live in the provider's supported auth path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

import yaml

QWEN_DEFAULT = "qwen-default"


@dataclass(frozen=True)
class ModelRoute:
    alias: str
    provider: str
    provider_family: str
    opencode_provider: str
    candidates: tuple[str, ...]
    fallbacks: tuple[str, ...] = field(default_factory=tuple)

    @property
    def resolved_model(self) -> str:
        return self.candidates[0]

    @property
    def opencode_model_id(self) -> str:
        """Model id to pass to opencode (``provider/model``)."""
        return f"{self.opencode_provider}/{self.resolved_model}"


@dataclass(frozen=True)
class RoutePolicy:
    schema_version: str
    routes: dict[str, ModelRoute]
    excluded_providers: tuple[str, ...]

    def resolve(self, alias: str) -> ModelRoute:
        if alias not in self.routes:
            raise KeyError(f"unknown model alias: {alias}")
        return self.routes[alias]

    def is_excluded(self, provider: str) -> bool:
        return provider in self.excluded_providers


def _default_yaml_text() -> str:
    ref = resources.files("cli_agent_orchestrator.agent_system.policy") / "model_routes.yaml"
    return Path(str(ref)).read_text()


def load_route_policy(path: str | Path | None = None) -> RoutePolicy:
    text = Path(path).read_text() if path else _default_yaml_text()
    doc = yaml.safe_load(text)
    routes = {}
    for alias, spec in (doc.get("aliases") or {}).items():
        routes[alias] = ModelRoute(
            alias=alias,
            provider=spec["provider"],
            provider_family=spec["provider_family"],
            opencode_provider=spec["opencode_provider"],
            candidates=tuple(spec["candidates"]),
            fallbacks=tuple(spec.get("fallbacks", ())),
        )
    return RoutePolicy(
        schema_version=doc.get("schema_version", "model-routes/1"),
        routes=routes,
        excluded_providers=tuple(doc.get("excluded_providers", ())),
    )
