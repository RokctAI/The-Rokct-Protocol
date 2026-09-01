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


class UnknownArtifactError(StartupOSError):
    """A selective compile or gap check named an artifact that does not exist.

    The message always lists every valid artifact name, so a caller (studio,
    TenderAssist, a human at the CLI) can correct the request without digging
    through the template folder.
    """


class BrandingError(StartupOSError):
    """A brand/ asset (design system file, logo, image) is malformed.

    Raised instead of rendering a half-branded deck: a deck that silently
    dropped the brand would look deliberate to the investor reading it.
    """
