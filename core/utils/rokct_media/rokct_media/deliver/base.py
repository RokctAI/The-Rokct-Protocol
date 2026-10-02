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

"""The sink interface a caller (a Frappe app, say) implements to add its own
destination, registered through the entry-point group "rokct_media.sinks".
Rendering and delivering are separate: sinks run only after every output
passed its gates."""
from __future__ import annotations

from typing import Protocol


class Sink(Protocol):
    name: str
    publishes: bool  # True -> agreement_in_place is checked before rendering

    def validate(self, opts: dict, job) -> list[str]: ...

    def deliver(self, outputs: list, opts: dict, job): ...
