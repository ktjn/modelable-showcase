"""Rust generated package build (IMPLEMENTATION_PLAN.md Task 7.1): prove
generated Rust alone builds, before any API work depends on it.

`generated/rust/` is a real multi-package layout - one Cargo package per
`package {}` block in model/workspace.mdl (clinic-core, clinical-core,
billing-core), each with its own Cargo.toml, wired together with `path`
dependencies rather than a shared [workspace] manifest, so packages are
checked individually (`cargo check` inside each package directory), not
via a single workspace-wide command.

Against the pinned 1.8.0 release, UPSTREAM_FINDINGS.md #14 is fixed, so
clinical-core now builds cleanly (its optional-array-of-named-type shape
`clinical.Encounter.diagnoses?: array<Diagnosis>` resolves). billing-core
still fails, but for a different, new bug (UPSTREAM_FINDINGS.md #26): the
`From<BillingInvoiceV2Status> for ReportingOutstandingInvoicesV1Status` impl
is never generated even though the projection's `From<BillingInvoiceV2>`
impl calls `src.status.into()`. clinic-core (patient + scheduling domains)
builds cleanly and carries the real proof for the "registered semantic
newtype exposes a stable ID" and "model exposes schema version/content
signature constants" requirements; note the registry-id ledger moved with
1.8.0 (model/registry-ids.lock) and PatientId's stable ID is now 2, not 1.
The "at least one cross-package reference compiles" requirement is proven
with a small isolated two-package fixture (tests/conformance/rust-probe/).

clinical-core's restored build and billing-core's current #26 failure are
both asserted explicitly (with their precise expected outcomes) rather than
skipped, so this file itself becomes the signal to update once Modelable is
re-pinned past a release that fixes #26.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = REPO_ROOT / "model"
RUST_DIR = REPO_ROOT / "generated" / "rust"
PROBE_DIR = Path(__file__).resolve().parents[1] / "conformance" / "rust-probe"

pytestmark = [
    pytest.mark.skipif(shutil.which("modelable") is None, reason="modelable is not on PATH"),
    pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo is not on PATH"),
]


def run_modelable(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["modelable", *args], cwd=REPO_ROOT, capture_output=True, text=True)


def cargo(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["cargo", *args], cwd=cwd, capture_output=True, text=True)


# --- clinic-core: builds cleanly against 1.8.0 (UPSTREAM_FINDINGS.md #14 fixed) -


def test_clinic_core_directory_exists():
    assert (RUST_DIR / "clinic-core" / "Cargo.toml").exists(), "run 'make generate' first"


def test_clinic_core_package_checks_cleanly():
    result = cargo("check", cwd=RUST_DIR / "clinic-core")
    assert result.returncode == 0, result.stdout + result.stderr


def test_clinic_core_package_tests_pass():
    result = cargo("test", cwd=RUST_DIR / "clinic-core")
    assert result.returncode == 0, result.stdout + result.stderr


def test_registered_semantic_newtype_exposes_stable_registry_id():
    text = (RUST_DIR / "clinic-core" / "src" / "patient" / "patient_id.rs").read_text()
    assert "pub struct PatientId(pub uuid::Uuid);" in text
    assert "pub const REGISTRY_ID: u32 = 2;" in text


def test_model_exposes_schema_version_and_content_signature_constants():
    text = (RUST_DIR / "clinic-core" / "src" / "patient" / "patient_patient_v2.rs").read_text()
    assert "pub const SCHEMA_VERSION: u32 = 2;" in text
    assert "pub const SCHEMA_CONTENT_SIGNATURE: [u8; 32] = [" in text


# --- cross-package reference compiles (isolated probe, see its own header) --


def test_cross_package_reference_compiles():
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "out"
        compile_result = run_modelable(
            "compile",
            str(PROBE_DIR),
            "--target",
            "rust",
            "--out",
            str(out_dir),
            "--registry",
            str(Path(tmp) / "registry.db"),
            "--registry-ids",
            str(Path(tmp) / "registry-ids.lock"),
            "--enum-numbers",
            str(Path(tmp) / "enum-numbers.lock"),
        )
        assert compile_result.returncode == 0, compile_result.stdout + compile_result.stderr

        pkg_b_order = out_dir / "pkg-b" / "src" / "domainb" / "domainb_order_v1.rs"
        assert "use pkg_a::domaina::widget_id::WidgetId;" in pkg_b_order.read_text()
        assert "pub widget_id: WidgetId," in pkg_b_order.read_text()

        result_a = cargo("check", cwd=out_dir / "pkg-a")
        assert result_a.returncode == 0, result_a.stdout + result_a.stderr
        result_b = cargo("check", cwd=out_dir / "pkg-b")
        assert result_b.returncode == 0, result_b.stdout + result_b.stderr


# --- clinical-core / billing-core: clinical-core restored, billing-core #26 ---


def test_clinical_core_builds_per_finding_14_fixed():
    result = cargo("check", cwd=RUST_DIR / "clinical-core")
    assert result.returncode == 0, result.stdout + result.stderr


def test_billing_core_builds_per_findings_26_35_36_fixed():
    result = cargo("check", cwd=RUST_DIR / "billing-core")
    # UPSTREAM_FINDINGS.md #26 (missing From impl), #35 (duplicate serde default),
    # and #36 (cross-domain From imports via super::) are all fixed by v1.9.2.
    assert result.returncode == 0, result.stdout + result.stderr
