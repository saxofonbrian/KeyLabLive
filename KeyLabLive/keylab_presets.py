# =============================================================================
# KeyLabLive - PRESETS
# =============================================================================
#
# One preset list, shared by every track, and loaded by hot-swapping a
# track's instrument.
#
# TWO FILES, TWO SOURCES
#   The list on screen is built from two files, and the whole design rests on
#   keeping them apart. They have different owners and different places to look
#   a preset up:
#
#     presets-manual.txt   Yours. The script READS it and never writes it.
#                          Looked up in the browser at large - see
#                          PRESET_SEARCH_ROOTS. Nothing has to be tagged.
#
#     presets.txt          The script's. Rewritten on every Cycle from your
#                          Collection, and looked up in that Collection.
#
#   The manual list comes first on screen, then the tagged one. Chapters are
#   matched by name, so "Racks" in both files is one chapter.
#
#   Because nothing writes to the manual file, nothing can lose what is in it.
#   That is the entire reason it is a separate file rather than a marked block
#   inside the other one.
#
# HOW THE TAGGED LIST WORKS
#   1. You tag presets in Live's browser with one Collection.
#   2. The script indexes that Collection and writes presets.txt.
#   3. Choosing an entry hot-swaps it into the instrument on the track whose
#      button you held.
#
#   Untagging a preset does not delete your work. The line moves to a
#   remembered block at the bottom of presets.txt, marked "#~", and comes back
#   with its chapter if the preset is ever tagged again.
#
# THE LINE FORMAT, IN BOTH FILES
#   One line per preset: "Preset name, Chapter". The name is the preset's own
#   name in the browser - there is no second, prettier name to keep in step
#   with it. The chapter is optional and is yours; use none anywhere and there
#   are no chapters at all.
#
# WHY ONE LIST AND NOT ONE PER TRACK
#   A track here is a slot, not an instrument. It becomes whatever preset you
#   load into it, so a preset does not belong to a particular track and there
#   is nothing to divide up. One Collection also leaves the other six of Live's
#   own Collections alone, which are the user's, not ours.
#
# There is no Max for Live device, no extra track, no Program Change and no
# pre-built rack. The track becomes whatever preset you pick - an Analog, an
# Operator, an Instrument Rack with a plugin inside it. The track is a slot.
#
# WHAT IT CAN LOAD
#   Anything Live's own hot-swap accepts in an instrument slot: Live's
#   instruments, Instrument Racks (.adg), Sounds, Packs and plugin presets.
#   Not audio effect presets - that is Live's filter, not ours.
#
# WHAT IT COSTS
#   A hot-swap RELOADS the device. Held notes are cut, and a large sampled
#   instrument takes as long to load as it takes. This is inherent to preset
#   files and cannot be coded away. Switch between songs or sections, not in
#   the middle of a phrase. Two heavy sounds that alternate within one song
#   still belong on two tracks.
#
# This file owns the entire "import Live" and all browser knowledge, so the
# rest of the script has no dependency on either.
# =============================================================================

from __future__ import absolute_import, print_function, unicode_literals

import os

import Live

from .keylab_config import LABEL_MAX_LEN

# Browser roots that may be used in a path. "colors" is Collections, the
# coloured labels at the top of Live's sidebar; "user_folders" is Places.
BROWSER_ROOTS = (
    "colors", "user_folders", "user_library", "instruments", "sounds",
    "drums", "audio_effects", "midi_effects", "plugins", "packs",
    "clips", "samples", "max_for_live", "current_project",
)

# Extensions stripped before names are compared. Live's browser shows presets
# without an extension and the files on disk have one, so it is removed at
# both ends: a preset file may name a preset with or without ".adg" and it
# lands the same.
STRIPPED_EXTENSIONS = (".adv", ".adg", ".amxd", ".adp", ".alc", ".aupreset", ".fxp")

# How deep to walk. A Collection is flat, so this is only a safety limit.
MAX_DEPTH = 10


def _words(text):
    """Split on anything that is not a letter or digit. '80-beat' is two."""
    out, current = [], []
    for ch in (text or ""):
        if ch.isalnum():
            current.append(ch)
        elif current:
            out.append("".join(current))
            current = []
    if current:
        out.append("".join(current))
    return out


