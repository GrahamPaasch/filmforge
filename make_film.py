#!/usr/bin/env python3
"""Film forge: churn out a fresh video in a genre.
  usage:  make_film.py <nature|horror|pastoral> [seed] [num_scenes] [--poc] [--no-music]
Run with the ComfyUI venv python (has torch/transformers/mido)."""
import sys, os, time, json, random, subprocess, urllib.request, urllib.parse
import numpy as np, scipy.io.wavfile as wav

ROOT = "/home/gpaasch/filmforge"
ENV = "/home/gpaasch/synthenv"
FS = f"{ENV}/bin/fluidsynth"; SOX = f"{ENV}/bin/sox"
SFIZZ = f"{ROOT}/bin/sfizz_render"; SFLIB = {"LD_LIBRARY_PATH": f"{ENV}/lib"}
SF = f"{ROOT}/assets/MuseScore_General.sf2"
PERF = f"{ROOT}/assets/sso/Sonatina Symphonic Orchestra/Strings - Performance"
COMFY = "http://127.0.0.1:8188"; CKPT = "RealVisXL_V5.0_fp16.safetensors"
SERVE_DIR = "/tmp/movie-share"; SERVE_URL = "http://192.168.5.21:8009"

sys.path.insert(0, ROOT)
import ff_compose, ff_pools

def sh(cmd, env=None):
    e = dict(os.environ, **(env or {}))
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=e)

