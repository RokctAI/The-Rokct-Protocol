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

"""Level 2: audio composition. An ad (or any spoken spot) JSON in, a mixed,
mastered file out: voices from the line cache, a procedural music bed and
sound effects, ducking, loudness and true-peak mastering.

Moved verbatim from RokctAI/factory radio_ads/adfactory (2026-11-20, step 4
of the one-engine move); factory's radio_ads/make_ad.py now calls this.
Defaults that used to sit beside the code (voices/, cache/, relative paths
in an ad) resolve against ROKCT_MEDIA_COMPOSE_ROOT, else the working folder.
"""
