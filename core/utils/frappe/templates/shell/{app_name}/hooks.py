# Copyright (c) 2026 ROKCT INTELLIGENCE (PTY) LTD
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
