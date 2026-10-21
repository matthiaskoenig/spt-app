"""Bundle convergence media and quantitative results from porous_media."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from data.convert_videos_images import (
    artifact,
    convert_image,
    generation_artifact,
    sha256,
)

MESH_IDS = ("50000", "37250", "25000", "18750", "12500", "09375", "06250")
RUN_IDS = tuple(f"convergence_{mesh}" for mesh in MESH_IDS)
STUDY = "convergence_lobulus"
TABLES = (
    "native-timecourses.tsv",
    "matched-timecourses.tsv",
    "spatial-profiles.tsv",
    "convergence-means.tsv",
    "convergence-profiles.tsv",
)
FIGURES = (
    "timecourses.png",
    "timecourses-symlog.png",
    "endpoints.png",
    "endpoints-symlog.png",
    "convergence-errors.png",
    "convergence-errors-symlog.png",
    "initial-properties.png",
    *(
        f"spatial-{index:02}{suffix}.png"
        for index in range(3)
        for suffix in ("", "-symlog")
    ),
)


def read_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read a TSV without changing numeric precision or missing entries."""
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader.fieldnames or ()), list(reader)


def write_table(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    """Write a portable TSV with consistent line endings."""
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def load_runs(source_root: Path) -> list[dict[str, str]]:
    """Keep all seven resolutions, including readable truncated histories."""
    _, catalogue = read_table(source_root / "catalog.tsv")
    records = [row for row in catalogue if row["study"] == "convergence_sixth"]
    if sorted(row["run_id"] for row in records) != sorted(RUN_IDS):
        raise ValueError("The source catalogue must contain all seven convergence runs")
    runs = []
    for run_id in RUN_IDS:
        source = next(row for row in records if row["run_id"] == run_id)
        if source["status"] != "available" or source["complete"] not in {
            "True",
            "False",
        }:
            raise ValueError(f"Convergence history is unavailable: {run_id}")
        manifest = source_root / STUDY / "runs" / run_id / "manifest.json"
        full = json.loads(manifest.read_text())["catalog"]
        row = {"run_id": run_id}
        for name in ("num_cells", "num_points", "num_steps"):
            row[name] = str(int(full[name]))
        for name in ("tstart_s", "tend_s", "expected_duration_s", "complete"):
            row[name] = source[name]
        if float(row["tend_s"]) != float(full["tend_s"]):
            raise ValueError(
                f"Full-lobule and source history endpoints differ: {run_id}"
            )
        runs.append(row)
    return runs


def import_convergence(source_root: Path, media_root: Path, output_root: Path) -> None:
    """Validate and prepare the complete convergence study before publication."""
    runs = load_runs(source_root)
    counts = {row["run_id"]: row["num_cells"] for row in runs}
    start = max(float(row["tstart_s"]) for row in runs)
    end = min(float(row["tend_s"]) for row in runs)
    analysis = source_root / "analysis" / STUDY
    sources: dict[str, Path] = {}
    generations: dict[str, str] = {}
    for name in (*FIGURES, *TABLES, "analysis.nc"):
        sources[name], manifest = generation_artifact(analysis, name)
        generations[name] = manifest["generation"]
    sources["meshes.png"], overview = generation_artifact(
        source_root / "overviews" / STUDY, "meshes.png"
    )
    generations["meshes.png"] = overview["generation"]
    _, matched = read_table(sources["matched-timecourses.tsv"])
    if {row["run"] for row in matched} != set(RUN_IDS):
        raise ValueError("The quantitative analysis must include all seven meshes")
    times = sorted({float(row["time"]) for row in matched})
    if not times or times[0] != start or times[-1] != end:
        raise ValueError("The quantitative comparison window differs from the cohort")
    for row in matched:
        if int(row["num_cells"]) != int(counts[row["run"]]):
            raise ValueError(
                f"Analysis cell count differs from the geometry: {row['run']}"
            )
    mean_columns, differences = read_table(sources["convergence-means.tsv"])
    reference = max(counts, key=lambda run_id: int(counts[run_id]))
    if {row["reference_run"] for row in differences} != {reference}:
        raise ValueError("Differences must use the finest available mesh as reference")
    for row in differences:
        row["num_cells"] = counts[row["run"]]
    _, profiles = read_table(sources["spatial-profiles.tsv"])
    spatial_times = sorted({float(row["time"]) for row in profiles})
    comparison = {
        "start_s": start,
        "end_s": end,
        "spatial_times_s": spatial_times,
        "reference_run": reference,
        "reference_num_cells": int(counts[reference]),
        "necrosis_table_unit": "fraction",
        "necrosis_figure_unit": "percent",
    }
    for run in runs:
        run_id = run["run_id"]
        _, current = artifact(source_root, run_id, "timecourse.png", study=STUDY)
        for filename, destination in (
            ("timecourse.png", f"{run_id}.png"),
            ("timecourse.mp4", f"{run_id}_h264.mp4"),
            ("mesh.png", f"{run_id}_mesh.png"),
        ):
            sources[destination], media = artifact(
                media_root, run_id, filename, study=STUDY
            )
            if media["configuration"]["source"] != current["configuration"]["source"]:
                raise ValueError(
                    f"Media uses an outdated convergence history: {run_id}"
                )
            times = media["configuration"]["options"]["video_times"]
            if not times or times[0] != start or times[-1] != end:
                raise ValueError(f"Media does not use the common interval: {run_id}")
            generations[destination] = media["generation"]
    repository = Path(
        subprocess.run(
            ["git", "-C", str(source_root), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    revision = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(repository), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    provenance = {
        "source_repository": "https://github.com/matthiaskoenig/porous_media",
        "source_revision": revision,
        "source_worktree_dirty": bool(dirty),
        "renderer_source_hashes": {
            name: sha256(repository / "research" / "spt" / name)
            for name in (
                "plot_render.py",
                "plot_data.py",
                "plot_mesh.py",
                "plot_view.py",
                "fields.py",
            )
            if (repository / "research" / "spt" / name).is_file()
        },
        "source_catalog_sha256": sha256(source_root / "catalog.tsv"),
        "exported_at": datetime.now(UTC).isoformat(),
        "comparison": comparison,
        "table_transformations": {
            "convergence-means.tsv": (
                "num_cells joined from active full-lobule run metadata; "
                "difference values and missing entries preserved"
            )
        },
        "files": {},
    }
    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".convergence-", dir=output_root.parent
    ) as tmp:
        staging = Path(tmp)
        for name, source in sources.items():
            destination = staging / name
            if name.endswith(".png") and not name.endswith("_mesh.png"):
                convert_image(source, destination, width=2000)
            else:
                shutil.copyfile(source, destination)
            if name == "convergence-means.tsv":
                write_table(destination, mean_columns, differences)
            provenance["files"][name] = {
                "source_sha256": sha256(source),
                "sha256": sha256(destination),
                "source_generation": generations[name],
            }
        write_table(staging / "convergence.tsv", list(runs[0]), runs)
        (staging / "study.json").write_text(json.dumps(comparison, indent=2) + "\n")
        for name in ("convergence.tsv", "study.json"):
            provenance["files"][name] = {"sha256": sha256(staging / name)}
        (staging / "provenance.json").write_text(
            json.dumps(provenance, indent=2) + "\n"
        )
        output_root.mkdir(parents=True, exist_ok=True)
        for path in sorted(staging.iterdir()):
            path.replace(output_root / path.name)
    print(
        f"Imported seven convergence meshes and quantitative results into {output_root}"
    )


def main() -> None:
    """Import current convergence results with a separate optional video export."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--media-root", type=Path)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parent / "convergence",
    )
    args = parser.parse_args()
    import_convergence(
        args.source_root.resolve(),
        (args.media_root or args.source_root).resolve(),
        args.output_root.resolve(),
    )


if __name__ == "__main__":
    main()
