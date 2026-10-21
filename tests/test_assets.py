"""Verify bundled media integrity and safe analysis imports."""

import csv
import json
from pathlib import Path

import pytest
from PIL import Image

from data.convert_videos_images import (
    SIMULATION_IDS,
    artifact,
    import_assets,
    load_simulations,
    sha256,
)

DATA = Path(__file__).resolve().parents[1] / "data"


def test_bundled_assets_match_provenance() -> None:
    """Every catalogue entry has the exact image and video recorded at export."""
    provenance = json.loads((DATA / "provenance.json").read_text())
    with (DATA / "simulations.tsv").open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert [row["sim_key"] for row in rows] == list(SIMULATION_IDS)
    assert sorted(provenance["assets"]) == list(SIMULATION_IDS)
    assert len({(row["pattern_key"], row["boundary_flow_key"]) for row in rows}) == 48
    assert all(row["boundary_flow_unit"] == "unspecified in source" for row in rows)
    expected_flows = (
        -1.60747e-09,
        -7.58061e-06,
        -1.41387e-05,
        -2.51064e-05,
        -4.15705e-05,
        -5.37477e-05,
        -6.33526e-05,
        -7.12447e-05,
    )
    for row in rows:
        assert (
            float(row["boundary_flow"]) == expected_flows[int(row["boundary_flow_key"])]
        )
    for simulation_id in SIMULATION_IDS:
        record = provenance["assets"][simulation_id]
        image_path = DATA / f"{simulation_id}.png"
        video_path = DATA / f"{simulation_id}_h264.mp4"
        assert sha256(image_path) == record["image_sha256"]
        assert sha256(video_path) == record["video_sha256"]
        with Image.open(image_path) as image:
            assert image.width == 2000
            image.verify()


def test_partial_catalogue_is_rejected(tmp_path: Path) -> None:
    """A partial upstream export cannot silently remove simulations."""
    (tmp_path / "catalog.tsv").write_text("study\trun_id\nsimulations_sixth\tsim001\n")
    with pytest.raises(ValueError, match="all 48 simulations"):
        load_simulations(tmp_path)


def test_missing_sources_preserve_bundled_assets(tmp_path: Path) -> None:
    """An unavailable analysis leaves the previous app media intact."""
    destination = tmp_path / "data"
    destination.mkdir()
    image = destination / "sim001.png"
    image.write_bytes(b"previous image")
    with pytest.raises(FileNotFoundError):
        import_assets(tmp_path / "missing", tmp_path / "missing", destination)
    assert image.read_bytes() == b"previous image"
    assert list(destination.iterdir()) == [image]


def test_stale_manifest_is_rejected(tmp_path: Path) -> None:
    """Do not publish a file that differs from its completed generation."""
    directory = tmp_path / "figures" / "simulations_lobulus" / "sim001"
    generation = directory / "generation-test"
    generation.mkdir(parents=True)
    image = generation / "timecourse.png"
    image.write_bytes(b"original")
    info = image.stat()
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "generation": generation.name,
                "outputs": [
                    {
                        "path": str(image),
                        "size": info.st_size,
                        "mtime_ns": info.st_mtime_ns,
                    }
                ],
            }
        )
    )
    image.write_bytes(b"changed source")
    with pytest.raises(ValueError, match="fingerprint"):
        artifact(tmp_path, "sim001", "timecourse.png")
