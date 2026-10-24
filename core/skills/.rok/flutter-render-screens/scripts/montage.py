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

import sys
from PIL import Image

out = sys.argv[1]
files = sys.argv[2:]
ims = [Image.open(f).convert("RGB") for f in files]
h = max(i.height for i in ims)
w = sum(i.width for i in ims) + 8 * (len(ims) - 1)
m = Image.new("RGB", (w, h), (200, 200, 200))
x = 0
for i in ims:
    m.paste(i, (x, 0))
    x += i.width + 8
m = m.resize((m.width // 2, m.height // 2)) if m.width > 2000 else m
m.save(out)
