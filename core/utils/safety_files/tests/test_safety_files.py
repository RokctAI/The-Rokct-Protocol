# Copyright (c) 2026 ROKCT INTELLIGENCE (PTY) LTD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Tests for the Safety Files engine. Run: python -m pytest core/utils/safety_files/tests -q"""

import copy
import importlib.util
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)

# Mount the flat directory as the `safetyfiles` package, as the wheel does.
_spec = importlib.util.spec_from_file_location("safetyfiles", os.path.join(PKG, "__init__.py"), submodule_search_locations=[PKG])
safetyfiles = importlib.util.module_from_spec(_spec)
sys.modules["safetyfiles"] = safetyfiles
_spec.loader.exec_module(safetyfiles)

from safetyfiles import builder, main, templates  # noqa: E402

TODAY = "2026-11-22"


@pytest.fixture
def profile():
    with open(os.path.join(PKG, "examples", "sample_profile.json"), encoding="utf-8") as fh:
        return json.load(fh)


def test_rejects_unsupported_jurisdiction(profile):
    profile["jurisdiction"] = "KE"
    with pytest.raises(builder.ProfileError):
        builder.status(profile, today=TODAY)


def test_requires_company_and_site(profile):
    broken = copy.deepcopy(profile)
    del broken["company"]["name"]
    with pytest.raises(builder.ProfileError):
        builder.status(broken, today=TODAY)
    broken = copy.deepcopy(profile)
    broken["site"] = {}
    with pytest.raises(builder.ProfileError):
        builder.status(broken, today=TODAY)


def test_never_claims_compliance(profile, tmp_path):
    report = builder.build(profile, str(tmp_path), today=TODAY)
    assert report["status"] == "draft"
    assert report["reviewed"] is False
    text = (tmp_path / "binder.md").read_text(encoding="utf-8").lower()
    assert templates.REVIEW_NOTICE.lower() in text
    for claim in ("is compliant", "fully compliant", "complies with", "meets the requirements"):
        assert claim not in text


def test_review_gap_while_unreviewed(profile):
    gaps = builder.status(profile, today=TODAY)["gaps"]
    assert any(g["status"] == "not_reviewed" for g in gaps)


def test_evidence_fail_closed(profile, tmp_path):
    rows = {r["type"]: r["status"] for r in builder._evidence(profile, None, builder._today(TODAY))}
    assert rows["coida_letter"] == "provided"
    assert rows["public_liability"] == "not_provided"
    # A listed file that does not exist is not "provided".
    profile["documents"][0]["file"] = "missing.pdf"
    rows = {r["type"]: r["status"] for r in builder._evidence(profile, str(tmp_path), builder._today(TODAY))}
    assert rows["coida_letter"] == "file_missing"
    (tmp_path / "missing.pdf").write_bytes(b"%PDF-1.4")
    rows = {r["type"]: r["status"] for r in builder._evidence(profile, str(tmp_path), builder._today(TODAY))}
    assert rows["coida_letter"] == "provided"
    # An expiring document with no expiry date, or an expired one, is not "provided".
    del profile["documents"][0]["file"]
    profile["documents"][0]["expires"] = ""
    rows = {r["type"]: r["status"] for r in builder._evidence(profile, None, builder._today(TODAY))}
    assert rows["coida_letter"] == "expiry_unknown"
    profile["documents"][0]["expires"] = "2026-01-01"
    rows = {r["type"]: r["status"] for r in builder._evidence(profile, None, builder._today(TODAY))}
    assert rows["coida_letter"] == "expired"
    # A reference is what makes a document count; a bare type does not.
    profile["documents"][0]["reference"] = ""
    rows = {r["type"]: r["status"] for r in builder._evidence(profile, None, builder._today(TODAY))}
    assert rows["coida_letter"] == "not_provided"


def test_expiry_log_states(profile):
    entries = builder.expiry_log(profile, today=TODAY)
    states = {(e["kind"], e["who"]): e["state"] for e in entries}
    assert states[("medical", "Demo Installer")] == "expired"
    assert states[("training", "Demo Installer")] == "due_soon"
    assert states[("document", "")] == "ok"
    assert [e["date"] for e in entries] == sorted(e["date"] for e in entries)


def test_missing_sections_reported(profile):
    profile["hazards"] = []
    profile["policy"] = {}
    gaps = builder.status(profile, today=TODAY)["gaps"]
    keys = {g["section"] for g in gaps}
    assert "risk_assessment" in keys
    assert "policy" in keys


def test_build_writes_valid_outputs(profile, tmp_path):
    report = builder.build(profile, str(tmp_path), today=TODAY)
    pdf = (tmp_path / "binder.pdf").read_bytes()
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%EOF")
    assert pdf.count(b"/Type /Page ") == len(templates.SECTIONS) + 2  # cover + index + one page per section
    assert json.loads((tmp_path / "gap_report.json").read_text()) == report["gaps"]
    assert json.loads((tmp_path / "expiry_log.json").read_text()) == report["expiries"]
    md = (tmp_path / "binder.md").read_text(encoding="utf-8")
    for section in templates.SECTIONS:
        assert section["title"] in md


def test_table_cells_wrap_not_truncate():
    long = "Isolate and lock out the supply; only a qualified electrician connects the sign"
    lines = builder._table_lines([("a", "A"), ("b", "B")], [{"a": "x", "b": long}])
    joined = " ".join(part.split("|")[1].strip() for part in lines[2:])
    assert joined == long
    assert all(len(line) <= builder.TABLE_WIDTH for line in lines)


def test_fingerprint_changes_with_content(profile):
    first = builder.fingerprint(profile)
    profile["site"]["name"] = "Other site"
    assert builder.fingerprint(profile) != first


def test_cli_status_and_bad_profile(profile, tmp_path, capsys):
    path = tmp_path / "p.json"
    path.write_text(json.dumps(profile))
    assert main.main(["status", "--profile", str(path), "--today", TODAY]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "draft"
    path.write_text(json.dumps({"jurisdiction": "ZA"}))
    assert main.main(["status", "--profile", str(path)]) == 2


def test_wheel_builds_and_imports(tmp_path):
    pytest.importorskip("setuptools")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(tmp_path), PKG],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("pip wheel unavailable here: " + result.stderr[-200:])
    wheels = list(tmp_path.glob("safetyfiles-*.whl"))
    assert wheels, result.stdout
