# ai.py
#
# Copyright 2026 The High Tide Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Support for TIDAL's AI-generated content labels.

TIDAL marks fully AI-generated tracks (and albums) with an ``ai`` boolean in
its catalog responses. python-tidal 0.8.x does not copy that field onto its
models, so :func:`install` extends the model parsers to keep it. The value is
then available as ``track.ai`` / ``album.ai``.

TIDAL's own "Allow AI content" preference lives in each client's local
storage and is not exposed through the API, so the preference in High Tide is
kept locally too.
"""

import logging
from collections.abc import Iterable
from typing import Any, ClassVar

from gi.repository import GObject
from tidalapi.album import Album
from tidalapi.media import Media

logger = logging.getLogger(__name__)


class _AISettings(GObject.GObject):
    """Notifies widgets when the AI label visibility changes."""

    __gsignals__: ClassVar[dict] = {
        "labels-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }


settings = _AISettings()

AI_MODE_SHOW = "show"
AI_MODE_HIDE_IN_PLAYLISTS = "hide-in-playlists"
AI_MODE_REMOVE = "remove"

#: Order used by the preference combo row.
AI_MODES = (AI_MODE_SHOW, AI_MODE_HIDE_IN_PLAYLISTS, AI_MODE_REMOVE)

DEFAULT_AI_MODE = AI_MODE_HIDE_IN_PLAYLISTS

_mode = DEFAULT_AI_MODE
_show_labels = True
_installed = False


def install() -> None:
    """Teach python-tidal to retain TIDAL's ``ai`` catalog flag.

    Safe to call more than once. If (a future version of) python-tidal already
    exposes the flag, the patches still work and simply set the same value.
    """

    global _installed
    if _installed:
        return

    original_media_parse = Media.parse
    original_album_parse = Album.parse

    def media_parse_with_ai(self: Any, json_obj: Any, album: Any = None) -> None:
        original_media_parse(self, json_obj, album)
        self.ai = bool(json_obj.get("ai", False))

    def album_parse_with_ai(
        self: Any, json_obj: Any, artist: Any = None, artists: Any = None
    ) -> Album:
        parsed = original_album_parse(self, json_obj, artist, artists)
        parsed.ai = bool(json_obj.get("ai", False))
        return parsed

    Media.parse = media_parse_with_ai
    Album.parse = album_parse_with_ai
    _installed = True


def get_mode() -> str:
    """Return the current AI content preference."""

    return _mode


def set_mode(mode: str) -> None:
    """Set the current AI content preference."""

    global _mode
    if mode not in AI_MODES:
        logger.warning("Unknown AI content mode %r, using default", mode)
        mode = DEFAULT_AI_MODE
    _mode = mode


def get_show_labels() -> bool:
    """Return whether AI badges should be displayed."""

    return _show_labels


def set_show_labels(show: bool) -> None:
    """Show or hide AI badges, notifying any visible widgets."""

    global _show_labels
    show = bool(show)
    if _show_labels == show:
        return
    _show_labels = show
    settings.emit("labels-changed")


def is_ai(item: Any) -> bool:
    """Return whether a TIDAL track or album is labelled AI-generated."""

    return bool(getattr(item, "ai", False))


def is_track_allowed(track: Any, context: str | None = None) -> bool:
    """Return whether a track may be shown/played in a given context.

    Args:
        track: A TIDAL track.
        context: ``"playlist"`` when the track comes from a playlist. ``None``
            for albums, mixes, search, the queue, and playback.
    """

    if not is_ai(track):
        return True
    if _mode == AI_MODE_REMOVE:
        return False
    return not (_mode == AI_MODE_HIDE_IN_PLAYLISTS and context == "playlist")


def filter_tracks(tracks: Iterable[Any], context: str | None = None) -> list[Any]:
    """Filter AI tracks out of a list according to the current preference."""

    return [track for track in tracks if is_track_allowed(track, context)]
