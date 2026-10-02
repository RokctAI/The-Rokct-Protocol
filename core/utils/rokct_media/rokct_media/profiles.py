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

"""Output profiles: loudness and format per destination (spec section 2).

This version renders the level-1 profiles. The others are listed so a job
that names one gets a clear "not in this version" rather than a typo error.
"""
from __future__ import annotations

PROFILES = {
    "clip_wav": {"level": 1, "format": "wav", "sample_rate": 24_000, "channels": 1, "subtype": "PCM_16",
                 "rms_dbfs": -20.0, "peak_max": 0.99, "true_peak_max_dbtp": 0.0},
    "app_r3_mp3": {"level": 1, "format": "mp3", "bitrate_kbps": 64, "sample_rate": 24_000, "channels": 1,
                   "rms_dbfs": -20.0},
    "lesson_replay": {"level": 2},
    "broadcast_r128": {"level": 2, "lufs": -23.0, "true_peak_max_dbtp": -1.0},
    "radio_streaming": {"level": 2, "lufs": -16.0, "true_peak_max_dbtp": -1.0},
    "audiobook_acx": {"level": 2},
    "audiobook_streaming": {"level": 2, "lufs": -18.0, "true_peak_max_dbtp": -2.0},
    "tiktok_9x16": {"level": 3, "lufs": -16.0, "true_peak_max_dbtp": -1.5, "fps": 30},
    "fb_reel_9x16": {"level": 3, "lufs": -16.0, "true_peak_max_dbtp": -1.5, "fps": 30},
    "yt_short_9x16": {"level": 3, "lufs": -16.0, "true_peak_max_dbtp": -1.5, "fps": 30},
}
IMPLEMENTED = ("clip_wav", "app_r3_mp3")
