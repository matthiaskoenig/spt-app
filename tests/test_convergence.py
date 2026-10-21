"""Check convergence media, scientific comparison windows, and study controls."""

import json
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from data.convert_videos_images import sha256
from data.import_convergence import MESH_IDS, RUN_IDS, load_runs, read_table, write_table

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "convergence"
COUNTS = (708, 1224, 2640, 4398, 10080, 17586, 39246)
END_TIMES = (86400.0, 86400.0, 86400.0, 86400.0, 86400.0, 77687.6, 36590.0)


def convergence_app() -> AppTest:
    """Open the convergence study through the same control used by visitors."""
    app = AppTest.from_file(str(ROOT / "spt_app.py")).run()
    app.radio(key="study").set_value("Convergence study").run()
    return app


def test_every_convergence_mesh() -> None:
    """All seven meshes render their own media and correct source completion."""
    app = convergence_app()
    assert not app.exception
    assert app.selectbox(key="convergence_run").value == "convergence_12500"
    assert app.radio(key="convergence_scale").value == "Symlog"
    assert [tab.label for tab in app.tabs] == [
        "Selected mesh",
        "Study comparison",
        "Spatial profiles",
        "Differences",
    ]
    videos = set()
    images = set()
    for run_id, count, end in zip(RUN_IDS, COUNTS, END_TIMES, strict=True):
        app.selectbox(key="convergence_run").select(run_id).run()
        assert not app.exception
        assert not app.error
        assert app.metric[0].value == f"{count:,}"
        assert len(app.warning) == int(end < 86400)
        if end < 86400:
            assert f"{end:,.1f} s" in app.warning[0].value
        video = app.get("video")[0].proto
        assert run_id in video.alt
        assert video.url.startswith("/mock/media/")
        assert video.autoplay and video.loop and video.muted
        videos.add(video.url)
        images.add(app.get("image")[0].proto.imgs[0].url)
    assert len(videos) == len(images) == 7


def test_convergence_controls_and_return_to_simulations() -> None:
    """Scale, readout, profile time and study selection remain usable."""
    app = convergence_app()
    assert not app.exception
    app.radio(key="convergence_scale").set_value("Linear").run()
    assert not app.exception
    for field in ("rr_(S_ext)", "rr_(P_ext)", "rr_protein", "rr_(T)", "rr_necrosis"):
        app.selectbox(key="convergence_field").select(field).run()
        assert not app.exception
    for time in (0.0, 5400.0, 36590.0):
        app.select_slider(key="convergence_time").set_value(time).run()
        assert not app.exception
    app.radio(key="study").set_value("Simulations").run()
    assert not app.exception
    assert app.selectbox(key="simulation_pattern").value == "linear increase"
    assert app.select_slider(key="simulation_flow").value == 3
    assert "sim012" in app.markdown[0].value


def test_convergence_provenance_and_assets() -> None:
    """Every exported study file matches its provenance and remains readable."""
    provenance = json.loads((DATA / "provenance.json").read_text())
    assert provenance["comparison"]["end_s"] == 36590
    assert provenance["comparison"]["reference_run"] == "convergence_06250"
    for name, record in provenance["files"].items():
        path = DATA / name
        assert sha256(path) == record["sha256"]
        if path.suffix == ".png":
            with Image.open(path) as image:
                image.verify()
    assert all((DATA / f"{run_id}_h264.mp4").is_file() for run_id in RUN_IDS)
    assert all((DATA / f"{run_id}_mesh.png").is_file() for run_id in RUN_IDS)


