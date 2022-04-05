import datetime
import logging
import re

from mopidy.models import TlTrack
from mopidy_mpd.protocol import tagtype_list

logger = logging.getLogger(__name__)

# TODO: special handling of local:// uri scheme
normalize_path_re = re.compile(r"[^/]+")


def normalize_path(path, relative=False):
    parts = normalize_path_re.findall(path or "")
    if not relative:
        parts.insert(0, "")
    return "/".join(parts)


def track_to_mpd_format(track, position=None, stream_title=None):
    """
    Format track for output to MPD client.

    :param track: the track
    :type track: :class:`mopidy.models.Track` or :class:`mopidy.models.TlTrack`
    :param position: track's position in playlist
    :type position: integer
    :param stream_title: the current streams title
    :type position: string
    :rtype: list of two-tuples
    """
    if isinstance(track, TlTrack):
        (tlid, track) = track
    else:
        (tlid, track) = (None, track)

    if not track.uri:
        logger.warning("Ignoring track without uri")
        return []

    result = [
        ("file", track.uri),
        ("Time", track.length and (track.length // 1000) or 0),
        *multi_tag_list(track.artists, "name", "Artist"),
        ("Album", track.album and track.album.name or ""),
    ]

    if stream_title is not None:
        result.append(("Title", stream_title))
        if track.name:
            result.append(("Name", track.name))
    else:
        result.append(("Title", track.name or ""))

    if track.date:
        result.append(("Date", track.date))

    if track.album is not None and track.album.num_tracks is not None:
        result.append(
            ("Track", f"{track.track_no or 0}/{track.album.num_tracks}")
        )
    else:
        result.append(("Track", track.track_no or 0))
    if position is not None and tlid is not None:
        result.append(("Pos", position))
        result.append(("Id", tlid))

    if hasattr(track,'artwork'):
        result.append(('artwork',track.artwork))
    if hasattr(track,'like'):
        result.append(('like',track.like))

    if track.album is not None and track.album.musicbrainz_id is not None:
        result.append(("MUSICBRAINZ_ALBUMID", track.album.musicbrainz_id))

    if track.album is not None and track.album.artists:
        result += multi_tag_list(track.album.artists, "name", "AlbumArtist")

        musicbrainz_ids = concat_multi_values(
            track.album.artists, "musicbrainz_id"
        )
        if musicbrainz_ids:
            result.append(("MUSICBRAINZ_ALBUMARTISTID", musicbrainz_ids))

    if track.artists:
        musicbrainz_ids = concat_multi_values(track.artists, "musicbrainz_id")
        if musicbrainz_ids:
            result.append(("MUSICBRAINZ_ARTISTID", musicbrainz_ids))

    if track.composers:
        result += multi_tag_list(track.composers, "name", "Composer")

    if track.performers:
        result += multi_tag_list(track.performers, "name", "Performer")

    if track.genre:
        result.append(("Genre", track.genre))

    if track.disc_no:
        result.append(("Disc", track.disc_no))

    if track.last_modified:
        datestring = datetime.datetime.utcfromtimestamp(
            track.last_modified // 1000
        ).isoformat()
        result.append(("Last-Modified", datestring + "Z"))

    if track.musicbrainz_id is not None:
        result.append(("MUSICBRAINZ_TRACKID", track.musicbrainz_id))

    if track.album and track.album.uri:
        result.append(("X-AlbumUri", track.album.uri))

    result = [element for element in result if _has_value(*element)]

    return result


def _has_value(tagtype, value):
    """
    Determine whether to add the tagtype to the output or not.

    :param tagtype: the MPD tagtype
    :type tagtype: string
    :param value: the tag value
    :rtype: bool
    """
    if tagtype in tagtype_list.TAGTYPE_LIST:
        return bool(value)
    return True


def concat_multi_values(models, attribute):
    """
    Format Mopidy model values for output to MPD client.

    :param models: the models
    :type models: array of :class:`mopidy.models.Artist`,
        :class:`mopidy.models.Album` or :class:`mopidy.models.Track`
    :param attribute: the attribute to use
    :type attribute: string
    :rtype: string
    """
    # Don't sort the values. MPD doesn't appear to (or if it does it's not
    # strict alphabetical). If we just use them in the order in which they come
    # in then the musicbrainz ids have a higher chance of staying in sync
    return ";".join(
        getattr(m, attribute)
        for m in models
        if getattr(m, attribute, None) is not None
    )


def multi_tag_list(objects, attribute, tag):
    """
    Format multiple objects for output to MPD client in a list with one tag per
    value.

    :param objects: the model objects
    :type objects: array of :class:`mopidy.models.Artist`,
        :class:`mopidy.models.Album`, or :class:`mopidy.models.Track`
    :param attribute: the attribute to use
    :type attribute: string
    :param tag: the name of the tag
    :type tag: string
    :rtype: list of tuples of string and attribute value
    """

    return [
        (tag, getattr(obj, attribute))
        for obj in objects
        if getattr(obj, attribute, None) is not None
    ]


def tracks_to_mpd_format(tracks, start=0, end=None):
    """
    Format list of tracks for output to MPD client.

    Optionally limit output to the slice ``[start:end]`` of the list.

    :param tracks: the tracks
    :type tracks: list of :class:`mopidy.models.Track` or
        :class:`mopidy.models.TlTrack`
    :param start: position of first track to include in output
    :type start: int (positive or negative)
    :param end: position after last track to include in output
    :type end: int (positive or negative) or :class:`None` for end of list
    :rtype: list of lists of two-tuples
    """
    if end is None:
        end = len(tracks)
    tracks = tracks[start:end]
    positions = range(start, end)
    assert len(tracks) == len(positions)
    result = []
    for track, position in zip(tracks, positions):
        formatted_track = track_to_mpd_format(track, position)
        if formatted_track:
            result.append(formatted_track)
    return result


def playlist_to_mpd_format(playlist, *args, **kwargs):
    """
    Format playlist for output to MPD client.

    Arguments as for :func:`tracks_to_mpd_format`, except the first one.
    """
    return tracks_to_mpd_format(playlist.tracks, *args, **kwargs)
