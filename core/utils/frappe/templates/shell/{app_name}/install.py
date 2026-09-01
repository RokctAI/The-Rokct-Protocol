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

# Minimal install surface for a freshly scaffolded shell, referenced from
# hooks.py. Grow it with site-role checks, seeders, or database extension
# setup as the shell matures (rcore/install.py is the reference example).


def before_install():
    # Runs before `bench install-app {app_name}`.
    pass


def after_install():
    # Runs after `bench install-app {app_name}`.
    pass
