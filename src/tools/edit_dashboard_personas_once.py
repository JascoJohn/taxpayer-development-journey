"""Editing Pass 3 (one-off): carry the Pass 2/3 persona-picture edits into the dashboard's persona illustrations (dashboard/assets/*_persona_*.png).

The cards of report/working/images/persona_<stage>_pass2.jpg hold the same illustrations as the dashboard assets, at another scale. For each stage this
finds the box the illustration occupies in the original card, takes the pixels that the Pass 2/3 edit changed (bubble lettering, certificate emblems, cap
badge, plaque) from the edited card, scales them down to the asset's size and pastes them over the original asset, leaving every other pixel untouched.
Originals are kept in _archive/process_records/dashboard_assets_before_pass3/. Run once; not part of the pipeline.
"""
import io, os, shutil, zipfile
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCX = os.path.join(ROOT, "report", "submission_v1", "Taxpayer_Development_Journey_submission_v1.docx")
IMG = os.path.join(ROOT, "report", "working", "images")
ASSETS = os.path.join(ROOT, "dashboard", "assets")
KEEP = os.path.join(ROOT, "_archive", "process_records", "dashboard_assets_before_pass3")
# where each illustration sits inside its original persona card (found by matching the asset against the card)
BOXES = {"seed": {"x": 62, "y": 140, "W": 1076, "H": 784}, "entry": {"x": 62, "y": 129, "W": 1076, "H": 807}, "active": {"x": 62, "y": 121, "W": 1076, "H": 823}, "enterprise": {"x": 169, "y": 101, "W": 862, "H": 862}, "asset": {"x": 178, "y": 101, "W": 844, "H": 862}, "legacy": {"x": 255, "y": 101, "W": 690, "H": 862}}
SOURCES = {"seed": ("image15.jpg", "seed_persona_amina.png"), "entry": ("image17.jpg", "entry_persona_juma.png"), "active": ("image19.jpg", "active_persona_neema.png"),
           "enterprise": ("image21.jpg", "enterprise_persona_asha.png"), "asset": ("image24.jpg", "asset_persona_joseph.png"), "legacy": ("image27.jpg", "legacy_persona_mzeehamisi.png")}


def main():
    os.makedirs(KEEP, exist_ok=True)
    z = zipfile.ZipFile(DOCX)
    for st, (media, asset_name) in SOURCES.items():
        b = BOXES[st]
        ap = os.path.join(ASSETS, asset_name)
        bak = os.path.join(KEEP, asset_name)
        if not os.path.exists(bak):
            shutil.copy2(ap, bak)
        asset = Image.open(bak).convert("RGB")
        aw, ah = asset.size
        box = (b["x"], b["y"], b["x"] + b["W"], b["y"] + b["H"])
        orig = Image.open(io.BytesIO(z.read("word/media/" + media))).convert("RGB").crop(box)
        edit = Image.open(os.path.join(IMG, "persona_%s_pass2.jpg" % st)).convert("RGB").crop(box)
        diff = np.abs(np.array(orig).astype(int) - np.array(edit).astype(int)).max(axis=2)
        mask = diff > 40
        mask = ndi.binary_opening(mask, iterations=1)
        lab, n = ndi.label(ndi.binary_dilation(mask, iterations=6))
        mask = ndi.binary_dilation(mask, iterations=4)
        if st in ("seed",) or not mask.any():
            print(st, "no illustration edit; asset unchanged")
            asset.save(ap)
            continue
        # only the card's edited pixels (not the frame/panel), resized to the asset
        m_small = Image.fromarray((mask * 255).astype(np.uint8)).resize((aw, ah), Image.BILINEAR)
        m_arr = np.array(m_small).astype(float)[..., None] / 255.0
        m_arr = ndi.gaussian_filter(m_arr, sigma=(1.2, 1.2, 0))
        e_small = np.array(edit.resize((aw, ah), Image.LANCZOS)).astype(float)
        out = np.array(asset).astype(float) * (1 - m_arr) + e_small * m_arr
        Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8)).save(ap, optimize=True)
        print(st, "patched %.2f%% of the asset" % (100 * (m_arr[..., 0] > 0.5).mean()))


if __name__ == "__main__":
    main()