def _norm(text):
    """Lower case, trimmed, and without the extension on the last path part."""
    value = (text or "").strip().replace("\\", "/").lower()
    if not value:
        return ""
    head, _sep, tail = value.rpartition("/")
    for ext in STRIPPED_EXTENSIONS:
        if tail.endswith(ext):
            tail = tail[:-len(ext)]
            break
    return (head + "/" + tail) if head else tail


def preset_key(name):
    """
    A preset name reduced to what the index compares: case, surrounding space
    and the file extension folded away. Two names with the same key are the
    same preset, which is how the two lists are joined without duplicates.
    """
    return _norm(name)


def short_label(preset_name, limit=LABEL_MAX_LEN):
    """
    A preset's name cut down to what a screen button can show.

    Used when the footer is drawn, not when the file is written - the file
    holds the preset's real name and nothing else.

    The cut falls on a word boundary when one lands near the end, so
    "Ac Strings Pizz Stage" becomes "Ac Strings". When the first word alone
    fills most of the space it cuts mid-word instead, because "Organ Transi"
    tells you which organ and "Organ" does not.

    The list on screen is NOT cut: list_item_packet sends the name whole. Only
    the footer and the popup are this narrow.
    """
    name = (preset_name or "").strip()
    if len(name) <= limit:
        return name
    cut = name[:limit]
    space = cut.rfind(" ")
    if space >= limit - 4:
        return cut[:space].strip()
    return cut.strip()


# A remembered line: a preset that is no longer tagged, kept so that its
# chapter and its place come back if it is tagged again. Two characters, not
# one, because the file's own explanatory header is full of commas and a plain
# "#" line would be indistinguishable from a preset.
REMEMBERED = "#~"


def _read_lines(path):
    """The file's lines, or [] if it is not there. A missing file is normal."""
    try:
        with open(path, "r") as handle:
            return handle.read().splitlines()
    except (IOError, OSError):
        return []


def _parse_entry(body):
    """'Preset, Chapter' -> (preset, chapter), or None if there is no preset."""
    preset, _sep, chapter = body.partition(",")
    preset, chapter = preset.strip(), chapter.strip()
    return (preset, chapter) if preset else None


def load_manual_file(path):
    """
    Read the hand-written list. Returns [(preset_name, chapter)] in file order.

    Nothing writes to this file, so there is no remembered block and no merge -
    what it says is what you get. "#" starts a comment; a missing file is an
    empty list, which is the normal state for anyone who has not made one.
    """
    entries = []
    for raw in _read_lines(path):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entry = _parse_entry(line)
        if entry:
            entries.append(entry)
    return entries


def load_preset_file(path):
    """
    Read the tagged preset file. Returns (entries, remembered), each a list of
    (preset_name, chapter) in file order.

    One entry per line, "Preset name, Chapter". The chapter is optional; a line
    with no comma is simply a preset with no chapter. Blank lines and comments
    are ignored - except lines starting with "#~", which are the remembered
    ones.
    """
    entries, remembered = [], []
    for raw in _read_lines(path):
        line = raw.strip()
        if not line:
            continue
        if line.startswith(REMEMBERED):
            body, target = line[len(REMEMBERED):].strip(), remembered
        elif line.startswith("#"):
            continue
        else:
            body, target = line, entries
        entry = _parse_entry(body)
        if entry:
            target.append(entry)
    return entries, remembered


