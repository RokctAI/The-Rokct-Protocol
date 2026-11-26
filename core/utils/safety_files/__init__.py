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

"""Safety Files: a stateless compiler for a contractor's site safety file.

It takes one JSON profile (company, site, people, hazards, registers,
training, supporting documents) and returns an indexed binder (Markdown and
PDF), a gap report and an expiry log. It keeps no state between runs: the SDK
that calls it owns the records and passes them in each time.

Rules carried over from StartupOS (core/utils/startup_os):

- Fail closed. The tool never states that a file "complies" with any law.
  A supporting document is shown as provided only when the profile lists it
  with a reference and, where a file path is given, the file exists.
- Every output carries a provenance footer and a review notice.
- Jurisdiction gated: South Africa only for now; anything else is refused.
- No AI. Hazards and controls come from the user; the tool only lays them out.

LEGAL STATUS: the templates in `templates.py` have NOT been reviewed by a
registered South African OHS practitioner or a lawyer. Until that review is
recorded in `templates.REVIEW`, every page says so.
"""

__version__ = "0.1.0"
