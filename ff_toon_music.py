#!/usr/bin/env python3
"""Spec 02 score: original ragtime / stride piano, FIXED tempo, whole bars only.

Music comes first here. The animation is cut to this, exactly the way the Silly
Symphonies were made: compose, mark the bars, then time the picture to them. So the
one thing this module must guarantee is a rigid grid — 120 bpm, 4/4, an integer
number of bars — because ff_toon cuts on the downbeat and cannot tolerate drift.

Every pitch is written from scratch. These get published; Content ID doesn't care
about intent.
"""
import os, random, mido

TPB = 480
BPM = 120
BEATS_PER_BAR = 4
BAR_SECONDS = BEATS_PER_BAR * 60 / BPM      # 2.0 s

# G major-ish ragtime harmony. Roman numerals in a key that sits well under the
# stride left hand: G, C, D7, E7, A7.
CHORDS = {
    'G':  [55, 59, 62], 'C':  [48, 52, 55], 'D7': [50, 54, 57, 60],
    'E7': [52, 56, 59, 62], 'A7': [45, 49, 52, 55], 'Em': [52, 55, 59],
    'Cm': [48, 51, 55],
}
BASS = {'G': 43, 'C': 36, 'D7': 38, 'E7': 40, 'A7': 33, 'Em': 40, 'Cm': 36}

# Four strains. Ragtime form is sectional (AABBACC); the arc from the spec —
# starts playing, world wakes up, it runs away, it collapses — maps onto them.
STRAIN_A = ['G', 'G', 'C', 'G', 'D7', 'D7', 'G', 'G']          # the tune begins
STRAIN_B = ['C', 'C', 'G', 'G', 'A7', 'A7', 'D7', 'D7']        # the world joins in
STRAIN_C = ['E7', 'E7', 'A7', 'A7', 'D7', 'D7', 'G', 'G']      # it gets away from him
STRAIN_D = ['Cm', 'Cm', 'G', 'D7', 'G', 'Cm', 'D7', 'G']       # the collapse and last chord

# Syncopated right-hand figure, in beats within a bar: (offset, scale-degree, dur).
# The tied-over-the-beat 1.5 is what makes it ragtime rather than a march.
RAG_FIGURE = [
    (0.0, 0, 0.5), (0.5, 2, 0.5), (1.0, 4, 0.5), (1.5, 2, 1.0),
    (2.5, 4, 0.5), (3.0, 1, 0.5), (3.5, 0, 0.5),
]
RAG_FIGURE_B = [
    (0.0, 4, 0.75), (0.75, 2, 0.25), (1.0, 0, 0.5), (1.5, 2, 1.0),
    (2.5, 0, 0.5), (3.0, 4, 0.5), (3.5, 2, 0.5),
]


def _voice(chord, degree, octave=1):
    """Pick a chord tone `degree` steps up, transposed into the melody register."""
    tones = CHORDS[chord]
    p = tones[degree % len(tones)] + 12 * (degree // len(tones))
    return p + 12 * octave


def compose_toon(outdir, seed, n_bars):
    """Write one piano MIDI of exactly `n_bars` bars at BPM. Returns (path, meta)."""
    rnd = random.Random(seed)
    os.makedirs(outdir, exist_ok=True)
    notes = []          # (start_beat, dur_beats, pitch, velocity)

    def add(start, dur, pitch, vel):
        if 0 <= pitch <= 127:
            notes.append((start, dur, int(pitch), int(max(1, min(127, vel)))))

    # Build a bar list of exactly n_bars by cycling the strains in ragtime order.
    order = STRAIN_A + STRAIN_A + STRAIN_B + STRAIN_B + STRAIN_A + STRAIN_C + STRAIN_C + STRAIN_D
    bars = [order[i % len(order)] for i in range(n_bars)]

    for b, chord in enumerate(bars):
        t = b * BEATS_PER_BAR
        # Where we are in the piece drives the dynamic arc: quiet start, big middle,
        # a hard final chord.
        frac = b / max(1, n_bars - 1)
        vel = int(62 + 34 * min(1.0, frac * 1.35)) if frac < 0.85 else 104

        # --- left hand: stride. Bass note on 1 and 3, chord stab on 2 and 4. ---
        root = BASS[chord]
        add(t + 0.0, 0.9, root, vel)
        add(t + 2.0, 0.9, root + 7, vel - 4)
        for beat in (1.0, 3.0):
            for p in CHORDS[chord]:
                add(t + beat, 0.6, p + 12, vel - 18)

        # --- right hand: the syncopated figure, alternating shape per phrase ---
        fig = RAG_FIGURE if (b // 2) % 2 == 0 else RAG_FIGURE_B
        for (off, deg, dur) in fig:
            # a little melodic variety without leaving the chord
            d = deg + (1 if rnd.random() < 0.18 else 0)
            add(t + off, dur * 0.95, _voice(chord, d, octave=1), vel + 6)

        # --- the last bar lands on one flat chord and stops: the collapse ---
        if b == n_bars - 1:
            notes[:] = [n for n in notes if n[0] < t]
            for p in CHORDS[chord]:
                add(t, BEATS_PER_BAR, p, 110)
                add(t, BEATS_PER_BAR, p + 12, 104)
            add(t, BEATS_PER_BAR, BASS[chord] - 12, 112)

    mid = mido.MidiFile(ticks_per_beat=TPB)
    tr = mido.MidiTrack(); mid.tracks.append(tr)
    tr.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(BPM), time=0))
    tr.append(mido.Message('program_change', channel=0, program=0, time=0))   # piano
    evs = []
    for (start, dur, pitch, vel) in notes:
        evs.append((int(round(start * TPB)), 1, pitch, vel))
        evs.append((int(round((start + dur) * TPB)), 0, pitch, 0))
    evs.sort(key=lambda e: (e[0], e[1]))
    prev = 0
    for (t, on, pitch, vel) in evs:
        tr.append(mido.Message('note_on' if on else 'note_off', channel=0,
                               note=pitch, velocity=vel, time=t - prev))
        prev = t
    path = f"{outdir}/toon.mid"
    mid.save(path)
    meta = {'bpm': BPM, 'bars': n_bars, 'seconds': n_bars * BAR_SECONDS,
            'key': 'G major', 'idiom': 'ragtime / stride piano'}
    return path, meta


def render_toon_music(outdir, midi_path, dest_wav, FS, SF, SOX, SFLIB):
    """Piano through the existing sampler chain, mastered like a 1930s optical track:
    band-limited, a little compressed, deliberately not hi-fi."""
    import subprocess

    def sh(cmd):
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, env=dict(os.environ, **SFLIB))

    raw = f"{outdir}/toon_raw.wav"
    sh([FS, "-ni", "-R", "0", "-C", "0", "-g", "1.1", "-r", "44100", "-F", raw, SF, midi_path])
    # Optical sound on 1930s prints rolled off hard at both ends and had a narrow
    # dynamic range. Faking that is another limitation-as-style: it hides sampler
    # thinness and it is what the era actually sounded like.
    sh([SOX, raw, dest_wav,
        "highpass", "120", "lowpass", "6500",
        "equalizer", "1200", "1.4q", "+2.5",
        "reverb", "22", "40", "60", "100", "12", "0",
        "compand", "0.05,0.25", "6:-30,-18,-8", "0", "-90", "0.05",
        "gain", "-n", "-2.0"])
    return dest_wav
