# =============================================================================
# KeyLabLive - SETTINGS
# =============================================================================
#
# Everything you are meant to change lives in this file. Nothing else needs
# editing to set the script up for your own Live set.
#
# This file imports nothing, so every other module can read from it without
# any risk of a circular import. Keep it that way.
#
# What is NOT here: the SysEx packet formats, the screen layout bytes and the
# keyboard's CC and LED numbers. Those are not settings - they are measured
# facts about the hardware, and changing them does not reconfigure anything,
# it just breaks the display. They live in keylab_screen.py, marked as such.
#
# After editing this file, press the Cycle button on the keyboard. Only the
# preset list and the browser index reload that way; anything else here needs
# Live restarted.
# =============================================================================


# -----------------------------------------------------------------------------
# TRACKS
# -----------------------------------------------------------------------------
# One screen button, one track, one fader - entirely by POSITION, not by
# name: track 1 is whatever your first track is, in Live's own order,
# however it happens to be named. Loading a preset replaces the instrument,
# and Live renames an un-renamed track after whatever device it now holds -
# a track called "Pad" can become "Grand Piano" ten seconds later, and
# nothing here depends on that name ever being right.
#
# The script finds your tracks itself and assigns them to screen buttons
# 1-4, then 5-8 if you have more than four - see SCREEN_BUTTONS in
# keylab_screen.py for exactly which CC and footer id each position gets.
# There is nothing to configure here for a normal set; the one thing this
# file controls is the ceiling.
#
# MAX_TRACKS exists because the keyboard has exactly eight screen buttons in
# this row - that is a hardware fact, not a preference, and raising this
# past 8 does nothing (there is no ninth button to assign it to). Lowering
# it is a real choice: set it to 4, say, to keep this script off track 5 and
# up even if your set has more - to leave those tracks for something else
# you control a different way.
MAX_TRACKS = 8

# All tracks pick from the SAME preset list - see PRESET_COLLECTION below. A
# track is a slot that becomes whatever preset you load into it, so there is
# nothing to divide up: any preset can go on any track.
#
# Arm state is NOT set here. It comes from the Live set itself, exactly like
# any other track property Live saves - open a set with track 3 armed, and
# track 3 is armed when this script starts. Nothing here overwrites that.
#
# There is no starting volume here either. Volumes belong to your set, and
# the script does not touch them until you move a fader - see FADERS further
# down in this file.


# -----------------------------------------------------------------------------
# PRESETS
# -----------------------------------------------------------------------------

# The ONE Collection every track picks from. Collections are the coloured
# labels at the top of Live's browser sidebar. Tagging a preset with one is
# just that - a tag. The preset stays where it is on disk, nothing is copied,
# and the same name may exist elsewhere in the library without confusing
# anything.
#
# Rename one of Live's own Collections to this name. Which colour it happens to
# be does not matter: the script looks it up by NAME.
#
# One list for every track is deliberate. A track here is a slot that
# becomes whatever you load into it, so a preset does not belong to a
# particular track, and a list per track would be that many near-identical
# things to keep tidy instead of one.
PRESET_COLLECTION = "Presets"

# The file the script writes that list to, in this folder. One line per preset,
# "Preset name, Chapter". You open it to sort presets into chapters or to
# change the order of the list.
PRESET_FILE = "presets.txt"

# The OTHER list - the hand-written one. Same format, same folder, and the
# script never writes to it. It is read at startup and on every Cycle, and its
# presets appear FIRST on screen, ahead of the tagged ones.
#
# The point of it is that nothing here has to be tagged. Type a preset's name
# as Live's browser spells it, give it a chapter if you like, and it is on the
# list. Because nothing writes to the file, nothing can move or delete what you
# put in it.
#
# Use the manual list for the sounds that are always there, and the Collection
# for what you tag in and out as you work. Chapters are shared between the two:
# "Racks" in both files is one chapter.
#
# The file does not have to exist. Without it you simply have the tagged list.
PRESET_FILE_MANUAL = "presets-manual.txt"

# Where the manual list's presets are looked up. The Collection is indexed
# whole, but these roots are only searched for the names your manual file
# actually asks for - nothing else from them is indexed - so a hundred
# hand-written names cost a hundred entries no matter how large your library
# is.
#
# The walk itself takes time, and how much depends on how many Packs you have
# installed. It happens at startup and on Cycle, never while you are playing.
# If Cycle feels slow, cut this list down or empty it: with no search roots,
# only tagged presets are found, and any manual line that is not also tagged
# goes quiet.
#
# "instruments" covers Live's own devices and their presets. "sounds" covers
# the Instrument Racks from Packs - that is where Grand Piano and the rest of
# the multisampled instruments live. Add "packs", "user_library" or
# "user_folders" if your own presets are somewhere else.
PRESET_SEARCH_ROOTS = ["instruments", "sounds"]

