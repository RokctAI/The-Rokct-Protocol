# Copyright (c) 2026 RokctAI
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

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