def write_preset_file(path, entries, remembered, collection):
    """Write the preset file. Returns True on success."""
    lines = [
        "# Written by KeyLabLive - but your edits are kept.",
        "#",
        "# This list is the '%s' Collection in Live's browser, and it is the" % collection,
        "# same list on every track - a track becomes whatever you load",
        "# into it, so any preset can go anywhere.",
        "#",
        "# Tag a preset with that Collection, press Cycle, and it appears here.",
        "# Remove the tag and the line moves down to the remembered block at",
        "# the bottom; tag it again and it comes back with its chapter intact.",
        "#",
        "# FORMAT   Preset name, Chapter",
        "#",
        "# The preset name is its name in Live's browser. Leave it alone - it is",
        "# how the preset is found. Long names are cut to %d characters on the" % LABEL_MAX_LEN,
        "# screen button, but the list itself shows them whole.",
        "#",
        "# The chapter is yours, and optional. Presets with the same chapter are",
        "# shown together, and Tap and Metro step between chapters while a list",
        "# is open. Chapters appear in the order they first appear in this file.",
        "# Give no preset a chapter and there are no chapters at all - one flat",
        "# list, and Tap and Metro have no chapters to step between.",
        "#",
        "# You may reorder the lines, and the order sticks. Newly tagged presets",
        "# land at the end with no chapter, so the order you know never",
        "# shuffles under your fingers.",
        "#",
        "# This is not the only list. presets-manual.txt is yours alone - this",
        "# script never writes to it - and its presets come FIRST on screen,",
        "# without being tagged at all. Put a preset there if you want it on the",
        "# list permanently, here if you want to tag it in and out.",
        "",
    ]
    for preset, chapter in entries:
        lines.append("%s, %s" % (preset, chapter) if chapter else preset)

    if remembered:
        lines.extend([
            "",
            "# ---------------------------------------------------------------",
            "# Remembered: tagged once, not tagged now. These are not in the",
            "# list. Tag one again and it returns above with its chapter. Delete",
            "# a line to forget it for good.",
            "# ---------------------------------------------------------------",
        ])
        for preset, chapter in remembered:
            lines.append("%s %s, %s" % (REMEMBERED, preset, chapter)
                         if chapter else "%s %s" % (REMEMBERED, preset))

    try:
        with open(path, "w") as handle:
            handle.write("\n".join(lines) + "\n")
        return True
    except (IOError, OSError):
        return False


def merge_preset_entries(existing, remembered, names):
    """
    Work out the new list from what the Collection holds now, what the file
    says already, and what the file remembers from before.

    Returns (entries, remembered).

    Kept from the file: the chapter of any preset still in the Collection, and
    the order those presets were in.
    Brought back: a preset in the remembered block that has been tagged again -
    it returns with the chapter it had.
    Done for you: presets new to the Collection are appended with no chapter;
    presets no longer in it move down to the remembered block.

    So the Collection decides WHAT is on the list, and the file decides which
    CHAPTER each preset is in and in WHICH ORDER. Nothing you have written is
    ever thrown away by an untag - only by deleting the line yourself.
    """
    by_key = {}
    for name in names:
        by_key.setdefault(_norm(name), name)

    ordered, placed = [], set()
    for preset, chapter in existing:
        key = _norm(preset)
        if key in by_key and key not in placed:
            placed.add(key)
            ordered.append((by_key[key], chapter))

    still = []
    for preset, chapter in remembered:
        key = _norm(preset)
        if key in by_key:
            if key not in placed:
                placed.add(key)
                ordered.append((by_key[key], chapter))
        else:
            still.append((preset, chapter))

    # Anything dropped from the list keeps its chapter in the remembered block.
    known = set(_norm(p) for p, _c in still)
    for preset, chapter in existing:
        key = _norm(preset)
        if key not in by_key and key not in known:
            known.add(key)
            still.append((preset, chapter))

    for key, name in by_key.items():
        if key not in placed:
            ordered.append((name, ""))
    return ordered, still


def chapters_of(entries):
    """
    The chapter names in the order they first appear, with the presets that
    have no chapter last under an empty name.

    Returns [] when no preset has a chapter - the signal that this set does not
    use chapters at all, and that the chapter buttons should do nothing.
    """
    names, seen, has_blank = [], set(), False
    for _preset, chapter in entries:
        if not chapter:
            has_blank = True
        elif chapter not in seen:
            seen.add(chapter)
            names.append(chapter)
    if not names:
        return []
    if has_blank:
        names.append("")
    return names



