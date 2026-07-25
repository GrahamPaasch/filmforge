#!/usr/bin/env python3
"""Spec 01 pastoral score: original F major / 2-4 sunrise piece, parameterized by
target seconds rather than a fixed bar count.

Idiom is Beethoven 6/i crossed with Grieg's Morning Mood: small motifs repeated as
ostinato over a pedal drone, slow harmonic rhythm, woodwind statements answered by
strings, one single sunrise bloom and no storm section.

Every pitch here is written from scratch. Nothing quotes either model work -- these
films get published and Content ID does not care about intent.
"""
import os, math, random, mido

from ff_compose import TPB, TRACKS, GROUPS, STRING_TRACKS, write_stem

BEATS_PER_BAR = 2                      # 2/4

# F major. Slow harmonic rhythm: one chord per two bars.
CHORDS = {
    'F':  [65, 69, 72], 'Bb': [65, 70, 74], 'C':  [64, 67, 72],
    'Dm': [65, 69, 74], 'Gm': [62, 67, 70], 'Am': [64, 69, 72],
    'C7': [64, 67, 70, 72],
}
ROOT = {'F': 41, 'Bb': 46, 'C': 36, 'Dm': 38, 'Gm': 43, 'Am': 45, 'C7': 36}

# Eight chords = sixteen bars. It turns and returns; it never goes anywhere dark.
PROG = ['F', 'F', 'Bb', 'F', 'C', 'F', 'Bb', 'C']
# Slightly warmer turn for the bloom, still no minor drama.
PROG_BLOOM = ['F', 'Bb', 'F', 'Dm', 'Bb', 'C', 'F', 'C']

# The motif: eight bars of 2/4, an arch that rises to F and settles back on C.
# (pitch, duration in beats)
MOTIF = [
    (72, 1), (74, 1), (77, 2), (74, 1), (72, 1), (69, 2),
    (72, 1), (69, 1), (65, 2), (67, 1), (69, 1), (72, 2),
]
MOTIF_BARS = sum(d for _, d in MOTIF) // BEATS_PER_BAR      # 8

# Six sections, fractions of the total. One bloom, then it settles: the shape of
# the film itself.
SECTIONS = [
    ('drone',   0.16),   # solo woodwind over a pedal
    ('answer',  0.14),   # oboe answers the flute, ostinato firms up
    ('strings', 0.15),   # strings enter under the winds
    ('build',   0.16),   # horn and moving bass, the light coming up
    ('bloom',   0.17),   # full tutti sunrise
    ('settle',  0.22),   # everything recedes back to the drone
]
# A section shorter than one motif statement would carry no motif at all, so a
# short cut (the 60s POC) drops whole middle sections instead of shrinking them.
# The arc that must survive: start on the drone, bloom once, settle back.
DROP_ORDER = ['answer', 'strings', 'build']