# ---------- images via ComfyUI ----------
def gen_images(cfg, seed, n, outdir):
    os.makedirs(outdir, exist_ok=True)
    rnd = random.Random(seed)
    scenes = rnd.sample(cfg['pool'], min(n, len(cfg['pool'])))
    def post(p, d):
        r = urllib.request.Request(COMFY+p, data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
        return json.loads(urllib.request.urlopen(r, timeout=30).read())
    def get(p): return json.loads(urllib.request.urlopen(COMFY+p, timeout=30).read())
    for i, scene in enumerate(scenes):
        wf = {
            "4":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":CKPT}},
            "5":{"class_type":"EmptyLatentImage","inputs":{"width":1344,"height":768,"batch_size":1}},
            "6":{"class_type":"CLIPTextEncode","inputs":{"text":scene+cfg['style'],"clip":["4",1]}},
            "7":{"class_type":"CLIPTextEncode","inputs":{"text":cfg['neg'],"clip":["4",1]}},
            "3":{"class_type":"KSampler","inputs":{"seed":seed*100+i,"steps":28,"cfg":cfg['cfg'],
                 "sampler_name":"dpmpp_2m","scheduler":"karras","denoise":1.0,
                 "model":["4",0],"positive":["6",0],"negative":["7",0],"latent_image":["5",0]}},
            "8":{"class_type":"VAEDecode","inputs":{"samples":["3",0],"vae":["4",2]}},
            "9":{"class_type":"SaveImage","inputs":{"filename_prefix":"ff","images":["8",0]}},
        }
        pid = post("/prompt", {"prompt": wf})["prompt_id"]; src=None
        for _ in range(200):
            time.sleep(1.5); h = get(f"/history/{pid}")
            if pid in h:
                for node in h[pid]["outputs"].values():
                    for img in node.get("images", []): src=img
                break
        if not src: print(f"img {i} FAILED", flush=True); continue
        q=f"/view?filename={urllib.parse.quote(src['filename'])}&subfolder={src.get('subfolder','')}&type={src.get('type','output')}"
        open(f"{outdir}/frame{i:02d}.png","wb").write(urllib.request.urlopen(COMFY+q, timeout=30).read())
        print(f"img {i:02d}/{len(scenes)}", flush=True)
    return len(scenes)

# ---------- orchestral music (fluidsynth + Sonatina strings + sox) ----------
def render_orchestral(d):
    for g in ("winds","color"):
        sh([FS,"-ni","-R","0","-C","0","-g","1.0","-r","44100","-F",f"{d}/raw_{g}.wav",SF,f"{d}/stem_{g}.mid"])
    patch = {"vln":"1st Violins Sustain.sfz","pad":"Violas Sustain.sfz","cello":"Celli Sustain.sfz",
             "bass":"Basses Sustain.sfz","solo":"Violin Solo 1 Sustain.sfz"}
    for t,p in patch.items():
        sh([SFIZZ,"--sfz",f"{PERF}/{p}","--midi",f"{d}/stem_{t}.mid","--wav",f"{d}/sfz_{t}.wav","-s","44100","-p","256"], env=SFLIB)
    gains={"vln":"-3","pad":"-6","cello":"-5","bass":"-7","solo":"-4"}
    for t,g in gains.items(): sh([SOX,f"{d}/sfz_{t}.wav",f"{d}/b_{t}.wav","gain",g], env=SFLIB)
    sh([SOX,"-m",f"{d}/b_vln.wav",f"{d}/b_pad.wav",f"{d}/b_cello.wav",f"{d}/b_bass.wav",f"{d}/b_solo.wav",f"{d}/strings.wav","gain","-2"], env=SFLIB)
    sh([SOX,f"{d}/raw_winds.wav",f"{d}/sh_winds.wav","gain","-9","lowpass","5200","treble","-4"], env=SFLIB)
    sh([SOX,f"{d}/raw_color.wav",f"{d}/sh_color.wav","bass","+1","gain","-4"], env=SFLIB)
    sh([SOX,"-m",f"{d}/strings.wav",f"{d}/sh_winds.wav",f"{d}/sh_color.wav",f"{d}/mix.wav"], env=SFLIB)
    sh([SOX,f"{d}/mix.wav",f"{d}/music.wav","gain","-3","equalizer","250","1.2q","+2",
        "equalizer","3500","2.0q","-2.5","equalizer","9000","1.0q","-2",
        "reverb","74","42","100","100","24","0","compand","0.3,0.9","6:-70,-60,-18","-3","-90","0.2","gain","-n","-1.5"], env=SFLIB)

# ---------- pastoral music: same sampler chain, gentler master ----------
def render_pastoral(d):
    """The orchestral master is tuned for the D-major piece and its compander lifts
    quiet material ~10dB, which flattens a sunrise arc to about 4dB of swing. The
    whole point of this score is one bloom, so pastoral keeps the dynamics."""
    for g in ("winds","color"):
        sh([FS,"-ni","-R","0","-C","0","-g","1.0","-r","44100","-F",f"{d}/raw_{g}.wav",SF,f"{d}/stem_{g}.mid"])
    patch = {"vln":"1st Violins Sustain.sfz","pad":"Violas Sustain.sfz","cello":"Celli Sustain.sfz",
             "bass":"Basses Sustain.sfz","solo":"Violin Solo 1 Sustain.sfz"}
    for t,p in patch.items():
        sh([SFIZZ,"--sfz",f"{PERF}/{p}","--midi",f"{d}/stem_{t}.mid","--wav",f"{d}/sfz_{t}.wav","-s","44100","-p","256"], env=SFLIB)
    gains={"vln":"-4","pad":"-6","cello":"-6","bass":"-6","solo":"-5"}
    for t,g in gains.items(): sh([SOX,f"{d}/sfz_{t}.wav",f"{d}/b_{t}.wav","gain",g], env=SFLIB)
    sh([SOX,"-m",f"{d}/b_vln.wav",f"{d}/b_pad.wav",f"{d}/b_cello.wav",f"{d}/b_bass.wav",f"{d}/b_solo.wav",f"{d}/strings.wav","gain","-2"], env=SFLIB)
    # winds lead this piece, so they sit forward of where the orchestral chain puts them
    sh([SOX,f"{d}/raw_winds.wav",f"{d}/sh_winds.wav","gain","-6","lowpass","6000","treble","-2"], env=SFLIB)
    sh([SOX,f"{d}/raw_color.wav",f"{d}/sh_color.wav","bass","+1","gain","-6"], env=SFLIB)
    sh([SOX,"-m",f"{d}/strings.wav",f"{d}/sh_winds.wav",f"{d}/sh_color.wav",f"{d}/mix.wav"], env=SFLIB)
    # open-air reverb, a warm tilt, and peak-only limiting -- no upward compression
    sh([SOX,f"{d}/mix.wav",f"{d}/music.wav","gain","-3","equalizer","220","1.0q","+2",
        "equalizer","3200","2.0q","-2","equalizer","10000","1.0q","-1.5",
        "reverb","62","48","96","100","20","0",
        "compand","0.1,0.6","6:-24,-18,-6","0","-90","0.1","gain","-n","-2.5"], env=SFLIB)


# ---------- horror music (compose guide -> MusicGen melody conditioning) ----------
def render_horror(d, seed):
    import torch, torchaudio
    from transformers import MusicgenMelodyForConditionalGeneration, AutoProcessor
    sh([FS,"-ni","-R","0","-C","0","-g","1.0","-r","44100","-F",f"{d}/guide.wav",SF,f"{d}/guide.mid"])
    name="facebook/musicgen-melody-large"
    proc=AutoProcessor.from_pretrained(name)
    model=MusicgenMelodyForConditionalGeneration.from_pretrained(name, torch_dtype=torch.float16).to("cuda")
    out_sr=model.config.audio_encoder.sampling_rate; fe_sr=proc.feature_extractor.sampling_rate
    sr,a=wav.read(f"{d}/guide.wav"); a=a.astype(np.float32)
    if a.ndim>1: a=a.mean(axis=1)
    a/=(np.max(np.abs(a))+1e-8)
    if sr!=fe_sr:
        a=torchaudio.functional.resample(torch.from_numpy(a).unsqueeze(0),sr,fe_sr).squeeze(0).numpy(); sr=fe_sr
    a=np.ascontiguousarray(a,dtype=np.float32); dur=len(a)/sr
    prompt=("dark atonal alien horror film score, dissonant strings, groaning drones, "
            "unsettling dread, terrifying, cinematic, sparse, no drums")
    os.makedirs(f"{d}/seg",exist_ok=True); N=24; win=30.0; step=(dur-win)/(N-1)
    for i in range(N):
        s0=int(i*step*sr); seg=a[s0:s0+int(win*sr)]
        if len(seg)<int(2*sr): seg=a[-int(win*sr):]
        inp=proc(text=[prompt],audio=seg,sampling_rate=sr,padding=True,return_tensors="pt")
        inp={k:(v.to("cuda").half() if v.dtype==torch.float32 else v.to("cuda")) for k,v in inp.items()}
        torch.manual_seed(seed*7+i)
        with torch.no_grad():
            aud=model.generate(**inp,max_new_tokens=1500,do_sample=True,guidance_scale=3.0)
        out=aud[0].float().cpu().numpy()
        if out.ndim>1: out=out[0]
        out/=(np.max(np.abs(out))+1e-8)
        wav.write(f"{d}/seg/seg{i:02d}.wav",out_sr,(out*32767*0.95).astype(np.int16))
        print(f"music {i:02d}/{N}",flush=True)
    del model; torch.cuda.empty_cache()
    import glob
    segs=sorted(glob.glob(f"{d}/seg/seg*.wav")); ins=[]
    for s in segs: ins+=["-i",s]
    fc=[]; prev="[0:a]"
    for i in range(1,len(segs)):
        o=f"[a{i}]" if i<len(segs)-1 else "[mix]"; fc.append(f"{prev}[{i}:a]acrossfade=d=3:c1=tri:c2=tri{o}"); prev=o
    sh(["ffmpeg","-y",*ins,"-filter_complex",";".join(fc),"-map","[mix]","-c:a","pcm_s16le",f"{d}/joined.wav"])
    sh([SOX,f"{d}/joined.wav",f"{d}/music.wav","gain","-3","equalizer","220","1.0q","+1.5",
        "equalizer","8000","1.0q","-1.5","reverb","35","50","90","100","15","0","gain","-n","-1.5"], env=SFLIB)

# ---------- assemble: Ken Burns + xfade + mux ----------
def assemble(cfg, d, nframes, out):
    import glob
    frames=sorted(glob.glob(f"{d}/frames/frame*.png")); os.makedirs(f"{d}/segs",exist_ok=True)
    FPS=30; DUR=22.0; XF=1.5; FP=int(DUR*FPS)
    creep = cfg['motion']=='creep'; zs = "0.00022" if creep else "0.00035"; zmax="1.14" if creep else "1.18"
    segs=[]
    for i,img in enumerate(frames):
        o=f"{d}/segs/s{i:02d}.mp4"
        if i%3==0: z=f"min(zoom+{zs},{zmax})"; x="iw/2-(iw/zoom/2)"; y="ih/2-(ih/zoom/2)"
        elif i%3==1: z=f"min(zoom+{zs},{zmax})"; x="iw/2-(iw/zoom/2)"; y=f"(ih-ih/zoom)*(on/{FP})"
        else: z=f"if(lte(on,1),{zmax},max(zoom-{zs},1.0))"; x="iw/2-(iw/zoom/2)"; y="ih/2-(ih/zoom/2)"
        vf=(f"scale=3840:2160:force_original_aspect_ratio=increase,crop=3840:2160,"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={FP}:s=1920x1080:fps={FPS},format=yuv420p")
        sh(["ffmpeg","-y","-loop","1","-i",img,"-t",str(DUR),"-r",str(FPS),"-vf",vf,
            "-c:v","libx264","-preset","medium","-crf","19",o]); segs.append(o)
    ins=[]
    for s in segs: ins+=["-i",s]
    fc=[]; prev="0:v"; off=0.0
    for i in range(1,len(segs)):
        off+=DUR-XF; lbl=f"v{i}"; fc.append(f"[{prev}][{i}:v]xfade=transition={cfg['xfade_kind']}:duration={XF}:offset={off:.3f}[{lbl}]"); prev=lbl
    sh(["ffmpeg","-y",*ins,"-filter_complex",";".join(fc),"-map",f"[{prev}]","-c:v","libx264",
        "-preset","medium","-crf","19","-pix_fmt","yuv420p",f"{d}/video.mp4"])
    vdur=float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f"{d}/video.mp4"]).strip())
    fout=vdur-6
    sh(["ffmpeg","-y","-i",f"{d}/video.mp4","-i",f"{d}/music.wav","-filter_complex",
        f"[1:a]afade=t=in:st=0:d=2,afade=t=out:st={fout:.1f}:d=6[a]","-map","0:v","-map","[a]",
        "-c:v","copy","-c:a","aac","-b:a","256k","-movflags","+faststart","-shortest",out])

