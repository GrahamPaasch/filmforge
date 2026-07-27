#!/usr/bin/env python3
"""Push the CPU half of filmforge onto the other two boxes.

The 3090 machine should be doing exactly one thing during a render: generating.
Everything else here is pure CPU and was competing with it — ffmpeg encodes in
particular, which is why the CPU package sat at 89C during the pastoral run.

  encode host   192.168.5.2   32 cores, ffmpeg installed, 366 GB free
  archive host  192.168.5.8   94 GB RAM, 754 GB free

Both are key-based SSH, no password. Everything degrades gracefully: if a host is
unreachable the work just runs locally, because a render must never fail because a
side machine is off.
"""
import os, shlex, subprocess, uuid

ENCODE_HOST = os.environ.get("FF_ENCODE_HOST", "192.168.5.2")
ARCHIVE_HOST = os.environ.get("FF_ARCHIVE_HOST", "192.168.5.8")
ARCHIVE_DIR = os.environ.get("FF_ARCHIVE_DIR", "~/filmforge-archive")
REMOTE_TMP = "/tmp/ff-encode"

SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6",
       "-o", "StrictHostKeyChecking=accept-new"]


def _run(cmd, **kw):
    return subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, **kw)


def host_up(host):
    """Cheap reachability probe. Never raises — a dead helper box is not an error."""
    try:
        subprocess.run(SSH + [f"gpaasch@{host}", "true"], check=True, timeout=10,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def remote_ffmpeg(inputs, argv_after_inputs, dest, host=None, input_args=None):
    """Run one ffmpeg job on the encode host.

    `inputs` is the ordered list of local input paths; `argv_after_inputs` is
    everything that follows them on the command line (filters, codec flags), with
    the OUTPUT omitted — we append it. Inputs are copied over, the job runs there,
    and only the result comes back.

    Returns True if it ran remotely, False if the caller should do it locally.
    """
    host = host or ENCODE_HOST
    if not host_up(host):
        return False
    job = f"{REMOTE_TMP}/{uuid.uuid4().hex}"
    try:
        _run(SSH + [f"gpaasch@{host}", f"mkdir -p {shlex.quote(job)}"])
        remote_inputs = []
        for n, p in enumerate(inputs):
            rp = f"{job}/in{n:03d}{os.path.splitext(p)[1] or '.mp4'}"
            _run(["scp", "-q", "-o", "BatchMode=yes", p, f"gpaasch@{host}:{rp}"])
            remote_inputs.append(rp)
        rout = f"{job}/out{os.path.splitext(dest)[1] or '.mp4'}"
        cmd = ["ffmpeg", "-y"]
        for rp in remote_inputs:
            # Input options (-framerate, -f, -r on the read side) MUST precede their
            # -i or ffmpeg silently ignores them. Passing -framerate after the input
            # is what turned a 30-frame shot into 16 frames of output.
            cmd += list(input_args or []) + ["-i", rp]
        cmd += list(argv_after_inputs) + [rout]
        _run(SSH + [f"gpaasch@{host}", " ".join(shlex.quote(c) for c in cmd)])
        _run(["scp", "-q", "-o", "BatchMode=yes", f"gpaasch@{host}:{rout}", dest])
        return True
    except Exception:
        return False
    finally:
        try:
            _run(SSH + [f"gpaasch@{host}", f"rm -rf {shlex.quote(job)}"])
        except Exception:
            pass


def ffmpeg_job(inputs, argv_after_inputs, dest, prefer_remote=True, input_args=None):
    """Encode on the helper box when we can, locally when we can't. One call site
    for every heavy ffmpeg stage in the pipeline."""
    if prefer_remote and remote_ffmpeg(inputs, argv_after_inputs, dest, input_args=input_args):
        return dest
    cmd = ["ffmpeg", "-y"]
    for p in inputs:
        cmd += list(input_args or []) + ["-i", p]
    cmd += list(argv_after_inputs) + [dest]
    _run(cmd)
    return dest


def archive(path, host=None, dest_dir=None):
    """Copy a finished film or a whole run directory to the big-disk box.

    This exists because spec 01's first POC died with the root filesystem at 20 GB
    free. Generated video is enormous and this machine is the one that can least
    afford to fill up."""
    host = host or ARCHIVE_HOST
    dest_dir = dest_dir or ARCHIVE_DIR
    if not host_up(host):
        return None
    try:
        _run(SSH + [f"gpaasch@{host}", f"mkdir -p {dest_dir}"])
        _run(["rsync", "-a", "--partial", "-e", " ".join(SSH),
              path.rstrip("/"), f"gpaasch@{host}:{dest_dir}/"])
        return f"{host}:{dest_dir}/{os.path.basename(path.rstrip('/'))}"
    except Exception:
        return None


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        for h, what in ((ENCODE_HOST, "encode"), (ARCHIVE_HOST, "archive")):
            print(f"{what:8} {h:14} {'up' if host_up(h) else 'DOWN'}")
    elif len(sys.argv) > 2 and sys.argv[1] == "archive":
        print(archive(sys.argv[2]) or "archive failed")