def test_native_and_matched_history_endpoints() -> None:
    """Native histories retain truncation; matched comparisons do not extrapolate."""
    catalogue = pd.read_csv(DATA / "convergence.tsv", sep="\t")
    assert catalogue["run_id"].tolist() == list(RUN_IDS)
    assert catalogue["num_cells"].tolist() == list(COUNTS)
    assert catalogue["tend_s"].tolist() == list(END_TIMES)
    assert catalogue["complete"].tolist() == [True] * 5 + [False, False]
    native = pd.read_csv(DATA / "native-timecourses.tsv", sep="\t")
    endpoints = native.groupby("run")["time"].max()
    for run_id, end in zip(RUN_IDS, END_TIMES, strict=True):
        assert endpoints[run_id] == end
    matched = pd.read_csv(DATA / "matched-timecourses.tsv", sep="\t")
    assert set(matched["run"]) == set(RUN_IDS)
    assert matched["time"].min() == 0
    assert matched["time"].max() == 36590
    assert matched["time"].nunique() == 51
    for run_id, count in zip(RUN_IDS, COUNTS, strict=True):
        assert set(matched.loc[matched["run"] == run_id, "num_cells"]) == {count}
    # Keep the actual coarsest-mesh outlier in the exported results.
    substrate = matched[
        (matched["run"] == RUN_IDS[0]) & (matched["field"] == "rr_(S_ext)")
    ]
    assert substrate["mean"].max() > 2000


def test_differences_and_necrosis_units() -> None:
    """Differences use the finest available mesh and preserve undefined ratios."""
    means = pd.read_csv(DATA / "convergence-means.tsv", sep="\t")
    assert set(means["reference_run"]) == {"convergence_06250"}
    for run_id, count in zip(RUN_IDS, COUNTS, strict=True):
        assert set(means.loc[means["run"] == run_id, "num_cells"]) == {count}
    reference = means[means["run"] == "convergence_06250"]
    assert (reference["absolute_difference"] == 0).all()
    assert means["relative_difference"].isna().any()
    profiles = pd.read_csv(DATA / "convergence-profiles.tsv", sep="\t")
    assert set(profiles["reference_run"]) == {"convergence_06250"}
    assert profiles["reference_volume_coverage"].between(0, 1 + 1e-8).all()
    matched = pd.read_csv(DATA / "matched-timecourses.tsv", sep="\t")
    necrosis = matched.loc[matched["field"] == "rr_necrosis", "mean"]
    assert necrosis.between(0, 1 + 1e-8).all()


def test_import_preserves_incomplete_runs(tmp_path: Path) -> None:
    """Readable short histories remain part of the exported seven-mesh cohort."""
    records = []
    for mesh, run_id, count, end in zip(
        MESH_IDS, RUN_IDS, COUNTS, END_TIMES, strict=True
    ):
        record = {
            "study": "convergence_sixth",
            "run_id": run_id,
            "status": "available",
            "complete": str(end == 86400),
            "tstart_s": "0",
            "tend_s": str(end),
            "expected_duration_s": "86400",
        }
        records.append(record)
        directory = tmp_path / "convergence_lobulus" / "runs" / run_id
        directory.mkdir(parents=True)
        (directory / "manifest.json").write_text(
            json.dumps(
                {
                    "catalog": {
                        "num_cells": count,
                        "num_points": count + 10,
                        "num_steps": 367 if mesh == "06250" else 866,
                        "tend_s": end,
                    }
                }
            )
        )
    write_table(tmp_path / "catalog.tsv", list(records[0]), records)
    runs = load_runs(tmp_path)
    assert [row["run_id"] for row in runs] == list(RUN_IDS)
    assert [row["complete"] for row in runs] == ["True"] * 5 + ["False", "False"]
    assert [int(row["num_cells"]) for row in runs] == list(COUNTS)


def test_partial_convergence_catalogue_is_rejected(tmp_path: Path) -> None:
    """A partial source selection cannot silently drop a mesh."""
    write_table(tmp_path / "catalog.tsv", ["study", "run_id"], [])
    with pytest.raises(ValueError, match="all seven convergence"):
        load_runs(tmp_path)


def test_table_round_trip_preserves_precision_and_missing_fields(tmp_path: Path) -> None:
    """Normalize Windows line endings without trimming empty final columns."""
    source = tmp_path / "source.tsv"
    source.write_bytes(
        b"run\tvalue\toptional\r\n"
        b"convergence_06250\t1.2345678901234567\t\r\n"
        b"convergence_50000\t\t\r\n"
    )
    columns, rows = read_table(source)
    destination = tmp_path / "export.tsv"
    write_table(destination, columns, rows)
    assert destination.read_bytes() == source.read_bytes().replace(b"\r\n", b"\n")
