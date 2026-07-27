#!/usr/bin/env python3
"""Render the generated 3D character with a toon shader.

The missing piece all night was dimensionality. Every failure came from trying to
transform OUTPUT — pushing the pixels of a finished picture around. Animation is
made the other way: you pose a model that knows what is behind and beside
everything, and rendering is the last step, never the thing you edit.

That is why occlusion kept killing us. Inpainting invented an extra arm because a
flat image genuinely does not contain what is underneath the bow. A model does,
for free.

So: Hunyuan3D turned the illustration into a mesh, and this renders it. Every frame
is a fresh render of ONE consistent object, which is why nothing can melt, flicker,
or lose a prop — the same triangles are on screen every frame, just seen from a
different angle.

Toon look is two passes: an inflated back-face hull in black for the ink line, then
the surface with its lighting quantised into flat bands, the way cel shading works.
"""
import math, os, subprocess

import numpy as np
import moderngl
import trimesh

W, H = 854, 640
FPS = 12

VERT = """
#version 330
uniform mat4 mvp;
uniform mat4 model;
uniform float inflate;
in vec3 in_pos;
in vec3 in_norm;
out vec3 v_norm;
void main() {
    vec3 p = in_pos + in_norm * inflate;
    v_norm = mat3(model) * in_norm;
    gl_Position = mvp * vec4(p, 1.0);
}
"""

FRAG = """
#version 330
uniform vec3 light;
uniform int outline;
in vec3 v_norm;
out vec4 f_color;
void main() {
    if (outline == 1) { f_color = vec4(0.0, 0.0, 0.0, 1.0); return; }
    float d = max(dot(normalize(v_norm), normalize(light)), 0.0);
    // quantise into flat bands -- this is what makes it read as cel art rather
    // than as a smooth 3D render
    float band = d > 0.75 ? 1.0 : (d > 0.45 ? 0.72 : (d > 0.2 ? 0.42 : 0.16));
    f_color = vec4(vec3(band), 1.0);
}
"""


def look_at(eye, target, up=(0, 1, 0)):
    f = np.array(target, dtype='f4') - np.array(eye, dtype='f4')
    f /= np.linalg.norm(f)
    u = np.array(up, dtype='f4')
    s = np.cross(f, u); s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.eye(4, dtype='f4')
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    t = np.eye(4, dtype='f4')
    t[:3, 3] = -np.array(eye, dtype='f4')
    return m @ t


def perspective(fov, aspect, near, far):
    t = 1.0 / math.tan(math.radians(fov) / 2)
    m = np.zeros((4, 4), dtype='f4')
    m[0, 0] = t / aspect
    m[1, 1] = t
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]], dtype='f4')


def load_mesh(path):
    m = trimesh.load(path, force='mesh')
    m.vertices -= m.bounding_box.centroid
    m.vertices /= np.abs(m.vertices).max()
    if m.vertex_normals is None or len(m.vertex_normals) != len(m.vertices):
        m.rezero()
    return (np.asarray(m.vertices, dtype='f4'),
            np.asarray(m.vertex_normals, dtype='f4'),
            np.asarray(m.faces, dtype='i4'))


def render(glb, seconds=10, seed=31, workdir="/home/gpaasch/filmforge/runs/render3d"):
    import ff_toon_music, make_film as MF, ff_progress, ff_puppet_viola as V
    os.makedirs(f"{workdir}/frames", exist_ok=True)

    n_bars = max(1, round(seconds / ff_toon_music.BAR_SECONDS))
    midi, meta = ff_toon_music.compose_toon(workdir, seed, n_bars)
    music = ff_toon_music.render_toon_music(workdir, midi, f"{workdir}/music.wav",
                                            MF.FS, MF.SF, MF.SOX, MF.SFLIB)
    notes = V.read_score(midi, meta["bpm"])
    print(f"music {meta}; {len(notes)} onsets", flush=True)

    verts, norms, faces = load_mesh(glb)
    print(f"mesh: {len(verts)} vertices, {len(faces)} faces", flush=True)

    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
    prog = ctx.program(vertex_shader=VERT, fragment_shader=FRAG)
    vbo = ctx.buffer(np.hstack([verts, norms]).astype('f4').tobytes())
    ibo = ctx.buffer(faces.tobytes())
    vao = ctx.vertex_array(prog, [(vbo, '3f 3f', 'in_pos', 'in_norm')], ibo)
    fbo = ctx.simple_framebuffer((W, H))
    fbo.use()

    proj = perspective(32.0, W / H, 0.1, 20.0)
    total = int(seconds * FPS)
    ff_progress.install_page()
    prog_bar = ff_progress.Progress(f"render3d-{seed}", total, "rendering the mesh")

    for n in range(total):
        t = n / FPS
        last = max([ts for (ts, _p, _v) in notes if ts <= t], default=-9)
        pulse = max(0.0, 1.0 - (t - last) / 0.2)

        # the camera orbits, and pushes in a little on every note attack
        ang = 0.55 * math.sin(t * 0.5)
        dist = 3.05 - 0.10 * pulse
        eye = (math.sin(ang) * dist, 0.12 + 0.05 * math.sin(t * 0.9), math.cos(ang) * dist)
        view = look_at(eye, (0, 0, 0))
        model = rot_y(0.25 * math.sin(t * 0.35))
        mvp = (proj @ view @ model).astype('f4')

        fbo.clear(1.0, 1.0, 1.0, 1.0)
        prog['mvp'].write(mvp.T.tobytes())
        prog['model'].write(model.T.tobytes())
        prog['light'].value = (0.5, 0.8, 0.9)

        # pass 1: inflated hull, front faces culled -> a black ink outline
        ctx.front_face = 'cw'
        prog['inflate'].value = 0.018
        prog['outline'].value = 1
        vao.render()

        # pass 2: the surface itself, in flat bands
        ctx.front_face = 'ccw'
        prog['inflate'].value = 0.0
        prog['outline'].value = 0
        vao.render()

        from PIL import Image
        Image.frombytes('RGB', (W, H), fbo.read(components=3)).transpose(
            Image.FLIP_TOP_BOTTOM).save(f"{workdir}/frames/f{n:04d}.png")
        prog_bar.step()

    prog_bar.finish("encoding")
    silent = f"{workdir}/silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{workdir}/frames/f%04d.png",
                    "-vf", "format=gray,noise=alls=5:allf=t+u,vignette=PI/5",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-r", str(FPS), silent],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = f"/home/gpaasch/filmforge/films/render3d-{seed}.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", silent, "-i", music, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
                    "-movflags", "+faststart", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"DONE {out}", flush=True)
    return out


if __name__ == "__main__":
    import sys
    glb = sys.argv[1] if len(sys.argv) > 1 else "/home/gpaasch/ComfyUI/output/betty3d_00001_.glb"
    render(glb, seconds=float(sys.argv[2]) if len(sys.argv) > 2 else 10)
