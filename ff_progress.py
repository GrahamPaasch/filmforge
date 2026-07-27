#!/usr/bin/env python3
"""Live progress, published to the same directory the films are served from.

Graham's ask, and a fair one: "is it done yet" should not require asking. Every
long stage writes a small JSON file into films/, and progress.html polls it. The
ETA is measured, not guessed -- it comes from the mean of the frame times actually
observed so far, so it gets more honest as the run proceeds rather than less.
"""
import json, os, time

FILMS = "/home/gpaasch/filmforge/films"
STATE = f"{FILMS}/progress.json"


class Progress:
    def __init__(self, label, total, stage=""):
        self.label, self.total, self.stage = label, total, stage
        self.done = 0
        self.t0 = time.time()
        self.marks = []
        self.write()

    def step(self, n=1, stage=None):
        now = time.time()
        self.marks.append(now)
        self.done += n
        if stage:
            self.stage = stage
        self.write()

    def eta(self):
        # Use the last 20 intervals: early frames include model load time and would
        # otherwise poison the estimate for the whole run.
        recent = self.marks[-21:]
        if len(recent) < 2:
            return None
        per = (recent[-1] - recent[0]) / (len(recent) - 1)
        left = max(0, self.total - self.done)
        return per * left

    def write(self):
        eta = self.eta()
        data = {"label": self.label, "stage": self.stage, "done": self.done,
                "total": self.total, "pct": round(100 * self.done / max(1, self.total), 1),
                "elapsed": round(time.time() - self.t0),
                "eta_seconds": round(eta) if eta is not None else None,
                "updated": time.time(), "finished": self.done >= self.total}
        os.makedirs(FILMS, exist_ok=True)
        tmp = STATE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, STATE)      # atomic, so the page never reads half a file

    def finish(self, note=""):
        self.done = self.total
        self.stage = note or "done"
        self.write()


PAGE = """<!doctype html>
<meta charset="utf-8"><title>filmforge</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
 body{background:#111;color:#eee;font:16px/1.5 system-ui,sans-serif;margin:0;padding:8vh 6vw}
 h1{font-size:1.1rem;font-weight:600;letter-spacing:.02em;margin:0 0 .2rem}
 .stage{color:#9aa;margin-bottom:1.4rem;min-height:1.5em}
 .bar{background:#222;border-radius:999px;height:26px;overflow:hidden;border:1px solid #333}
 .fill{background:linear-gradient(90deg,#4a9,#7c6);height:100%;width:0;transition:width .4s}
 .row{display:flex;justify-content:space-between;margin-top:.8rem;color:#bbb}
 .big{font-size:2.6rem;font-weight:700;margin:.6rem 0 0}
 .done{color:#7c6}
</style>
<h1 id="label">waiting for a render…</h1>
<div class="stage" id="stage"></div>
<div class="bar"><div class="fill" id="fill"></div></div>
<div class="big" id="pct">0%</div>
<div class="row"><span id="count"></span><span id="eta"></span></div>
<script>
function fmt(s){if(s==null)return'—';s=Math.round(s);const m=Math.floor(s/60);
 return m?`${m}m ${String(s%60).padStart(2,'0')}s`:`${s}s`}
async function tick(){
 try{
  const r=await fetch('progress.json?'+Date.now());const d=await r.json();
  label.textContent=d.label; stage.textContent=d.stage||'';
  fill.style.width=d.pct+'%'; pct.textContent=d.pct+'%';
  count.textContent=`${d.done} / ${d.total} frames`;
  if(d.finished){eta.textContent='finished'; pct.className='big done';}
  else {eta.textContent='about '+fmt(d.eta_seconds)+' left'; pct.className='big';}
 }catch(e){stage.textContent='(no render running)'}
}
tick(); setInterval(tick, 1000);
</script>
"""


def install_page():
    os.makedirs(FILMS, exist_ok=True)
    with open(f"{FILMS}/progress.html", "w") as f:
        f.write(PAGE)
    return f"{FILMS}/progress.html"


if __name__ == "__main__":
    print(install_page())
