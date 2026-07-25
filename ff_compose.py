#!/usr/bin/env python3
"""Parameterized orchestral composition -> per-section MIDI stems + a combined guide MIDI.
Same lyrical D-major piece I hand-wrote, but transposed/re-tempo'd per seed so runs differ."""
import mido, random, os

TPB = 480
BEATS_PER_BAR = 4

CHORDS = {
    'D':[62,66,69],'A':[64,69,73],'Bm':[62,66,71],'G':[62,67,71],
    'Em':[64,67,71],'A7':[64,67,69,73],'F#m':[61,66,69],'Gm':[62,67,70],
}
ROOT = {'D':50,'A':45,'Bm':47,'G':43,'Em':52,'A7':45,'F#m':54,'Gm':43}
PROG = ['D','A','Bm','G','D','G','A','D']
STORM = ['Bm','G','Em','A7','Bm','Gm','A7','A7']
THEME = [
    (69,1),(74,1),(78,2),(76,1),(78,1),(76,2),
    (74,1),(76,1),(78,1),(81,1),(79,2),(78,1),(76,1),
    (78,1),(76,1),(74,2),(71,1),(73,1),(74,2),
    (76,1),(78,1),(79,1),(76,1),(74,4),
]
TRACKS = {
    'vln':(1,48),'pad':(2,49),'cello':(3,42),'bass':(4,43),'horn':(5,60),
    'flute':(6,73),'oboe':(7,68),'harp':(8,46),'timp':(10,47),'piano':(11,0),
    'choir':(12,52),'solo':(13,40),
}
STRING_TRACKS = ['vln','pad','cello','bass','solo']
GROUPS = {'winds':['flute','oboe','horn'],'color':['harp','timp','choir','piano']}


