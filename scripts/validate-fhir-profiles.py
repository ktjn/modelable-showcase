#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""HL7 FHIR Validator smoke (IMPLEMENTATION_PLAN.md Task 15.4, Phase 15):
validates representative generated Patient/Observation/Encounter FHIR
profiles using the real official validator CLI
(https://github.com/hapifhir/org.hl7.fhir.core) - never a hand-rolled
structural check pretending to be HL7 conformance.

Optional: requires Java and a local `tools/validator_cli.jar`
(`scripts/install-fhir-validator.sh` installs a pinned,
checksum-verified copy - not part of `make bootstrap`). Skips cleanly
(exit 0, printing why) when either prerequisite is missing, per this
task's "if available in CI cache/tool setup" framing - this is an
opt-in profile, not a required gate.

Each representative profile is validated together with its own
`*.ext.*.fhir.json` extension sidecar files (the validator needs every
referenced extension definition loaded in the same invocation to resolve
`Extension.url` references), matching how a real consumer would validate
a complete FHIR profile bundle.

Usage:
    uv run scripts/validate-fhir-profiles.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FHIR_DIR = REPO_ROOT / "generated" / "fhir-profile"
VALIDATOR_JAR = REPO_ROOT / "tools" / "validator_cli.jar"
FHIR_VERSION = "4.0.1"

# Patient/Observation/Encounter - the representative base-HL7-resource
# profiles Task 15.4 asks for (each has `derivation: constraint` against a
# real `http://hl7.org/fhir/StructureDefinition/<Resource>`, unlike the
# handwritten reporting/billing profiles, which constrain nothing from HL7).
REPRESENTATIVE_PROFILES = [
    "clinical.PatientFhirView.v1",
    "clinical.ObservationFhirView.v1",
    "clinical.EncounterFhirView.v1",
]


def main() -> int:
    if shutil.which("java") is None:
        print("validate-fhir-profiles.py: SKIP - java is not on PATH", file=sys.stderr)
        return 0
    if not VALIDATOR_JAR.exists():
        print(
            f"validate-fhir-profiles.py: SKIP - {VALIDATOR_JAR} not found; "
            "run 'scripts/install-fhir-validator.sh' first",
            file=sys.stderr,
        )
        return 0
    if not FHIR_DIR.exists():
        print(f"validate-fhir-profiles.py: {FHIR_DIR} missing; run 'make generate' first", file=sys.stderr)
        return 1

    overall_ok = True
    for profile in REPRESENTATIVE_PROFILES:
        files = sorted(FHIR_DIR.glob(f"{profile}*.fhir.json"))
        if not files:
            print(f"validate-fhir-profiles.py: no files found for {profile}", file=sys.stderr)
            overall_ok = False
            continue
        result = subprocess.run(
            ["java", "-jar", str(VALIDATOR_JAR), *[str(f) for f in files], "-version", FHIR_VERSION],
            capture_output=True,
            text=True,
        )
        ok = "*SUCCESS*" in result.stdout and "*FAILURE*" not in result.stdout
        overall_ok = overall_ok and ok
        status = "OK" if ok else "FAILED"
        print(f"{status} {profile} ({len(files)} files)")
        if not ok:
            for line in result.stdout.splitlines():
                if "Error @" in line or "*FAILURE*" in line:
                    print(f"  {line.strip()}")

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
