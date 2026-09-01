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

"""StartupOS strategic compiler engine.

Canonical home for the engine. It is consumed under two package identities:

- The skill wrapper at `core/skills/.rok/startup_os/` fetches these modules at
  runtime and mounts them as the `core` package (`from core.parser import ...`).
- The `pyproject.toml` beside this file publishes the same directory as the
  pip-installable `startupos` package (`from startupos import parser`).

Every module here therefore imports its siblings *relatively*
(`from .parser import ...`), which resolves identically under either name.
"""

__version__ = "2.0.0"


def enable_utf8_console():
    """Make stdout/stderr tolerate non-ASCII on a cp1252 Windows console.

    Generated documents legitimately contain em dashes and currency symbols;
    without this a `print` of any of them raises UnicodeEncodeError and kills
    the run after the files have already been written.
    """
    import sys

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
