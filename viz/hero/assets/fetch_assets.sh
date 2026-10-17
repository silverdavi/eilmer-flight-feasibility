#!/usr/bin/env bash
# Download the CC0 assets used by the Blender renders into viz/hero/assets/_dl/ (see LICENSES.md).
#
#   viz/hero/assets/fetch_assets.sh            # Figure 3: habit texture + MakeHuman skin/eyes (~300 MB)
#   viz/hero/assets/fetch_assets.sh --monk     # + MPFB2, to rebuild monk*.blend with monk.py
#   viz/hero/assets/fetch_assets.sh --covers   # + stone texture and sky HDRIs for scene/ (~1 GB)
set -euo pipefail
cd "$(dirname "$0")"
DL=_dl
mkdir -p "$DL/tex" "$DL/hdri" "$DL/mh"
get() { [ -s "$2" ] || curl -fL --retry 3 -o "$2" "$1"; }

PH=https://dl.polyhaven.org/file/ph-assets
tex() { for m in diff nor_gl rough disp ao arm; do
  get "$PH/Textures/jpg/4k/$1/$1_${m}_4k.jpg" "$DL/tex/$1_${m}_4k.jpg"; done; }

tex caban

get http://files.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip \
  "$DL/mh_sys.zip"
[ -d "$DL/mh/skins" ] || unzip -q "$DL/mh_sys.zip" 'skins/*' 'eyes/*' 'eyebrows/*' 'eyelashes/*' -d "$DL/mh"

for a in "$@"; do case "$a" in
  --monk)
    [ -d "$DL/mpfb2" ] || git clone https://github.com/makehumancommunity/mpfb2.git "$DL/mpfb2"
    git -C "$DL/mpfb2" checkout -q 3af0cd5a2ffba072e93a34e5f6f494fdc4813ddf
    mkdir -p _blender_user/extensions/user_default
    ln -sfn "$PWD/$DL/mpfb2/src/mpfb" _blender_user/extensions/user_default/mpfb ;;
  --covers)
    tex castle_wall_varriation
    get "$PH/HDRIs/hdr/16k%2B/kloppenheim_06_puresky_16k.hdr" "$DL/hdri/kloppenheim_06_puresky_16k.hdr"
    for h in kloppenheim_06_puresky syferfontein_18d_clear_puresky; do
      get "$PH/HDRIs/hdr/8k/${h}_8k.hdr" "$DL/hdri/${h}_8k.hdr"; done ;;
  *) echo "unknown option $a" >&2; exit 2 ;;
esac; done
echo "assets in $(pwd)/$DL"