# ---------- pastoral: real generated motion (spec 01) ----------
def run_pastoral(cfg, d, seed, n_shots, want_music, out):
    """Video first, music second: the music is composed to the measured length of
    the assembled cut, and the POC is judged on video alone."""
    import ff_pastoral, ff_pastoral_music
    silent = ff_pastoral.render(cfg, d, seed, n_shots)
    if not want_music:
        ff_pastoral.finalize_silent(silent, out)
        print("music skipped (video-only cut)", flush=True)
        return
    vdur = ff_pastoral.probe_duration(silent)
    print(f"music for {vdur:.1f}s...", flush=True)
    meta = ff_pastoral_music.compose_pastoral(d, seed, vdur)
    print("compose", meta, flush=True)
    render_pastoral(d)
    ff_pastoral.mux(silent, f"{d}/music.wav", out)


def run_slideshow(cfg, d, seed, n, out):
    meta=ff_compose.compose(d, seed); print("compose",meta,flush=True)
    print("music...",flush=True)
    (render_orchestral if cfg['music']=='orchestral' else (lambda dd: render_horror(dd, seed)))(d)
    print("images...",flush=True); nf=gen_images(cfg, seed, n, f"{d}/frames")
    print("assemble...",flush=True); assemble(cfg, d, nf, out)