# Where the script looks for presets. A Collection is by far the best choice:
# it holds a reference, not a copy, so your presets stay where they are, the
# index stays tiny, and the same name can exist elsewhere in the library
# without causing confusion.
#
# This setting only decides the FORM of the browser path. Leave it alone unless
# you want to use a folder instead of a Collection, in which case:
#
#   "colors/%s"        a Collection            (default)
#   "user_library/%s"  a folder in User Library
#   "user_folders/%s"  one of your own Places folders
#
# The %s is replaced by PRESET_COLLECTION above.
PRESET_ROOT_FORMAT = "colors/%s"

# Set False to stop the script writing presets.txt, and maintain that file by
# hand instead. The Collection is then ignored entirely. This has no effect on
# the manual file above, which is never written either way.
PRESET_FILES_AUTO = True

# Longest text the screen buttons can show. Longer names are cut for you when
# the button is drawn: at a word boundary if one falls near the end - "Ac
# Strings Pizz Stage" becomes "Ac Strings" - and mid-word otherwise, because
# "Organ Transi" tells you which organ where "Organ" would not. The list on
# screen is not cut at all; this is the button only.
LABEL_MAX_LEN = 12

# Chapters wrap: past the last chapter is the first again. Set False and the
# ends are ends. Wrapping means you can always reach any chapter by holding one
# button down; not wrapping means you can feel where the list stops.
CHAPTER_WRAP = True

# The list's title reads "< Racks 2/4 >" rather than "Racks": the arrows point
# at Tap and Metro, which sit at the two ends of the transport row, and the
# count says whether there is anywhere to go. Set False for the bare name.
#
# Only shown when there are at least two chapters to move between.
CHAPTER_TITLE_ARROWS = True

# A preset with no chapter of its own is put in a chapter named after the file
# it came from, so the chapter on screen says where the preset came from rather
# than that a field was left empty.
#
#   CHAPTER_TAGGED    presets.txt - what you tagged with the Collection.
#                     Newly tagged presets arrive with no chapter, so this is
#                     where they land until you sort them.
#   CHAPTER_UNNAMED   presets-manual.txt - a hand-written line with no chapter.
#                     The list that ships gives every line a chapter, so you
#                     will not see this one unless you add a line without.
#
# Give a preset a chapter of its own and it goes there instead; give every
# preset one and neither of these ever appears.
#
# Both are only used if SOMETHING has a chapter. With no chapters anywhere
# there are no chapters at all - one flat list, and Tap and Metro stay dark.
CHAPTER_TAGGED = "Collection"
CHAPTER_UNNAMED = "Other"


# Opening a track's preset list also selects that track in Live, so the
# computer screen shows the track you are picking a preset for. Set False to
# leave Live's selection alone until a preset is actually loaded.
SELECT_TRACK_ON_OPEN = True


# -----------------------------------------------------------------------------
# REPERTOIRE (the song list)
# -----------------------------------------------------------------------------

# The list in the middle of the screen is simply the locators in your
# Arrangement. Add, rename, move or delete locators in Live and the list
# follows - there is no separate song file to keep in sync.
REPERTOIRE_TITLE = "Repertoire"

# Playback stops automatically this many milliseconds BEFORE the next locator,
# not exactly on it. Without the lead, a backing track occasionally lets a very
# short piece of the following song through before the transport halts.
#
# 200 ms is a chosen value, not a measured one. Raise it if you still hear a
# fragment; lower it if songs feel clipped at the end.
STOP_LEAD_MS = 200


# -----------------------------------------------------------------------------
# FEEL
# -----------------------------------------------------------------------------

# How long a screen button must be held before the preset list opens. A short
# press arms or un-arms the track instead.
LONG_PRESS_SECONDS = 0.4

# Back/Forward: how long before a held button starts repeating, and how fast it
# repeats once it does. Only applies to the repertoire list - inside a preset
# list each press moves exactly one step.
NAV_REPEAT_DELAY = 0.4
NAV_REPEAT_INTERVAL = 0.12

# Inside a preset list, Back/Forward move the cursor and then apply the preset
# after this pause. Long enough to step past two or three entries without
# loading each one on the way.
NAV_SELECT_DELAY = 0.3


# -----------------------------------------------------------------------------
# COLOURS
# -----------------------------------------------------------------------------
# All colours are (red, green, blue), each 0-127. Note that is not 0-255:
# Live's own track colours are 0-255 per channel and get halved on the way to
# the keyboard.
#
# Do not set an LED fully dark on stage. A button you cannot find is worse than
# a button showing the wrong state, so every "off" state here is dim rather
# than black.

# Screen buttons take their track's own colour from Live. Set False to use the
# two fixed colours below instead.
TRACK_COLOUR_FOOTER = True
TRACK_COLOUR_DIM = 4          # how much darker an un-armed track's colour is

