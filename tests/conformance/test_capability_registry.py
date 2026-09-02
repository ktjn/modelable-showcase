from __future__ import annotations

import json
import subprocess


REGISTRY_CAPABILITIES = {
    "application-package-identity",
    "consequence-graph-analysis",
    "cross-application-consequence-analysis",
    "local-registry-snapshot",
    "offline-compiler-analysis",
    "policy-evaluator-boundary",
    "snapshot-aware-impact",
    "snapshot-provenance",
    "transitive-dependency-closure",
}


def test_registry_capabilities_are_reported_as_implemented() -> None:
    result = subprocess.run(
        ["modelable", "capabilities", "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    capabilities = json.loads(result.stdout)
    by_name = {item["name"]: item for item in capabilities if item["category"] == "registry_capability"}

    assert REGISTRY_CAPABILITIES <= by_name.keys()
    assert {name for name in REGISTRY_CAPABILITIES if by_name[name]["status"] == "implemented"} == REGISTRY_CAPABILITIES
