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

"""The consumers index, the compose example and the product templates never
drift from one another.

nextjs_compose_example.json is generated from sdk_consumers.json alone
(tools/gen_nextjs_compose_example.py) and RokctAI/factory copies its sdks[]
into every new Next.js shell at spawn, so:

  * the committed example must equal what the generator produces from the
    committed index now (a refresh of the index without a regenerate fails);
  * every product template's sdks[] entry (core/utils/frappe/composer/*.json)
    must agree with the index on the SDK's repo, path and install.py pin -
    the index is what the weekly refresh reads from the SDK repos, so a
    template that disagrees is stale (or the index is) and must be fixed in
    the same change;
  * the SDK_ECOSYSTEM.md census (secondary) must agree with the index on
    each SDK's repo and Next.js half;
  * the generator must refuse an index that cannot yield the kernel.

Run:  python3 core/utils/nextjs/tests/test_nextjs_compose_example.py
"""

import importlib.util
import json
import os
import shutil
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
)
_GEN_SRC = os.path.join(_REPO_ROOT, "tools", "gen_nextjs_compose_example.py")
_TEMPLATES_DIR = os.path.join(_REPO_ROOT, "core", "utils", "frappe", "composer")
_ECOSYSTEM_MD = os.path.join(_REPO_ROOT, "SDK_ECOSYSTEM.md")
CENSUS_START = "@generated-sdk-census-start"
CENSUS_END = "@generated-sdk-census-end"
# Retired monorepos that still show in the census beside the real home.
RETIRED_CENSUS_REPOS = {"SDKs", "BetAssist"}


