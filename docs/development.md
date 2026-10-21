# Development and data updates

## Environment and checks

Use uv 0.13.4 or newer. If an existing uv installation is older, run
`uv self update` before syncing. Development and CI use Python 3.14, matching
the interpreter selected in `.python-version`.

```bash
uv sync --locked
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync ty check
uv run --no-sync pytest -q
```

Run `./fcode.sh` to sort imports and format Python files with Ruff. The
`./protein_app` launcher starts Streamlit using the locked environment.
CI runs the same checks. Update dependencies with `uv lock --upgrade`, then
sync and run the checks again. Keep direct dependency requirements in
`pyproject.toml` current when upgrading.

Streamlit supplies Pillow as a runtime dependency. Asset import also uses
Pillow, declared explicitly in the development group. OpenCV and system OpenGL
packages are no longer required.

## Refresh the simulation media

The app runs entirely from the committed `data/` directory. The optional refresh
workflow requires a separate porous_media checkout, its research environment,
completed SPT analysis, the original study data, and FFmpeg. These are not app
runtime requirements.

Use the current `results/spt/catalog.tsv` for simulation conditions and each
figure's `manifest.json` to resolve its active generation. Older plot catalogues
can still refer to previous generations. The catalogue must contain all 48
complete simulations: six zonation patterns and eight substrate flows. Flow
units remain unspecified because the source does not declare them.

Current analysis figures contain five time points and five scalar fields over
24 hours. The full lobule geometry, manuscript color maps, and shared color
ranges come from the upstream renderer. The app stores images at 2000 pixels
wide. Videos contain 200 frames at 12 fps, use H.264 with `yuv420p`, and include
MP4 fast-start metadata.

If the current analysis has no videos, generate them in a separate temporary
output directory. From the porous_media checkout, after syncing its research
environment:

```bash
PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg MPLCONFIGDIR=/tmp/spt-app-mpl \
  .venv/bin/python -m research.spt.plot_geometry \
  --input-root /data/koeniglab/spt \
  --data-root results/spt \
  --output-root /tmp/spt-app-source \
  --study simulations --geometry lobulus \
  --formats png --no-overviews \
  --video-frames 200 --fps 12 --dpi 125 --workers 4
```

This reads existing reconstructed simulation histories and writes only to the
temporary output directory. It does not rerun simulations or alter the study
data or existing analysis. Do not create videos from the five static snapshots;
the renderer samples native simulation histories at all 200 requested times.

From the spt-app checkout, import conditions from the current analysis and both
images and videos from the new export:

```bash
uv run --no-sync python data/convert_videos_images.py \
  --source-root ../porous_media/results/spt \
  --media-root /tmp/spt-app-source
```

If the current analysis already contains videos, omit `--media-root`. The
importer validates the cohort, artifact fingerprints, source histories, layers,
and shared color ranges before preparing replacements. All conversions finish
in a temporary directory before any bundled assets are replaced. Run the tests
after importing and review the resulting images and video playback.

`data/provenance.json` records the source commit, source catalogue hash, rendering
options, active figure generations, and SHA-256 hashes for source and bundled
media. Commit it together with `simulations.tsv` and all updated images and videos.
