# Copyright (c) 2026, Rokct Intelligence (pty) Ltd.
# For license information, please see license.txt


"""Exception hierarchy for StartupOS.

Every failure mode gets a named type so callers (CLI, Hermes bridge, CI) can
react differently instead of parsing printed strings.
"""


class StartupOSError(Exception):
    """Base class for every StartupOS failure."""


class UnsafeNameError(StartupOSError):
    """An instance name or type failed validation, or escaped the workspace."""


class WorkspaceError(StartupOSError):
    """The workspace root could not be resolved, or is missing required dirs."""


class ProfileNotFoundError(StartupOSError):
    """No questions.md exists for the requested instance."""


class TemplateError(StartupOSError):
    """A template is missing, malformed, or failed to render."""


class QuestionNotFoundError(StartupOSError):
    """A question label could not be located in questions.md."""
