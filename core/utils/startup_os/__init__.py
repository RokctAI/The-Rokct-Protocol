"""StartupOS strategic compiler engine.

Canonical home for the engine. The skill wrapper at
`core/skills/.rok/startup_os/` fetches these modules at runtime and mounts them
as the `core` package, so every module here must import its siblings via
`from core.<module> import ...`.
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