FOOTER_ARMED = (0x7F, 0x58, 0x00)     # amber
FOOTER_UNARMED = (0x7F, 0x7F, 0x7F)   # white

# The button whose preset list is on screen, armed and un-armed. Yellow is the
# only colour a screen button takes that does not come from its track, and that
# is the point: tracks in their own colours tell you nothing about which of
# them you are picking a preset for, so while a list is open its own button
# stops being an identity and becomes an answer.
#
# It stays yellow whether or not the track is armed - a short press arms it at
# any moment, and the button must not go quiet underneath the list it belongs
# to. Brightness still carries arm, so nothing is lost: the colour says whose
# list this is, the brightness says whether it is armed.
#
# Set both to the same value if you would rather not see arm at all while a
# list is open.
FOOTER_LIST_ARMED = (0x7F, 0x60, 0x00)     # yellow - this list is this track's
FOOTER_LIST_UNARMED = (0x26, 0x1C, 0x00)   # the same yellow, dim

# The pads while clip launch is switched off (SESSION_GRID below). Fully dark
# on purpose, the one exception to "nothing is ever dark" in this file: these
# pads do nothing, and a lit pad says "press me".
PAD_OFF = (0x00, 0x00, 0x00)

# Transport.
PLAY_READY = (0x00, 0x20, 0x00)       # dim green - stopped, cursor has a song
PLAY_RUNNING = (0x00, 0x7F, 0x00)     # green - playing
PLAY_NO_SONG = (0x7F, 0x7F, 0x7F)     # white - cursor line has no locator
PLAY_PRESET = (0x7F, 0x50, 0x00)      # amber - Play applies a preset instead
STOP_IDLE = (0x20, 0x20, 0x20)
STOP_RUNNING = (0x7F, 0x7F, 0x7F)

# Back/Forward. They turn yellow when they select presets rather than scroll,
# so the row changes colour together with Play.
NAV_IDLE = (0x20, 0x20, 0x20)
NAV_PRESSED = (0x7F, 0x7F, 0x7F)
NAV_SELECT_IDLE = (30, 25, 0)
NAV_SELECT_PRESSED = (127, 110, 0)

# Tap and Metro step between chapters while a preset list is open. With a
# list open and no chapters in your preset files they have nothing to do, and
# go almost dark. With no list open they are tap tempo and the metronome - see
# TAP_IDLE and the rest further down.
CHAPTER_OFF = (0x08, 0x08, 0x10)      # almost dark - a list is open, no chapters
CHAPTER_IDLE = (0x00, 0x30, 0x50)     # blue - a list is open, chapters exist
CHAPTER_PRESSED = (0x00, 0x60, 0x7F)  # bright blue - pressed

# When a list opens, Tap and Metro blink this many times and then hold steady.
# It is the only thing on the keyboard that says the chapter buttons are there,
# and it stops on its own because a light blinking all evening next to Play is
# noise - and reads as a warning. Touching either button stops it early.
#
# Set CHAPTER_PULSES = 0 for no blink at all. There is no blink in the
# keyboard's firmware, so this is done by the script on its poll loop.
CHAPTER_PULSES = 3
CHAPTER_PULSE_SECONDS = 0.5

# Tap and Metro's OWN roles - tap tempo and the metronome - which is what
# they do whenever no preset list is open. The chapter colours above only
# apply while a list is open; these are a separate pair so the two roles
# never have to share a meaning for the same colour.
TAP_IDLE = (0x10, 0x10, 0x18)
TAP_FLASH = (0x7F, 0x7F, 0x7F)      # lit for as long as Tap is held
METRO_ON = (0x00, 0x50, 0x7F)
METRO_OFF = (0x10, 0x10, 0x18)

# Cycle - rebuilds the preset list and the browser index. It is the only
# button in the transport row that is not transport, so it does not share the
# row's white: blue at rest tells you which one it is without reading the
# print. Amber is the one change of hue, because "working" has to catch the
# eye. Done is a brighter blue rather than green - green next to Play is
# ambiguous for exactly as long as it takes to glance down mid-song.
CYCLE_IDLE = (0x00, 0x10, 0x30)       # dim blue - at rest
CYCLE_BUSY = (0x7F, 0x60, 0x00)       # amber - rebuilding
CYCLE_DONE = (0x00, 0x40, 0x7F)       # bright blue - briefly, when ready
CYCLE_DONE_SECONDS = 1.0


# -----------------------------------------------------------------------------
# FADERS
# -----------------------------------------------------------------------------