class PresetBrowser(object):
    """
    The browser index and the hot-swap itself, shared by every track.

    THE INDEX IS SMALL ON PURPOSE, and is filled from two directions:

      roots         The Collection named in keylab_config.py, walked whole. It
                    holds exactly what you have tagged and nothing else - a
                    dozen entries, not the library's thirty thousand.

      search_roots  Wide parts of the browser - instruments, sounds - walked
                    only to find the names in presets-manual.txt, and adding
                    ONLY those. A hundred hand-written names cost a hundred
                    index entries however large the library is.

    So the manual list needs nothing tagged, and Cycle still answers quickly.
    The walk itself is the cost, and it stops the moment the last wanted name
    is found.
    """

    def __init__(self, surface, roots, search_roots=()):
        self._surface = surface
        self._roots = list(roots)
        self._search_roots = list(search_roots)
        self._wanted = []          # names from the manual file, in file order
        self._filter = None        # while set: only these keys may be indexed
        self._search_spent = False  # a search walk ran and found nothing
        self._index = {}
        self._count = 0
        self._ready = False

    # -- index ---------------------------------------------------------------

    def index_size(self):
        return self._count

    def set_manual_names(self, names):
        """
        The names the manual file asks for. Changing them invalidates the
        index, because the search roots are walked for these names alone.
        """
        wanted = [n for n in (names or []) if _norm(n)]
        if wanted != self._wanted:
            self._wanted = wanted
            self._ready = False
            self._search_spent = False

    def reload(self):
        """Force a rebuild. Returns the number of presets found."""
        self._ready = False
        self._search_spent = False
        self.warm()
        return self._count

    def warm(self):
        """Build the index if it is not built. Happens once."""
        if self._ready:
            return
        self._index = {}
        self._count = 0
        self._filter = None
        try:
            browser = self._surface.application().browser
        except (AttributeError, RuntimeError) as exc:
            self._log("browser unavailable (%r)" % (exc,))
            return

        for spec in self._roots:
            root = self._resolve_root(browser, spec)
            if root is None:
                self._log("root not found: %s - is the Collection named "
                          "exactly that?" % spec)
                continue
            before = self._count
            self._walk(root, "", 0)
            self._log("root '%s': %d preset(s)" % (spec, self._count - before))

        self._search_for_manual(browser)

        # Only call it ready if something was found. Live may still be
        # scanning the library just after startup, and an empty index must not
        # lock itself in as finished - every lookup would fail for the rest of
        # the session.
        if self._count > 0:
            self._ready = True
        self._log("indexed %d preset(s) from %s"
                  % (self._count, ", ".join(self._roots)))

    def _search_for_manual(self, browser):
        """
        Walk the search roots for the manual file's names, and index nothing
        else. Skipped entirely when the manual file is empty or every name it
        asks for is already tagged.
        """
        # A walk that came back with nothing is not repeated. warm() is called
        # again every few ticks while the index is empty, in case Live is still
        # scanning - and re-walking the whole library eight times over would
        # cost far more than the empty index it is trying to fix.
        if self._search_spent:
            return

        missing = set()
        for name in self._wanted:
            key = _norm(name)
            if key and key not in self._index:
                missing.add(key)
        if not missing or not self._search_roots:
            if missing:
                self._log("%d manual preset(s) not found - PRESET_SEARCH_ROOTS "
                          "is empty, so only tagged presets are indexed"
                          % len(missing))
            return

        self._filter = missing
        found_before = self._count
        try:
            for spec in self._search_roots:
                if not self._filter:
                    break
                root = self._resolve_root(browser, spec)
                if root is None:
                    self._log("search root not found: %s" % spec)
                    continue
                before = self._count
                self._walk(root, "", 0)
                self._log("search root '%s': %d manual preset(s) found"
                          % (spec, self._count - before))
            if self._filter:
                self._log("%d manual preset(s) still not found: %s"
                          % (len(self._filter),
                             " | ".join(sorted(self._filter)[:8])))
            self._search_spent = (self._count == found_before)
        finally:
            self._filter = None

    def list_items(self, spec):
        """
        Every loadable item under one root, in the browser's own order. Used to
        write the preset file. Goes one level into sub-folders - a Collection
        is flat, and a deep walk here would pull in the library.
        """
        try:
            browser = self._surface.application().browser
        except (AttributeError, RuntimeError):
            return []
        root = self._resolve_root(browser, spec)
        if root is None:
            return []

        names, seen = [], set()

        def collect(item, depth):
            for child in self._children_of(item):
                name = self._name_of(child)
                if not name:
                    continue
                if self._is_loadable(child):
                    key = _norm(name)
                    if key not in seen:
                        seen.add(key)
                        names.append(name)
                elif depth < 1:
                    collect(child, depth + 1)

        collect(root, 0)
        return names

    # -- lookup --------------------------------------------------------------

    def resolve(self, name):
        """Find a preset by name. Tolerant about folders and extensions."""
        self.warm()
        wanted = _norm(name)
        if not wanted:
            return None

        item = self._index.get(wanted)
        if item is not None:
            return item

        suffix = "/" + wanted
        for indexed, candidate in self._index.items():
            if indexed.endswith(suffix):
                return candidate

        tail = wanted.rpartition("/")[2]
        if tail and tail != wanted:
            item = self._index.get(tail)
            if item is not None:
                return item
            tail_suffix = "/" + tail
            for indexed, candidate in self._index.items():
                if indexed.endswith(tail_suffix):
                    return candidate

        self._log_near_misses(wanted, tail or wanted)
        return None

    def name_matches(self, preset_name, device_name):
        """
        Whether a device looks like it came from this preset. A loaded preset
        takes its own name, so this is how the script recognises what is
        already on a track. It is a name coincidence, not a fact - the device
        may have been renamed by hand - so nothing depends on it alone.
        """
        a, b = _norm(preset_name), _norm(device_name)
        if not a or not b:
            return False
        return a == b or a.endswith("/" + b) or a.split("/")[-1] == b

    # -- loading -------------------------------------------------------------

    def find_instrument(self, track):
        """
        The first instrument device on a track.

        Deliberately by TYPE and not by position: after a hot-swap the device
        may be something else entirely - an Analog replaced by an Instrument
        Rack - and it still has to be found next time.
        """
        try:
            devices = track.devices
        except (AttributeError, RuntimeError):
            return None
        for device in devices:
            try:
                if device.type == Live.Device.DeviceType.instrument:
                    return device
            except (AttributeError, RuntimeError):
                continue
        return None

    def load(self, track, device, name):
        """
        Hot-swap a preset into a track's instrument.
        Returns (True, name) or (False, reason).

        THE ORDER BELOW IS NOT OPTIONAL. The track and the device must be SELECTED before hotswap_target
        is set. Ableton's own code only ever points hotswap_target at something
        that is already selected.

        Skip the selection and Live stores the value quite happily - reading it
        back looks correct - but hot-swap is not actually armed, and load_item
        falls back to INSERTING a new device on whichever track happened to be
        selected. The symptom is instruments appearing on a completely
        different track.
        """
        item = self.resolve(name)
        if item is None:
            return False, "preset '%s' not in the browser (%d indexed)" % (
                name, self._count)

        try:
            browser = self._surface.application().browser
            song = self._surface.song()
        except (AttributeError, RuntimeError) as exc:
            return False, "browser/song unavailable (%r)" % (exc,)

        ok, why = self._select(song, track, device)
        if not ok:
            return False, why

        self._show_device_view()

        engaged = False
        try:
            try:
                browser.hotswap_target = device
                engaged = True
            except RuntimeError as exc:
                return False, "device cannot be hot-swapped (%s)" % (exc,)

            # Guard 1, deliberately lenient. It checks that there IS a target,
            # not that it is the same Python object: Live can hand back a new
            # wrapper for the same device, and a strict identity test would
            # silently reject a perfectly good swap.
            try:
                target = browser.hotswap_target
            except Exception:
                return False, "could not read the hot-swap target"
            if target is None:
                return False, "hot-swap did not engage - nothing loaded"

            # Guard 2, the strict one. If Live falls back to inserting instead
            # of swapping, it inserts on the SELECTED track - so that had
            # better be ours. This is what stops a preset landing on another
            # track.
            try:
                if song.view.selected_track != track:
                    return False, "selected track is not the target - nothing loaded"
            except Exception:
                return False, "could not confirm the selected track"

            browser.load_item(item)
            return True, name

        except Exception as exc:
            return False, "failed loading '%s' (%r)" % (name, exc)
        finally:
            if engaged:
                try:
                    browser.hotswap_target = None
                except Exception:
                    pass

    def _select(self, song, track, device):
        """
        Select the track and the device - the precondition for hot-swap.

        select_device belongs to Live.Song.Song.View, NOT Live.Track.Track.View.
        Calling it on a track's view raises AttributeError: 'View' object has
        no attribute 'select_device'.
        """
        try:
            song.view.selected_track = track
        except (AttributeError, RuntimeError) as exc:
            return False, "could not select the track (%r)" % (exc,)
        try:
            song.view.select_device(device)
        except (AttributeError, RuntimeError) as exc:
            # The track is selected by this point, and Live selects the first
            # device on a newly selected track by itself, so hot-swap still has
            # a fair chance. Guard 2 keeps any fallback on our own track.
            self._log("could not select the device (%r) - continuing" % (exc,))
        return True, None

    def _show_device_view(self):
        """
        Bring the device chain into view, as Ableton's own hot-swap does.
        """
        try:
            view = self._surface.application().view
            if view.is_view_visible("Detail") and view.is_view_visible("Detail/DeviceChain"):
                return
            view.show_view("Detail")
            view.show_view("Detail/DeviceChain")
        except Exception as exc:
            self._log("could not show the device view (%r)" % (exc,))

    def shutdown(self):
        """Never leave Live sitting in hot-swap mode."""
        try:
            self._surface.application().browser.hotswap_target = None
        except Exception:
            pass

    # -- browser walking -----------------------------------------------------

    def _resolve_root(self, browser, spec):
        segments = [s for s in spec.replace("\\", "/").split("/") if s]
        if not segments:
            return None
        first = segments[0].strip().lower().replace(" ", "_")
        if first not in BROWSER_ROOTS:
            self._log("unknown browser root '%s'" % segments[0])
            return None
        try:
            node = getattr(browser, first)
        except (AttributeError, RuntimeError):
            return None
        if node is None:
            return None
        for segment in segments[1:]:
            node = self._child_named(node, segment)
            if node is None:
                return None
        return node

    def _child_named(self, item, name):
        wanted = name.strip().lower()
        for child in self._children_of(item):
            if (self._name_of(child) or "").strip().lower() == wanted:
                return child
        return None

    @staticmethod
    def _name_of(item):
        try:
            return item.name or ""
        except (AttributeError, RuntimeError):
            return ""

    @staticmethod
    def _is_loadable(item):
        try:
            return bool(item.is_loadable)
        except (AttributeError, RuntimeError):
            return False

    @staticmethod
    def _children_of(item):
        try:
            children = item.children
        except (AttributeError, RuntimeError):
            # Some browser roots are a SEQUENCE of items rather than one item
            # with children - Collections among them. Then there is nothing to
            # read from .children and the contents are the object itself.
            try:
                return tuple(item)
            except TypeError:
                return ()
        return children or ()

    def _walk(self, item, path, depth):
        if depth > MAX_DEPTH:
            return
        for child in self._children_of(item):
            # While searching for the manual file's names, stop the moment the
            # last one is found. On a large library that is most of the saving.
            if self._filter is not None and not self._filter:
                return
            name = self._name_of(child)
            if not name:
                continue
            child_path = ("%s/%s" % (path, name)) if path else name
            if self._is_loadable(child):
                self._add(name, child_path, child)
            # A device entry is both loadable AND has children (its presets),
            # so keep walking either way.
            self._walk(child, child_path, depth + 1)

    def _add(self, name, path, item):
        name_key = _norm(name)
        if self._filter is not None:
            # A filtered walk indexes wanted names only, and by name alone -
            # the manual file gives a name, never a path.
            if name_key not in self._filter:
                return
            self._filter.discard(name_key)
            self._index[name_key] = item
            self._count += 1
            return
        path_key = _norm(path)
        if path_key and path_key not in self._index:
            self._index[path_key] = item
            self._count += 1
        if name_key and name_key not in self._index:
            self._index[name_key] = item

    # -- diagnostics ---------------------------------------------------------

    def _log_near_misses(self, wanted, tail):
        """
        Say what the index actually holds near what was asked for. "Not found
        among 33000" on its own tells you nothing.
        """
        try:
            words = sorted((w for w in _words(tail) if len(w) > 2),
                           key=len, reverse=True)
            near = []
            if words:
                needle = words[0]
                for indexed in self._index:
                    # Word boundary, not substring: "user" must not match
                    # "trouserpants".
                    if any(w.startswith(needle)
                           for w in _words(indexed.rpartition("/")[2])):
                        near.append(indexed)
                        if len(near) >= 8:
                            break
            sample = list(self._index)[:6]
            self._log("'%s' not found. Near misses: %s"
                      % (wanted, " | ".join(near) if near else "none"))
            self._log("index sample: %s" % (" | ".join(sample),))
        except Exception:
            pass

    def _log(self, message):
        try:
            self._surface.log_message("KeyLabLive/presets: %s" % message)
        except Exception:
            pass
