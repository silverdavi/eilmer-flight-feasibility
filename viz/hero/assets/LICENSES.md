# Third-party assets used in the Blender renders

Figure 3 (`figures/fig_apparatus.png`) and the cover images are path-traced (Blender 5.0.1
Cycles) from 3D geometry; no generated images. Every external asset below is CC0 1.0 (public
domain dedication); no attribution is legally required, but the authors are credited here.
The assets are not redistributed in this repository: `fetch_assets.sh` downloads them into
`assets/_dl/` (Figure 3 by default, `--monk` to rebuild the monk, `--covers` for the covers).

## Human (the monk) — MakeHuman / MPFB2

| Asset | Source | Licence | Needed for |
|---|---|---|---|
| MakeHuman base mesh, macro targets, `default` rig, proxy-fitting data (via MPFB2, commit `3af0cd5`, cloned to `_dl/mpfb2`) | https://github.com/makehumancommunity/mpfb2 | assets CC0 1.0 (`_dl/mpfb2/LICENSE.ASSETS.md`); code GPLv3, but per `LICENSE.md` §D the MakeHuman team claims nothing over output (saved models, renders) | rebuilding `monk*.blend` (`--monk`) |
| Skin `young_caucasian_male` (diffuse texture), eyes `high-poly` + `brown` iris, eyebrows `eyebrow007`, eyelashes `eyelashes02` (MakeHuman system assets, `makehuman_system_assets_cc0.zip`, unpacked to `_dl/mh`) | http://files.makehumancommunity.org/asset_packs/makehuman_system_assets/ | CC0 1.0 — "explicitly released as CC0 in September 2020" (header of each `.mhclo`/`.obj`; copyright holders Data Collection AB, Joel Palmius, Jonas Hauquier) | Figure 3, covers |

The habit, cowl, rope belt, sandals and lashings are original geometry built and
cloth-simulated in `assets/monk.py` (no external garment assets). `monk_prone.blend` is the
cached result of `monk.py -- --variant prone --frames 60 --out viz/hero/assets/monk_prone.blend`;
its textures point at `viz/hero/assets/_dl/` relative to the repository root.

## Textures — Poly Haven (https://polyhaven.com, CC0 1.0)

| Texture | Author | Used for |
|---|---|---|
| `caban` (4k: diff, nor_gl, rough) | colormass (photography), Rico Cilliers (processing) | woollen weave of the habit (Figure 3, covers) |
| `castle_wall_varriation` (4k: diff, nor_gl, rough, disp) | Rob Tuytel | tower and nave rubble walling (covers) |

## Skies — Poly Haven HDRIs (CC0 1.0), covers only

Figure 3 is lit by a studio world and lamps defined in `final/render_fig3_v2.py`; it uses no HDRI.

| HDRI | Authors | Used for |
|---|---|---|
| `kloppenheim_06_puresky` (16k final, 8k preview) | Greg Zaal (original), Jarod Guest (sky edits) | covers A, A2, A3 |
| `syferfontein_18d_clear_puresky` (8k) | Greg Zaal (original), Jarod Guest (sky edits) | covers B and C |

The HDRI sun is clamped to the surrounding sky and its measured irradiance is returned as a
sun lamp (B, C: 12.3 W/m² measured from the 8k map; A: the evening sun in that map is
below the horizon haze, so a 3.4 W/m² low sun is added).

## Everything else

Craft: `viz/hero/render_hero.py` `build_craft()` on the planform of `viz/render_blender.py`
(project code). Terrain, fields, hedges, trees, river, houses, tower and nave: procedural
geometry and shaders written for this project (`scene/landscape.py`, `scene/tower.py`).
Fonts: none in the renders; the Figure 3 labels are drawn by `final/compose_fig3_v*.py`.