def compose(outdir, seed):
    rnd = random.Random(seed)
    KEY = rnd.choice([-4,-2,0,0,2,3,5])       # transpose (semitones)
    BPM = rnd.choice([60,63,66,66,69,72])
    os.makedirs(outdir, exist_ok=True)
    notes = {k: [] for k in TRACKS}

    def add(track, start, dur, pitch, vel):
        p = int(pitch) + KEY
        if 0 <= p <= 127 and vel > 0:
            notes[track].append((start, dur, p, int(max(1, min(127, vel)))))

    def voice(chord, lo, hi):
        base = CHORDS[chord]; out = []
        for o in (-12,0,12,24):
            for p in base:
                if lo <= p+o <= hi: out.append(p+o)
        return sorted(set(out))

    def pad(sb,nb,chs,vel,trem=False):
        for b in range(nb):
            ch=chs[b%len(chs)]; s=(sb+b)*BEATS_PER_BAR; vs=voice(ch,55,79)
            if trem:
                t=0.0
                while t<BEATS_PER_BAR-1e-6:
                    for p in vs: add('pad',s+t,0.25,p,vel+(6 if (t%1)<0.25 else 0))
                    t+=0.25
            else:
                for p in vs: add('pad',s,BEATS_PER_BAR,p,vel)
    def choir(sb,nb,chs,vel):
        for b in range(nb):
            ch=chs[b%len(chs)]; s=(sb+b)*BEATS_PER_BAR
            for p in voice(ch,60,79): add('choir',s,BEATS_PER_BAR,p,vel)
    def bass(sb,nb,chs,vel,motion=False):
        for b in range(nb):
            ch=chs[b%len(chs)]; s=(sb+b)*BEATS_PER_BAR; r=ROOT[ch]
            if motion: add('bass',s,2,r,vel); add('bass',s+2,2,r+7,vel-4)
            else: add('bass',s,BEATS_PER_BAR,r,vel)
    def harp(sb,nb,chs,vel,density=8):
        for b in range(nb):
            ch=chs[b%len(chs)]; s=(sb+b)*BEATS_PER_BAR; tones=voice(ch,55,88)
            if not tones: continue
            step=BEATS_PER_BAR/density
            for i in range(density): add('harp',s+i*step,step*1.6,tones[i%len(tones)],vel-(i%2)*6)
    def timp(sb,nb,chs,vel,roll=False):
        for b in range(nb):
            ch=chs[b%len(chs)]; s=(sb+b)*BEATS_PER_BAR; r=ROOT[ch]-12
            if r<36: r+=12
            if roll:
                t=0.0
                while t<BEATS_PER_BAR-1e-6: add('timp',s+t,0.25,r,vel-10+int(20*(t/BEATS_PER_BAR))); t+=0.25
            else: add('timp',s,1.5,r,vel); add('timp',s+2,1.0,r,vel-12)
    def theme(track,sb,vel,octave=0,bars=8,dur_scale=1.0):
        t=sb*BEATS_PER_BAR; bu=0.0; pb=0
        for pitch,d in THEME:
            add(track,t,d*dur_scale,pitch+octave,vel+(5 if d>=2 else 0)); t+=d; bu+=d
            if bu>=BEATS_PER_BAR-1e-6:
                bu-=BEATS_PER_BAR; pb+=1
                if pb>=bars: break
    def counter(track,sb,nb,chs,vel):
        for b in range(nb):
            ch=chs[b%len(chs)]; s=(sb+b)*BEATS_PER_BAR; vs=voice(ch,52,64)
            if len(vs)>=2: add(track,s,2,vs[1],vel); add(track,s+2,2,vs[min(2,len(vs)-1)],vel-3)

    # descending 7-6 SUSPENSION CHAIN: the held resolution of each step becomes the 7th over the
    # next (lower) bass note, then resolves down by step again — a cascading dissonance/release.
    scale_off=[0,2,4,5,7,9,11]
    def dia(n):
        return 62 + 12*(n//7) + scale_off[n%7]
    def suspension_chain(sb, vel, full=False, start=0, steps=8):
        STEP=2
        for i in range(steps):
            s=sb*BEATS_PER_BAR + i*STEP
            bd=start-i
            bp=dia(bd)-12; inr=dia(bd+2); s1=dia(bd+6)+12; s2=dia(bd+5)+12
            add('bass',s,STEP,bp,vel)                 # descending bass
            add('pad',s,STEP,inr,vel-6)               # consonant inner third (violas)
            add('cello',s,STEP,dia(bd),vel-8)         # supporting voice
            add('vln',s,1.3,s1,vel+5)                 # the suspension: dissonant 7th...
            add('vln',s+1.3,STEP-1.3,s2,vel)          # ...resolving down a step to the 6th
            if full:
                add('horn',s,STEP,dia(bd)-12,vel-4)
                add('choir',s,STEP,inr,vel-10); add('choir',s,STEP,s2,vel-12)
                for j,p in enumerate([bp,inr,s2,s2+12]):
                    add('harp',s+j*(STEP/4),STEP/4*1.4,p,vel-8-(j%2)*4)
        se=sb*BEATS_PER_BAR+steps*STEP
        for p in [dia(start-steps)-12,dia(start-steps+2),dia(start-steps+4)+12]:
            add('pad',se,4,p,vel)
            if full: add('choir',se,4,p,vel-8)

    bar=0
    ic=['Bm','G','D','A','Bm','G','A','A']
    pad(bar,14,ic,42); harp(bar,14,ic,40,4); theme('flute',bar+2,54,0,4); theme('piano',bar+8,48,-12,4); bass(bar,14,ic,34); bar+=14
    pad(bar,16,PROG,54); harp(bar,16,PROG,50,8); bass(bar,16,PROG,48,True); theme('vln',bar,70,bars=8); theme('vln',bar+8,74,bars=8); counter('cello',bar+8,8,PROG,52); bar+=16
    # soft suspension chain — first, tender statement of the cascade (strings + harp)
    harp(bar,9,PROG,44,6); suspension_chain(bar,52,False,0); suspension_chain(bar+4,58,False,1); bar+=8
    dev=PROG+['Bm','F#m','G','A']+PROG
    pad(bar,24,dev,60); harp(bar,24,dev,56,8); bass(bar,24,dev,54,True); theme('oboe',bar,72,bars=8); theme('flute',bar+8,74,12,8); theme('vln',bar+16,80,bars=8); counter('cello',bar,24,dev,56); theme('horn',bar+16,64,-12,8); bar+=24
    p3=PROG*3
    pad(bar,24,p3,78); choir(bar,24,p3,54); harp(bar,24,p3,70,8); bass(bar,24,p3,76,True); timp(bar,24,p3,78)
    for k in range(3): theme('vln',bar+k*8,92,bars=8); theme('horn',bar+k*8,78,-12,8); theme('flute',bar+k*8,80,12,8)
    counter('cello',bar,24,p3,70); bar+=24
    # GRAND suspension chain — the cascade returns at full force as the emotional peak
    timp(bar,9,PROG,60); suspension_chain(bar,86,True,0); suspension_chain(bar+4,90,True,0); bar+=8
    pad(bar,16,STORM,84,True); bass(bar,16,STORM,88,True); timp(bar,16,STORM,88,True)
    for i,p in enumerate([66,69,71,74,76,79,81,83]): add('horn',(bar+i)*BEATS_PER_BAR,4,p,86); add('oboe',(bar+i)*BEATS_PER_BAR,4,p+12,74)
    choir(bar,16,STORM,66); bar+=16
    calm=PROG
    pad(bar,24,calm*3,52); choir(bar,24,calm*3,58); harp(bar,24,calm*3,54,6); bass(bar,24,calm*3,44); theme('solo',bar,78,bars=8); theme('solo',bar+8,80,bars=8); theme('flute',bar+16,66,12,8); theme('solo',bar+16,82,bars=8); bar+=24
    hp=PROG*4
    pad(bar,32,hp,74); choir(bar,32,hp,50); harp(bar,32,hp,66,8); bass(bar,32,hp,72,True); timp(bar,32,hp,64)
    for k in range(4): theme('vln',bar+k*8,86,bars=8); theme('cello',bar+k*8,68,-12,8)
    theme('horn',bar+16,74,bars=16); bar+=32
    cc=['D','G','A','D','Bm','G','A','D','G','D','A','D','D','D','D','D']
    pad(bar,16,cc,46); harp(bar,16,cc,44,4); bass(bar,16,cc,40); theme('solo',bar,64,bars=8,dur_scale=1.15); theme('piano',bar+8,52,-12,6,dur_scale=1.3)
    for p in [50,62,66,69,74]: add('pad',(bar+14)*BEATS_PER_BAR,12,p,44); add('choir',(bar+14)*BEATS_PER_BAR,12,p,40)
    add('harp',(bar+14)*BEATS_PER_BAR,8,38,46); bar+=16

    tempo = mido.bpm2tempo(BPM)
    def write_stem(fname, tns):
        mid=mido.MidiFile(ticks_per_beat=TPB); m=mido.MidiTrack(); m.append(mido.MetaMessage('set_tempo',tempo=tempo,time=0)); mid.tracks.append(m)
        for name in tns:
            chn,prog=TRACKS[name]; tr=mido.MidiTrack(); mid.tracks.append(tr); tr.append(mido.Message('program_change',channel=chn,program=prog,time=0))
            evs=[]
            for (start,dur,pitch,vel) in notes[name]:
                st=int(round(start*TPB)); en=int(round((start+dur)*TPB)); evs.append((st,1,pitch,vel,chn)); evs.append((en,0,pitch,0,chn))
            evs.sort(key=lambda e:(e[0],e[1])); tp=0
            for (t,on,pitch,vel,chn) in evs:
                dt=t-tp; tp=t; tr.append(mido.Message('note_on' if on else 'note_off',channel=chn,note=pitch,velocity=vel,time=dt))
        mid.save(fname)
    for g,tns in GROUPS.items(): write_stem(f'{outdir}/stem_{g}.mid', tns)
    for t in STRING_TRACKS: write_stem(f'{outdir}/stem_{t}.mid', [t])
    write_stem(f'{outdir}/guide.mid', list(TRACKS.keys()))
    return {'key_shift': KEY, 'bpm': BPM, 'bars': bar}


if __name__ == '__main__':
    import sys, json
    print(json.dumps(compose(sys.argv[1], int(sys.argv[2]))))
