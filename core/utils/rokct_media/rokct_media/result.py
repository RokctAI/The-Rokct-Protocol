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

"""Result of a render, as render() returns it and out/result.json stores it.

result.json carries ids, numbers and hashes only: never the script text or
an ASR transcript (those stay in .work/).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

Status = Literal["pass", "fail", "refused", "invalid"]
EXIT_CODES = {"pass": 0, "fail": 1, "invalid": 2, "refused": 3}


@dataclass
class Output:
    path: Path
    profile: str
    format: str
    sha256: str
    duration_s: float | None = None
    segment: str | None = None
    kind: str = "clip"  # clip | take | cut | listen
    publishable: bool = False
    lufs: float | None = None
    true_peak: float | None = None


@dataclass
class Delivery:
    sink: str
    ok: bool
    refs: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class Result:
    status: Status
    level: int = 1
    job_id: str = ""
    outputs: list[Output] = field(default_factory=list)
    segments: list[dict] = field(default_factory=list)
    refusals: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    model: dict = field(default_factory=dict)
    voices: dict = field(default_factory=dict)
    settings: dict = field(default_factory=dict)
    deliveries: list[Delivery] = field(default_factory=list)
    returned: list[Output] = field(default_factory=list)
    result_path: Path | None = None
    elapsed_s: float | None = None

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.status]

    def to_dict(self) -> dict:
        def conv(v):
            if isinstance(v, Path):
                return v.as_posix()
            if isinstance(v, dict):
                return {k: conv(x) for k, x in v.items()}
            if isinstance(v, (list, tuple)):
                return [conv(x) for x in v]
            return v

        d = conv(asdict(self))
        d["schema"] = "rokct-media/result@1"
        return d

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.result_path = path
        path.write_text(
            json.dumps(self.to_dict(), indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path