# Each fader sets the volume of its own track: fader 1 track 1, and so on for
# as many tracks as the script has taken (MAX_TRACKS). Set False to leave the
# faders alone entirely - useful if you would rather MIDI-map them yourself.
#
# The faders are absolute: where a fader stands is what the track gets.
#
# With one exception, and it matters. The keyboard reports where every fader is
# standing the moment the script connects, and the faders have no motors - they
# are wherever they were last left, which has nothing to do with the set you
# just opened. That first report is therefore noted and not applied; without
# it, opening a set would overwrite the volumes you saved every single time.
# A fader takes its track the moment you actually move it.
#
# Moving one still jumps the track to where the fader is standing. That is what
# absolute means, and it is why the track's own value goes on the screen when
# you touch a fader - see FADER_SHOW_VALUE below.
#
# Be aware that Live can swallow a fader before it reaches this script if it
# happens to be MIDI-mapped in the set. It looks exactly like a dead fader.
FADERS_CONTROL_VOLUME = True

# Show the TRACK's volume on the keyboard's screen when you touch a fader and
# while you move it, instead of the keyboard's own readout of where the
# hardware is standing.
#
# Resting a finger on a fader shows the value and changes nothing, so you can
# see what a track is at - and what you are about to take over - before you
# move anything. Touch to look, move to take over.
#
# The readout only appears while your skin is on the fader. That is the
# keyboard's capacitive sensor, not this setting: nudge a fader with a
# fingernail, or through a sheet of paper, and nothing is drawn at all - while
# the value still moves and the sound still follows. Nothing here can change
# that.
#
# The number shown is the raw 0-127 fader position - not decibels and not a
# percentage. That is deliberate: one number the whole way, whether it comes
# from the fader, goes to the track, or is read off the screen. 108 is roughly
# 0 dB, so you can set a fader by hand and read the number straight off.
FADER_SHOW_VALUE = True

# The colour of that readout.
FADER_POPUP = (0x7F, 0x7F, 0x7F)

# Save (Capture MIDI), Quantize, Undo, Redo.
SAVE_READY = (0x00, 0x60, 0x7F)        # bright blue - something to capture
SAVE_IDLE = (0x08, 0x08, 0x10)         # dim - nothing played that can be caught
UNDO_READY = (0x7F, 0x7F, 0x7F)
UNDO_IDLE = (0x20, 0x20, 0x20)
REDO_READY = (0x7F, 0x7F, 0x7F)
REDO_IDLE = (0x20, 0x20, 0x20)
QUANTIZE_IDLE = (0x20, 0x20, 0x20)
QUANTIZE_PRESSED = (0x7F, 0x7F, 0x7F)


# -----------------------------------------------------------------------------
# SESSION GRID (clip launch)
# -----------------------------------------------------------------------------
# Switched OFF as it comes: the pads are dark and do nothing, and Record is
# plain Record. Set SESSION_GRID = True and pads 1-12 launch clips from a
# 4x3 window of Session View, whether or not a preset list is open on screen -
# see keylab_session.py.
#
# Why off: the window starts on the same tracks the screen buttons arm, and an
# empty slot on an armed track is record-ready. Pressing that pad starts a
# recording, and with it the transport - so on stage, one stray hit on a pad
# sets the Arrangement playing. Switch it on if you launch clips; leave it off
# if your songs live in the Arrangement and the pads are just in the way.
SESSION_GRID = False

# An empty clip slot. Dim rather than fully dark, same reasoning as the rest
# of this file: a pad you cannot see is worse than one lit for nothing.
SESSION_EMPTY = (0x04, 0x04, 0x04)

# A clip that is there but not playing shows its own colour from Live, this
# much darker. Dimmed so that "playing" is told apart by brightness and not
# only by hue - a green clip at full strength is the playing colour.
SESSION_STOPPED_DIM = 12

# A clip about to start or stop playing on the next quantization point.
SESSION_TRIGGERED_PLAY = (0x00, 0x40, 0x00)
SESSION_PLAYING = (0x00, 0x7F, 0x00)

# A clip about to start, or already, recording.
SESSION_TRIGGERED_RECORD = (0x40, 0x00, 0x00)
SESSION_RECORDING = (0x7F, 0x00, 0x00)

# An empty slot on an armed track - nothing to launch, but pressing it starts
# a recording.
SESSION_RECORD_READY = (0x30, 0x00, 0x00)

# Record with the grid OFF: Live's Arrangement Record. Dim red at rest, bright
# red while recording - the same pairing as Play's two greens.
REC_OFF = (0x20, 0x00, 0x00)
REC_ON = (0x7F, 0x00, 0x00)

# Record with the grid ON, held as a modifier: hold + press a pad deletes that
# slot's clip instead of launching it. Bright while held, so it is never ambiguous
# whether the next pad press launches or deletes. Amber, not red - red is
# already "recording"/"record-ready" on the pads themselves, and Record
# glowing red at rest would read as if something were armed or recording.
REC_IDLE = (0x10, 0x08, 0x00)
REC_SHIFT = (0x7F, 0x40, 0x00)
