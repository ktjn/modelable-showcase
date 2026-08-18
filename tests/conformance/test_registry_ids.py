"""Integration tests proving `modelable compile`'s registry-id allocation
ledger (`--registry-ids`) evolves the way IMPLEMENTATION_PLAN.md Task 14.1
requires, via subprocess only. Never import modelable's Python internals here
- these tests exist to prove the downstream CLI contract, not implementation
details (IMPLEMENTATION_PLAN.md Sec 0, rule 2).

Every case uses copies/temp directories (`tmp_path`) and its own
`--registry-ids`/`--registry` paths; the canonical `model/registry-ids.lock`
is never written to by these tests (only read, in
test_canonical_model_compile_does_not_modify_the_committed_lock)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "registry-ids"
MODEL_DIR = REPO_ROOT / "model"

pytestmark = pytest.mark.skipif(
    shutil.which("modelable") is None,
    reason="modelable is not on PATH - run 'make bootstrap' (or source scripts/modelable-env.sh) first",
)


def _compile(
    source: Path,
    out_dir: Path,
    registry_ids: Path,
    registry_db: Path,
    *,
    allow_orphaned: bool = False,
) -> subprocess.CompletedProcess[str]:
    args = [
        "modelable",
        "compile",
        str(source),
        "--target",
        "registry",
        "--out",
        str(out_dir),
        "--registry",
        str(registry_db),
        "--registry-ids",
        str(registry_ids),
    ]
    if allow_orphaned:
        args.append("--allow-orphaned-registry-ids")
    return subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True)


def _workspace(tmp_path: Path, step_file: str) -> Path:
    """A fresh copy of the fixture workspace with `step_file` installed as
    `thing.mdl`, so each evolution step starts from an isolated source tree."""
    workspace = tmp_path / f"workspace-{Path(step_file).stem}"
    workspace.mkdir()
    shutil.copy2(FIXTURE_DIR / "workspace.mdl", workspace / "workspace.mdl")
    shutil.copy2(FIXTURE_DIR / step_file, workspace / "thing.mdl")
    return workspace


def _read_ids(path: Path) -> dict[str, int]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_baseline_compile_captures_ids(tmp_path: Path):
    workspace = _workspace(tmp_path, "v1_baseline.mdl")
    registry_ids = tmp_path / "registry-ids.lock"
    result = _compile(workspace, tmp_path / "out", registry_ids, tmp_path / "registry.db")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _read_ids(registry_ids) == {"thing.ThingId": 1}


def test_recompiling_unchanged_model_leaves_ids_unchanged(tmp_path: Path):
    workspace = _workspace(tmp_path, "v1_baseline.mdl")
    registry_ids = tmp_path / "registry-ids.lock"
    registry_db = tmp_path / "registry.db"
    first = _compile(workspace, tmp_path / "out1", registry_ids, registry_db)
    assert first.returncode == 0, first.stdout + first.stderr
    before = _read_ids(registry_ids)

    second = _compile(workspace, tmp_path / "out2", registry_ids, registry_db)
    assert second.returncode == 0, second.stdout + second.stderr
    assert _read_ids(registry_ids) == before == {"thing.ThingId": 1}


def test_adding_a_new_semantic_allocates_an_id_above_the_current_max(tmp_path: Path):
    registry_ids = tmp_path / "registry-ids.lock"
    registry_db = tmp_path / "registry.db"

    baseline = _compile(_workspace(tmp_path, "v1_baseline.mdl"), tmp_path / "out1", registry_ids, registry_db)
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    assert _read_ids(registry_ids) == {"thing.ThingId": 1}

    grown = _compile(_workspace(tmp_path, "v2_add_semantic.mdl"), tmp_path / "out2", registry_ids, registry_db)
    assert grown.returncode == 0, grown.stdout + grown.stderr
    ids = _read_ids(registry_ids)
    assert ids["thing.ThingId"] == 1, "existing id must not be reassigned"
    assert ids["thing.ThingCode"] == 2, "new id must be allocated above the current max"


def test_removing_a_semantic_errors_without_allow_orphaned_flag(tmp_path: Path):
    registry_ids = tmp_path / "registry-ids.lock"
    registry_db = tmp_path / "registry.db"

    _compile(_workspace(tmp_path, "v1_baseline.mdl"), tmp_path / "out1", registry_ids, registry_db)
    _compile(_workspace(tmp_path, "v2_add_semantic.mdl"), tmp_path / "out2", registry_ids, registry_db)

    shrunk = _compile(_workspace(tmp_path, "v3_remove_semantic.mdl"), tmp_path / "out3", registry_ids, registry_db)
    assert shrunk.returncode != 0, "compile must fail on an orphaned ledger entry by default"
    assert "orphan" in (shrunk.stdout + shrunk.stderr).lower()
    assert "thing.ThingId" in (shrunk.stdout + shrunk.stderr)
    # The ledger must be left untouched by the failed attempt.
    assert _read_ids(registry_ids) == {"thing.ThingId": 1, "thing.ThingCode": 2}


def test_allow_orphaned_flag_keeps_old_id_reserved_and_never_reuses_it(tmp_path: Path):
    registry_ids = tmp_path / "registry-ids.lock"
    registry_db = tmp_path / "registry.db"

    _compile(_workspace(tmp_path, "v1_baseline.mdl"), tmp_path / "out1", registry_ids, registry_db)
    _compile(_workspace(tmp_path, "v2_add_semantic.mdl"), tmp_path / "out2", registry_ids, registry_db)

    shrunk = _compile(
        _workspace(tmp_path, "v3_remove_semantic.mdl"),
        tmp_path / "out3",
        registry_ids,
        registry_db,
        allow_orphaned=True,
    )
    assert shrunk.returncode == 0, shrunk.stdout + shrunk.stderr
    ids = _read_ids(registry_ids)
    assert ids == {"thing.ThingId": 1, "thing.ThingCode": 2}, "orphaned id must remain reserved, unchanged"

    # A further evolution step (new semantic added while the orphan is still
    # present) must allocate an id above the current max, not reuse id 1.
    grown_again = _compile(
        _workspace(tmp_path, "v4_add_after_orphan.mdl"),
        tmp_path / "out4",
        registry_ids,
        registry_db,
        allow_orphaned=True,
    )
    assert grown_again.returncode == 0, grown_again.stdout + grown_again.stderr
    ids = _read_ids(registry_ids)
    assert ids == {"thing.ThingId": 1, "thing.ThingCode": 2, "thing.ThingSlug": 3}


def test_canonical_model_compile_does_not_modify_the_committed_lock(tmp_path: Path):
    before = MODEL_DIR.joinpath("registry-ids.lock").read_text(encoding="utf-8")

    tmp_registry_ids = tmp_path / "registry-ids.lock"
    shutil.copy2(MODEL_DIR / "registry-ids.lock", tmp_registry_ids)
    result = _compile(MODEL_DIR, tmp_path / "out", tmp_registry_ids, tmp_path / "registry.db")
    assert result.returncode == 0, result.stdout + result.stderr

    after = MODEL_DIR.joinpath("registry-ids.lock").read_text(encoding="utf-8")
    assert after == before, "compiling the canonical model must never modify the committed registry-ids.lock"
    assert json.loads(tmp_registry_ids.read_text(encoding="utf-8")) == json.loads(before), (
        "compiling against a copy of the canonical lock must reproduce the same ids"
    )
