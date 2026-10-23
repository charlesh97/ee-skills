#!/usr/bin/env python3
"""Verification: overlay digitized curves onto the original figure crop.
Creates out/verify/<fig>_overlay.png showing source crop + replot side by side."""
import argparse, json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from PIL import Image

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--figure", required=True)
    ap.add_argument("--figures-dir", default="out/figures")
    ap.add_argument("--digitized-dir", default="out/digitized")
    ap.add_argument("--manifest", default="out/figures/manifest.json")
    ap.add_argument("--out", default="out/verify")
    args = ap.parse_args()

    manifest = json.load(open(args.manifest))
    entry = None
    for pg in manifest["pages"]:
        for f in pg["figures"]:
            if f["figure"] == args.figure:
                entry = f; break
        if entry: break
    os.makedirs(args.out, exist_ok=True)

    src = mpimg.imread(os.path.join(args.figures_dir, entry["png"]))
    data = json.load(open(os.path.join(args.digitized_dir, f"{manifest.get('part', 'part')}_fig{args.figure}.json")))
    xlog = data.get("x_log", False)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    axes[0].imshow(src)
    axes[0].set_title(f"Source crop — {data['caption']}")
    axes[0].axis("off")

    ax = axes[1]
    for cu in data["curves"]:
        xs = [p[0] for p in cu["data"]]; ys = [p[1] for p in cu["data"]]
        rgb = tuple(cu["color"])
        ax.plot(xs, ys, color=rgb, lw=1.6, label=f"curve {cu['path_idx']}")
    ax.set_xlabel(data["x_label"])
    ax.set_ylabel(data["y_label"])
    if xlog:
        ax.set_xscale("log")
    ax.grid(True, which="both", alpha=0.3)
    ax.set_title(f"Digitized — {len(data['curves'])} curves")
    ax.legend(fontsize=8)
    fig.tight_layout()
    out = os.path.join(args.out, f"{args.figure}_overlay.png")
    fig.savefig(out, dpi=140)
    print("wrote", out)

if __name__ == "__main__":
    main()