def main():
    argv=[a for a in sys.argv[1:] if not a.startswith("--")]
    flags={a for a in sys.argv[1:] if a.startswith("--")}
    genre=argv[0]; seed=int(argv[1]) if len(argv)>1 else int(time.time())%100000
    cfg=ff_pools.GENRES[genre]
    video = cfg.get('pipeline')=='video'
    poc = "--poc" in flags
    # POC: six chained shots from the head of the water journey, ~60s, judged on video.
    default_n = (6 if poc else len(cfg['journey'])) if video else 33
    n=int(argv[2]) if len(argv)>2 else default_n
    want_music = "--no-music" not in flags and not (video and poc and "--music" not in flags)
    d=f"{ROOT}/runs/{genre}-{seed}" + ("-poc" if poc else ""); os.makedirs(d,exist_ok=True)
    print(f"== filmforge {genre} seed={seed} n={n}{' POC' if poc else ''} ==",flush=True)
    label = cfg['label'] + ("-poc" if poc else "")
    out=f"{ROOT}/films/{label}-{seed}.mp4"
    if video: run_pastoral(cfg, d, seed, n, want_music, out)
    else: run_slideshow(cfg, d, seed, n, out)
    link=f"{SERVE_DIR}/{label}-{seed}.mp4"
    try: os.remove(link)
    except FileNotFoundError: pass
    os.makedirs(SERVE_DIR, exist_ok=True)
    os.symlink(out, link)
    print(f"DONE {out}",flush=True)
    print(f"URL {SERVE_URL}/{label}-{seed}.mp4",flush=True)

if __name__=="__main__": main()
