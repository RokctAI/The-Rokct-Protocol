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

# Shell-owned identity and hooks. The backend composer appends its generated
# fence (dynamic SDK hooks) at the END of this file on every compose — keep
# hand-written content above it and never edit the fenced block by hand.

app_name = "{app_name}"
app_title = "{app_name}"
app_publisher = "ROKCT INTELLIGENCE (PTY) LTD"
app_description = "Composed Frappe app shell"
app_email = "admin@rokct.ai"
app_license = "mit"

# Installation
# ------------
before_install = "{app_name}.install.before_install"
after_install = "{app_name}.install.after_install"

# Website Route Rules
# -------------------
# Shell-owned website routes go here, e.g.:
# website_route_rules = [
#     {
#         "from_route": "/.well-known/assetlinks.json",
#         "to_route": "{app_name}.api.app_links.get_assetlinks",
#     },
# ]
