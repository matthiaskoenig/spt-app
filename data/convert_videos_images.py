"""Import current porous_media SPT figures and browser-compatible videos."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

SIMULATION_IDS = tuple(f"sim{index:03}" for index in range(1, 49))
COLUMNS = (
    "sim_key",
    "pattern_key",
    "pattern_name",
    "boundary_flow_key",
    "boundary_flow",
    "boundary_flow_unit",
)


def sha256(path: Path) -> str:
    """Hash an artifact without loading the entire file into memory."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def load_simulations(source_root: Path) -> list[dict[str, str]]:
    """Validate the complete simulation cohort and normalize its condition keys."""
    with (source_root / "catalog.tsv").open(newline="") as handle:
        records = [
            row
            for row in csv.DictReader(handle, delimiter="\t")
            if row["study"] == "simulations_sixth"
        ]
    if sorted(row["run_id"] for row in records) != list(SIMULATION_IDS):
        raise ValueError("The source catalogue must contain all 48 simulations once")
    simulations = []
    for row in records:
        if row["complete"] != "True" or row["status"] != "available":
            raise ValueError(
                f"Simulation is unavailable or incomplete: {row['run_id']}"
            )
        simulation = {column: row[column] for column in COLUMNS[1:]}
        simulation["sim_key"] = row["run_id"]
        for column in ("pattern_key", "boundary_flow_key"):
            value = float(row[column])
            if not math.isfinite(value) or not value.is_integer():
                raise ValueError(f"Invalid {column}: {row[column]}")
            simulation[column] = str(int(value))
        if not math.isfinite(float(row["boundary_flow"])):
            raise ValueError(f"Invalid boundary flow: {row['run_id']}")
        simulations.append(simulation)
    conditions = {
        (int(row["pattern_key"]), int(row["boundary_flow_key"])) for row in simulations
    }
    if conditions != {(pattern, flow) for pattern in range(6) for flow in range(8)}:
        raise ValueError("Expected six zonation patterns and eight substrate flows")
    return sorted(simulations, key=lambda row: row["sim_key"])


def artifact(root: Path, simulation_id: str, filename: str) -> tuple[Path, dict]:
    """Resolve an artifact through its active generation and verify its fingerprint."""
    directory = root / "figures" / "simulations_lobulus" / simulation_id
    manifest = json.loads((directory / "manifest.json").read_text())
    path = (directory / manifest["generation"] / filename).resolve()
    if not path.is_relative_to(directory.resolve()):
        raise ValueError(f"Artifact escapes its simulation directory: {path}")
    record = next(
        (item for item in manifest["outputs"] if Path(item["path"]).resolve() == path),
        None,
    )
    info = path.stat()
    if (
        record is None
        or record["size"] != info.st_size
        or record["mtime_ns"] != info.st_mtime_ns
    ):
        raise ValueError(f"Artifact fingerprint does not match its manifest: {path}")
    return path, manifest


def convert_image(image_in: Path, image_out: Path, width: int, dpi: int = 150) -> None:
    """Resize a figure with Lanczos filtering and close both image handles."""
    with Image.open(image_in) as image:
        height = round(image.height * width / image.width)
        with image.resize((width, height), Image.Resampling.LANCZOS) as resized:
            resized.save(image_out, dpi=(dpi, dpi), optimize=True)


def convert_video(video_in: Path, video_out: Path) -> None:
    """Copy the H.264 video already encoded by the upstream SPT renderer."""
    shutil.copyfile(video_in, video_out)


def import_assets(source_root: Path, media_root: Path, output_root: Path) -> None:
    """Prepare the entire cohort before replacing any bundled app assets."""
    simulations = load_simulations(source_root)
    sources = []
    for row in simulations:
        simulation_id = row["sim_key"]
        _, current_manifest = artifact(source_root, simulation_id, "timecourse.png")
        image, image_manifest = artifact(media_root, simulation_id, "timecourse.png")
        video, video_manifest = artifact(media_root, simulation_id, "timecourse.mp4")
        image_configuration = image_manifest["configuration"]
        video_configuration = video_manifest["configuration"]
        current_source = current_manifest["configuration"]["source"]
        if image_configuration["source"] != current_source:
            raise ValueError(
                f"Media uses an outdated simulation history: {simulation_id}"
            )
        if image_configuration["source"] != video_configuration["source"]:
            raise ValueError(f"Image and video sources differ: {simulation_id}")
        if image_configuration["ranges"] != video_configuration["ranges"]:
            raise ValueError(f"Image and video color ranges differ: {simulation_id}")
        if (
            image_configuration["options"]["layers"]
            != video_configuration["options"]["layers"]
        ):
            raise ValueError(f"Image and video layers differ: {simulation_id}")
        sources.append((simulation_id, image, video, image_manifest, video_manifest))

    output_root.mkdir(parents=True, exist_ok=True)
    revision = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    provenance = {
        "source_repository": "https://github.com/matthiaskoenig/porous_media",
        "source_revision": revision,
        "source_catalog_sha256": sha256(source_root / "catalog.tsv"),
        "exported_at": datetime.now(UTC).isoformat(),
        "image_width": 2000,
        "image_render_options": sources[0][3]["configuration"]["options"],
        "video_render_options": sources[0][4]["configuration"]["options"],
        "color_ranges": sources[0][3]["configuration"]["ranges"],
        "assets": {},
    }
    with tempfile.TemporaryDirectory(
        prefix=".spt-assets-", dir=output_root.parent
    ) as tmp:
        staging = Path(tmp)
        for simulation_id, image, video, image_manifest, video_manifest in sources:
            image_out = staging / f"{simulation_id}.png"
            video_out = staging / f"{simulation_id}_h264.mp4"
            convert_image(image, image_out, width=2000)
            convert_video(video, video_out)
            provenance["assets"][simulation_id] = {
                "source_image_sha256": sha256(image),
                "source_video_sha256": sha256(video),
                "image_generation": image_manifest["generation"],
                "video_generation": video_manifest["generation"],
                "image_sha256": sha256(image_out),
                "video_sha256": sha256(video_out),
            }
        with (staging / "simulations.tsv").open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=COLUMNS, delimiter="\t", lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(simulations)
        (staging / "provenance.json").write_text(
            json.dumps(provenance, indent=2) + "\n"
        )
        for path in sorted(staging.iterdir()):
            path.replace(output_root / path.name)
    print(f"Imported {len(simulations)} images and videos into {output_root}")


def main() -> None:
    """Import a complete SPT analysis and an optional separate media export."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--media-root", type=Path)
    parser.add_argument(
        "--output-root", type=Path, default=Path(__file__).resolve().parent
    )
    args = parser.parse_args()
    import_assets(
        args.source_root.resolve(),
        (args.media_root or args.source_root).resolve(),
        args.output_root.resolve(),
    )


if __name__ == "__main__":
    main()