def load_generator():
    spec = importlib.util.spec_from_file_location(
        "gen_nextjs_compose_example_test", _GEN_SRC
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gen = load_generator()


def read_json(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def repo_of_git(url):
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    return url[len(gen.GITHUB) :] if url.startswith(gen.GITHUB) else url


def load_templates():
    out = {}
    for name in sorted(os.listdir(_TEMPLATES_DIR)):
        if name.endswith(".json"):
            entries = read_json(os.path.join(_TEMPLATES_DIR, name)).get("sdks") or []
            out[name] = [s for s in entries if isinstance(s, dict) and s.get("name")]
    return out


def load_census():
    """{sdk: {"repos": [...], "nextjs": bool}} from SDK_ECOSYSTEM.md."""
    with open(_ECOSYSTEM_MD, "r", encoding="utf-8") as fh:
        text = fh.read()
    start, end = text.find(CENSUS_START), text.find(CENSUS_END)
    census = {}
    for line in text[start:end].splitlines():
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0] in ("SDK", "") or set(cells[0]) <= set("-"):
            continue
        entry = census.setdefault(cells[0], {"repos": [], "nextjs": False})
        if cells[1] not in RETIRED_CENSUS_REPOS and cells[1] not in entry["repos"]:
            entry["repos"].append(cells[1])
        if cells[4].lower() == "yes":
            entry["nextjs"] = True
    return census


class TestCommittedExample(unittest.TestCase):
    def setUp(self):
        self.example, self.warnings = gen.generate(_REPO_ROOT)
        self.committed = read_json(os.path.join(_REPO_ROOT, gen.OUTPUT_NAME))
        self.index = gen.load_consumers(_REPO_ROOT)

    def test_committed_file_is_current(self):
        self.assertEqual(
            self.committed,
            self.example,
            f"{gen.OUTPUT_NAME} is stale: run python3 tools/gen_nextjs_compose_example.py",
        )

    def test_kernel_is_telemetry_then_base_enabled_never_home(self):
        self.assertEqual([s["name"] for s in self.committed["sdks"]], list(gen.KERNEL))
        for entry in self.committed["sdks"]:
            self.assertTrue(entry["enabled"], entry["name"])
            self.assertIs(entry["home_sdk"], False, entry["name"])
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$", entry["name"])
            self.assertTrue(entry["version"], f"{entry['name']}: no version")

    def test_every_entry_mirrors_the_index(self):
        for entry in self.committed["sdks"] + self.committed["_available_sdks"]:
            record = self.index[entry["name"]]
            half = record["nextjs"]
            self.assertEqual(repo_of_git(entry["git"]), record["repo"], entry["name"])
            self.assertEqual(
                entry["path"], gen.sdk_path(record["repo"], half), entry["name"]
            )
            self.assertEqual(entry["sha256"], half["install_py_sha256"], entry["name"])
            self.assertEqual(entry["version"], half["version"], entry["name"])
            self.assertEqual(entry["consumers"], record["consumers"], entry["name"])
        menu = [s["name"] for s in self.committed["_available_sdks"]]
        self.assertEqual(len(menu), len(set(menu)))
        for name in gen.KERNEL:
            self.assertNotIn(name, menu)
        for name, record in self.index.items():
            listed = name in menu or name in gen.KERNEL
            self.assertEqual(listed, bool(record.get("nextjs")), name)


class TestTemplatesAgreeWithTheIndex(unittest.TestCase):
    """Every product template's Next.js entry matches the index's repo, path
    and pin. A disagreement means the template or the index is stale; the
    two are fixed together."""

    def setUp(self):
        self.index = gen.load_consumers(_REPO_ROOT)
        self.templates = load_templates()

    def test_template_entries_match_the_index(self):
        problems = []
        for tname, entries in self.templates.items():
            for entry in entries:
                if entry.get("source", "git") != "git" or not entry.get("git"):
                    continue
                record = self.index.get(entry["name"])
                if record is None or not record.get("nextjs"):
                    problems.append(
                        f"{tname}: {entry['name']} is not in {gen.CONSUMERS_JSON} "
                        "with a Next.js half - refresh the index"
                    )
                    continue
                half = record["nextjs"]
                if repo_of_git(entry["git"]).lower() != record["repo"].lower():
                    problems.append(
                        f"{tname}: {entry['name']} repo {repo_of_git(entry['git'])} "
                        f"vs index {record['repo']}"
                    )
                if (
                    entry.get("path", "").lower()
                    != gen.sdk_path(record["repo"], half).lower()
                ):
                    problems.append(
                        f"{tname}: {entry['name']} path {entry.get('path')} "
                        f"vs index {gen.sdk_path(record['repo'], half)}"
                    )
                if entry.get("sha256") and entry["sha256"] != half["install_py_sha256"]:
                    problems.append(
                        f"{tname}: {entry['name']} pin {entry['sha256'][:12]} "
                        f"vs index {half['install_py_sha256'][:12]}"
                    )
        self.assertEqual(problems, [], "\n".join(problems))

    def test_kernel_pinned_identically_by_every_template(self):
        for name in gen.KERNEL:
            pins = {
                t: e.get("sha256")
                for t, es in self.templates.items()
                for e in es
                if e["name"] == name
            }
            self.assertTrue(pins, f"{name}: pinned by no product template")
            self.assertEqual(
                set(pins.values()),
                {self.index[name]["nextjs"]["install_py_sha256"]},
                pins,
            )


class TestCensusAgreesWithTheIndex(unittest.TestCase):
    """Secondary cross-check: the SDK_ECOSYSTEM.md census and the index agree
    on where each SDK lives and whether it has a Next.js half (an SDK the
    census has not caught up with yet is allowed; a contradiction is not)."""

    def test_census_repo_and_half_match(self):
        index = gen.load_consumers(_REPO_ROOT)
        census = load_census()
        problems = []
        for name, record in index.items():
            row = census.get(gen.clean(name))
            if row is None:
                continue
            short = record["repo"].split("/", 1)[1]
            if row["repos"] and short.lower() not in [r.lower() for r in row["repos"]]:
                problems.append(
                    f"{name}: index says {record['repo']}, census lists {row['repos']}"
                )
            if row["nextjs"] and not record.get("nextjs"):
                problems.append(
                    f"{name}: census records a Next.js half the index does not"
                )
        self.assertEqual(problems, [], "\n".join(problems))


class TestGeneratorRules(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="compose-example-")
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))

    def write_index(self, sdks):
        with open(
            os.path.join(self.root, gen.CONSUMERS_JSON), "w", encoding="utf-8"
        ) as fh:
            json.dump({"generated_by": "test", "sdks": sdks}, fh)

    @staticmethod
    def record(repo, path, version, pin, consumers=()):
        return {
            "repo": repo,
            "consumers": list(consumers),
            "nextjs": {"path": path, "version": version, "install_py_sha256": pin},
        }

    def test_kernel_and_menu_come_from_the_index_alone(self):
        self.write_index(
            {
                "telemetry_sdk": self.record(
                    "RokctAI/core", "telemetry/nextjs", "1.2.0", "a" * 64, ["one"]
                ),
                "base_sdk": self.record(
                    "RokctAI/core", "base/nextjs", "1.35.0", "b" * 64, ["one"]
                ),
                "lms_sdk": self.record(
                    "RokctAI/agent", "lms/nextjs", "1.25.0", "c" * 64, ["one"]
                ),
                "zones_sdk": {
                    "repo": "RokctAI/zones",
                    "consumers": ["one"],
                    "nextjs": None,
                },
            }
        )
        example, warnings = gen.generate(self.root)
        self.assertEqual(
            [s["name"] for s in example["sdks"]], ["telemetry_sdk", "base_sdk"]
        )
        self.assertEqual(example["sdks"][1]["path"], "../core/base/nextjs")
        self.assertEqual(example["sdks"][1]["sha256"], "b" * 64)
        self.assertEqual(example["sdks"][1]["version"], "1.35.0")
        self.assertEqual([s["name"] for s in example["_available_sdks"]], ["lms_sdk"])
        self.assertIs(example["_available_sdks"][0]["enabled"], False)
        self.assertEqual(example["_available_sdks"][0]["consumers"], ["one"])
        self.assertEqual(example["_omitted_no_nextjs_half"], ["zones_sdk"])
        self.assertEqual(warnings, [])

    def test_kernel_missing_from_the_index_is_drift(self):
        self.write_index(
            {
                "base_sdk": self.record(
                    "RokctAI/core", "base/nextjs", "1.35.0", "b" * 64
                ),
            }
        )
        with self.assertRaises(gen.DriftError) as ctx:
            gen.generate(self.root)
        self.assertIn("telemetry_sdk", str(ctx.exception))

    def test_kernel_without_a_pin_is_drift(self):
        self.write_index(
            {
                "telemetry_sdk": self.record(
                    "RokctAI/core", "telemetry/nextjs", "1.2.0", None
                ),
                "base_sdk": self.record(
                    "RokctAI/core", "base/nextjs", "1.35.0", "b" * 64
                ),
            }
        )
        with self.assertRaises(gen.DriftError) as ctx:
            gen.generate(self.root)
        self.assertIn("pin", str(ctx.exception))

    def test_menu_entry_without_a_pin_is_a_warning(self):
        self.write_index(
            {
                "telemetry_sdk": self.record(
                    "RokctAI/core", "telemetry/nextjs", "1.2.0", "a" * 64
                ),
                "base_sdk": self.record(
                    "RokctAI/core", "base/nextjs", "1.35.0", "b" * 64
                ),
                "new_sdk": self.record("RokctAI/agent", "new/nextjs", None, None),
            }
        )
        example, warnings = gen.generate(self.root)
        self.assertTrue(any("new_sdk" in w for w in warnings))
        self.assertIn("_sha256_comment", example["_available_sdks"][0])

    def test_check_mode_reports_a_stale_file(self):
        self.write_index(
            {
                "telemetry_sdk": self.record(
                    "RokctAI/core", "telemetry/nextjs", "1.2.0", "a" * 64
                ),
                "base_sdk": self.record(
                    "RokctAI/core", "base/nextjs", "1.35.0", "b" * 64
                ),
            }
        )
        self.assertEqual(gen.main(["--root", self.root]), 0)
        self.assertEqual(gen.main(["--check", "--root", self.root]), 0)
        with open(
            os.path.join(self.root, gen.OUTPUT_NAME), "a", encoding="utf-8"
        ) as fh:
            fh.write("\n")
        self.assertEqual(gen.main(["--check", "--root", self.root]), 1)


if __name__ == "__main__":
    unittest.main()