def compose_pastoral(outdir, seed, target_seconds):
    """Write MIDI stems for a piece of roughly target_seconds. Stem filenames match
    what make_film.render_orchestral expects, so the existing sampler chain plays it."""
    rnd = random.Random(seed)
    BPM = rnd.choice([60, 63, 66, 66, 69, 72])
    os.makedirs(outdir, exist_ok=True)
    notes = {k: [] for k in TRACKS}

    sec_per_bar = BEATS_PER_BAR * 60.0 / BPM
    # A few bars of overrun so the final chord is never clipped; mux uses -shortest.
    total_bars = max(MOTIF_BARS * 4, int(math.ceil(target_seconds / sec_per_bar)) + 4)

    def add(track, start, dur, pitch, vel):
        p = int(pitch)
        if 0 <= p <= 127 and vel > 0:
            notes[track].append((start, dur, p, int(max(1, min(127, vel)))))

    def voice(chord, lo, hi):
        out = []
        for o in (-12, 0, 12, 24):
            for p in CHORDS[chord]:
                if lo <= p + o <= hi:
                    out.append(p + o)
        return sorted(set(out))

    def chord_at(bar, prog):
        return prog[(bar // 2) % len(prog)]

    # --- the pedal: F underneath nearly everything, re-struck so sustains don't die
    def drone(sb, nb, vel, low=True):
        b = 0
        while b < nb:
            span = min(8, nb - b)
            s = (sb + b) * BEATS_PER_BAR
            add('bass', s, span * BEATS_PER_BAR, 41, vel)
            if low:
                add('bass', s, span * BEATS_PER_BAR, 29, vel - 6)
            b += span

    # --- ostinato: the small repeated figure, Beethoven's trick for standing still
    def ostinato(track, sb, nb, prog, vel, per_bar=4):
        step = BEATS_PER_BAR / per_bar
        for b in range(nb):
            tones = voice(chord_at(sb + b, prog), 60, 84)
            if not tones:
                continue
            s = (sb + b) * BEATS_PER_BAR
            for i in range(per_bar):
                add(track, s + i * step, step * 1.5, tones[i % len(tones)], vel - (i % 2) * 5)

    def pad(sb, nb, prog, vel, lo=55, hi=79):
        for b in range(nb):
            s = (sb + b) * BEATS_PER_BAR
            for p in voice(chord_at(sb + b, prog), lo, hi):
                add('pad', s, BEATS_PER_BAR, p, vel)

    def choir(sb, nb, prog, vel):
        for b in range(nb):
            s = (sb + b) * BEATS_PER_BAR
            for p in voice(chord_at(sb + b, prog), 60, 79):
                add('choir', s, BEATS_PER_BAR, p, vel)

    def walking_bass(sb, nb, prog, vel):
        """Only where the music actually moves; elsewhere the drone holds."""
        for b in range(nb):
            ch = chord_at(sb + b, prog)
            s = (sb + b) * BEATS_PER_BAR
            add('bass', s, 1, ROOT[ch], vel)
            add('bass', s + 1, 1, ROOT[ch] + 7, vel - 5)

    def motif(track, sb, vel, octave=0, dur_scale=1.0):
        t = sb * BEATS_PER_BAR
        for pitch, d in MOTIF:
            add(track, t, d * dur_scale, pitch + octave, vel + (5 if d >= 2 else 0))
            t += d

    def counter(track, sb, nb, prog, vel):
        """Strings answering underneath: thirds moving at half the motif's speed."""
        for b in range(nb):
            vs = voice(chord_at(sb + b, prog), 50, 64)
            if len(vs) >= 2:
                s = (sb + b) * BEATS_PER_BAR
                add(track, s, BEATS_PER_BAR, vs[1 if b % 2 == 0 else min(2, len(vs) - 1)], vel)

    def timp(sb, nb, prog, vel):
        for b in range(0, nb, 4):
            ch = chord_at(sb + b, prog)
            r = ROOT[ch] - 12
            if r < 36:
                r += 12
            add('timp', (sb + b) * BEATS_PER_BAR, 1.5, r, vel)

    def statements(sb, nb, fn):
        """Lay motif statements on the 8-bar grid inside a section."""
        for k in range(nb // MOTIF_BARS):
            fn(sb + k * MOTIF_BARS, k)

    # ------------------------------------------------------------------ layout
    # Every kept section must hold at least one whole motif statement.
    kept = [name for name, _ in SECTIONS]
    for name in DROP_ORDER:
        if total_bars >= len(kept) * MOTIF_BARS:
            break
        kept.remove(name)
    plan = [(name, frac) for name, frac in SECTIONS if name in kept]
    scale = sum(frac for _, frac in plan)
    lengths, acc = {}, 0
    for n, (name, frac) in enumerate(plan):
        nb = total_bars - acc if n == len(plan) - 1 else int(round(total_bars * frac / scale))
        # Round to whole motif statements so a section never ends mid-phrase.
        nb = max(MOTIF_BARS, (nb // MOTIF_BARS) * MOTIF_BARS)
        lengths[name] = nb
        acc += nb
    total_bars = sum(lengths.values())

    bar = 0
    # I. a drone and one voice. Nothing has happened yet.
    if 'drone' in lengths:
        nb = lengths['drone']
        drone(bar, nb, 26)
        pad(bar, nb, ['F'] * 8, 20, 60, 72)
        statements(bar, nb, lambda sb, k: motif('flute', sb, 40 + 4 * k, dur_scale=1.1))
        ostinato('harp', bar + MOTIF_BARS, max(0, nb - MOTIF_BARS), ['F'] * 8, 26, 2)
        bar += nb

    # II. the oboe answers the flute. Still only winds over the pedal.
    if 'answer' in lengths:
        nb = lengths['answer']
        drone(bar, nb, 32)
        pad(bar, nb, PROG, 28)
        ostinato('harp', bar, nb, PROG, 34, 4)
        statements(bar, nb, lambda sb, k: (motif('flute', sb, 48) if k % 2 == 0
                                           else motif('oboe', sb, 50, -12)))
        bar += nb

    # III. strings underneath. The first real warmth.
    if 'strings' in lengths:
        nb = lengths['strings']
        drone(bar, nb, 40)
        pad(bar, nb, PROG, 42)
        ostinato('harp', bar, nb, PROG, 44, 4)
        counter('cello', bar, nb, PROG, 40)
        statements(bar, nb, lambda sb, k: (motif('vln', sb, 58 + 4 * k) if k % 2 == 0
                                           else motif('oboe', sb, 56)))
        bar += nb

    # IV. the light comes up: horn, moving bass, denser ostinato.
    if 'build' in lengths:
        nb = lengths['build']
        walking_bass(bar, nb, PROG, 62)
        pad(bar, nb, PROG, 64)
        ostinato('harp', bar, nb, PROG, 60, 4)
        ostinato('piano', bar, nb, PROG, 44, 2)
        counter('cello', bar, nb, PROG, 60)
        statements(bar, nb, lambda sb, k: (motif('vln', sb, 74 + 5 * k),
                                           motif('horn', sb, 64, -12),
                                           motif('flute', sb, 68, 12) if k % 2 else None))
        bar += nb

    # V. the single sunrise bloom. One climax, no storm.
    nb = lengths['bloom']
    walking_bass(bar, nb, PROG_BLOOM, 92)
    pad(bar, nb, PROG_BLOOM, 96)
    choir(bar, nb, PROG_BLOOM, 70)
    ostinato('harp', bar, nb, PROG_BLOOM, 84, 4)
    timp(bar, nb, PROG_BLOOM, 84)
    counter('cello', bar, nb, PROG_BLOOM, 86)
    statements(bar, nb, lambda sb, k: (motif('vln', sb, 112),
                                       motif('horn', sb, 96, -12),
                                       motif('flute', sb, 98, 12),
                                       motif('oboe', sb, 92)))
    bar += nb

    # VI. settle. The drone comes back and takes everything with it.
    nb = lengths['settle']
    drone(bar, nb, 42)
    ostinato('harp', bar, nb, PROG, 44, 2)
    tail = MOTIF_BARS * 2
    body = max(MOTIF_BARS, nb - tail)
    # the pad holds all the way to the end -- without it the last bars go hollow
    pad(bar, nb, PROG, 44)
    counter('cello', bar, body, PROG, 40)
    statements(bar, body, lambda sb, k: (motif('solo', sb, 60 - 5 * k, dur_scale=1.15),
                                         motif('flute', sb, 46, 12) if k == 0 else None))
    # last breath: one long F, everything holding, then done
    fin = (bar + nb - 4) * BEATS_PER_BAR
    for p in (41, 65, 69, 72, 77):
        add('pad', fin, 8, p, 38)
        add('choir', fin, 8, p, 30)
    add('bass', fin, 8, 41, 36)
    add('solo', fin, 8, 77, 44)
    add('harp', fin, 6, 65, 40)
    bar += nb

    tempo = mido.bpm2tempo(BPM)
    for g, tns in GROUPS.items():
        write_stem(f'{outdir}/stem_{g}.mid', tns, notes, tempo)
    for t in STRING_TRACKS:
        write_stem(f'{outdir}/stem_{t}.mid', [t], notes, tempo)
    write_stem(f'{outdir}/guide.mid', list(TRACKS.keys()), notes, tempo)
    return {'key': 'F major', 'meter': '2/4', 'bpm': BPM, 'bars': bar,
            'sections': kept, 'seconds': round(bar * sec_per_bar, 1),
            'target': round(target_seconds, 1)}


if __name__ == '__main__':
    import sys, json
    print(json.dumps(compose_pastoral(sys.argv[1], int(sys.argv[2]), float(sys.argv[3]))))
