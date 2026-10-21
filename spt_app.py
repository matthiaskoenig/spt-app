"""Explore SPT liver simulations and mesh convergence results."""

import json
import math
from pathlib import Path
from typing import TypedDict

import pandas as pd
import streamlit as st

DATA_PATH = Path(__file__).resolve().parent / "data"
CONVERGENCE_PATH = DATA_PATH / "convergence"
FIELD_LABELS = {
    "rr_(S_ext)": "Substrate [mM]",
    "rr_(P_ext)": "Product [mM]",
    "rr_protein": "Protein [-]",
    "rr_(T)": "Toxic compound [mM]",
    "rr_necrosis": "Necrosis [%]",
}


class Comparison(TypedDict):
    """Describe the common analysis window and finest available reference."""

    start_s: float
    end_s: float
    spatial_times_s: list[float]
    reference_run: str
    reference_num_cells: int


@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    """Load a bundled study catalogue or numerical result table."""
    return pd.read_csv(path, sep="\t")


@st.cache_data
def load_comparison(path: Path) -> Comparison:
    """Load the comparison settings exported with the study results."""
    return json.loads(path.read_text())


def render_media(directory: Path, run_id: str, description: str) -> None:
    """Render a matching local video and time-course figure."""
    video_path = directory / f"{run_id}_h264.mp4"
    image_path = directory / f"{run_id}.png"
    for path in (video_path, image_path):
        if not path.is_file():
            st.error(f"Result asset is missing: {path.name}")
            st.stop()
    st.video(str(video_path), autoplay=True, loop=True, muted=True, alt=description)
    st.divider()
    st.image(
        str(image_path), width="stretch", alt=f"Time-course snapshots for {run_id}"
    )


def render_simulations() -> None:
    """Select a zonation pattern and substrate flow from the simulation cohort."""
    simulations = load_data(DATA_PATH / "simulations.tsv")
    patterns = simulations["pattern_name"].drop_duplicates().tolist()
    selected_pattern = st.sidebar.selectbox(
        "Select zonation pattern",
        options=patterns,
        index=patterns.index("linear increase"),
        key="simulation_pattern",
    )
    pattern_runs = simulations[simulations["pattern_name"] == selected_pattern]
    flows = sorted(int(flow) for flow in pattern_runs["boundary_flow_key"].unique())
    selected_flow = st.sidebar.select_slider(
        "Select substrate flow",
        options=flows,
        value=3 if 3 in flows else flows[0],
        key="simulation_flow",
    )
    row = pattern_runs[pattern_runs["boundary_flow_key"] == selected_flow].iloc[0]
    simulation_id = str(row["sim_key"])
    st.markdown(
        f"**simulation**: `{simulation_id}`, **pattern**: `{selected_pattern}`, "
        f"**substrate flow**: `Sv{selected_flow}`"
    )
    render_media(
        DATA_PATH,
        simulation_id,
        f"{simulation_id}: {selected_pattern}, substrate flow Sv{selected_flow}",
    )


def result_image(filename: str, description: str) -> None:
    """Show a bundled comparison figure with an accessible description."""
    st.image(str(CONVERGENCE_PATH / filename), width="stretch", alt=description)


def download_result(filename: str, label: str) -> None:
    """Offer the actual exported data, preserving precision and missing values."""
    st.download_button(
        label,
        data=(CONVERGENCE_PATH / filename).read_bytes(),
        file_name=filename,
        mime="application/octet-stream"
        if filename.endswith(".nc")
        else "text/tab-separated-values",
        on_click="ignore",
    )


def render_native_timecourses(scale: str) -> None:
    """Plot every native output through each mesh's actual simulation endpoint."""
    field = st.selectbox(
        "Readout",
        options=list(FIELD_LABELS),
        format_func=FIELD_LABELS.__getitem__,
        key="convergence_field",
    )
    native = load_data(CONVERGENCE_PATH / "native-timecourses.tsv")
    mesh_order = (
        load_data(CONVERGENCE_PATH / "convergence.tsv")["run_id"]
        .str.removeprefix("convergence_")
        .tolist()
    )
    curves = pd.DataFrame(
        {
            "time_h": native["time"] / 3600,
            "mesh": native["run"].str.removeprefix("convergence_"),
            "value": native[f"{field}_mean"] * (100 if field == "rr_necrosis" else 1),
        }
    )
    y = {
        "field": "value",
        "type": "quantitative",
        "title": FIELD_LABELS[field],
        "scale": {"type": "linear"},
    }
    if scale == "Symlog" and field != "rr_necrosis":
        extent = float(curves["value"].abs().max())
        threshold = extent * 1e-6 if extent > 0 else 1e-6
        first = math.ceil(math.log10(threshold))
        last = math.floor(math.log10(extent)) if extent > 0 else 0
        y["scale"] = {"type": "symlog", "constant": threshold}
        y["axis"] = {
            "values": [0.0, *(10.0**power for power in range(first, last + 1))],
            "format": "~g",
        }
    spec = {
        "mark": {"type": "line", "clip": True},
        "encoding": {
            "x": {"field": "time_h", "type": "quantitative", "title": "Time [h]"},
            "y": y,
            "color": {
                "field": "mesh",
                "type": "nominal",
                "title": "Mesh",
                "sort": mesh_order,
                "scale": {"scheme": "viridis", "domain": mesh_order},
            },
            "tooltip": [
                {"field": "mesh", "type": "nominal", "title": "Mesh"},
                {"field": "time_h", "type": "quantitative", "title": "Time [h]"},
                {
                    "field": "value",
                    "type": "quantitative",
                    "title": FIELD_LABELS[field],
                },
            ],
        },
        "params": [{"name": "zoom", "select": "interval", "bind": "scales"}],
    }
    st.vega_lite_chart(
        curves,
        spec=spec,
        width="stretch",
        height=350,
        alt="Native time courses for all seven meshes through their actual endpoints",
    )
    st.caption(
        "Cell-volume-weighted means at every native output. Curves stop at each "
        "history's actual endpoint. Drag to zoom and double-click to reset."
    )
    download_result("native-timecourses.tsv", "Download native time courses")


def render_convergence() -> None:
    """Explore all mesh resolutions, shared comparisons, and native histories."""
    runs = load_data(CONVERGENCE_PATH / "convergence.tsv")
    comparison = load_comparison(CONVERGENCE_PATH / "study.json")
    run_ids = runs["run_id"].tolist()
    counts = runs.set_index("run_id")["num_cells"].to_dict()
    selected_run = st.sidebar.selectbox(
        "Select mesh",
        options=run_ids,
        index=run_ids.index("convergence_12500"),
        format_func=lambda run: (
            f"{run.removeprefix('convergence_')} ({counts[run]:,} cells)"
        ),
        help="Mesh labels are source identifiers. Cell counts refer to full lobules.",
        key="convergence_run",
    )
    scale = st.sidebar.radio(
        "Comparison plot scale",
        ["Linear", "Symlog"],
        index=1,
        horizontal=True,
        key="convergence_scale",
        help="Symlog exposes small values alongside outliers. "
        "Necrosis remains a linear percentage.",
    )
    suffix = "-symlog" if scale == "Symlog" else ""
    row = runs[runs["run_id"] == selected_run].iloc[0]
    st.title("Convergence study")
    st.markdown(f"**mesh**: `{selected_run.removeprefix('convergence_')}`")
    cells, outputs, duration = st.columns(3)
    cells.metric("Lobule cells", f"{int(row['num_cells']):,}")
    outputs.metric("Native outputs", f"{int(row['num_steps']):,}")
    duration.metric("Available history", f"{float(row['tend_s']) / 3600:.2f} h")
    st.caption(
        f"Shared comparison window: {comparison['start_s']:g} to "
        f"{comparison['end_s']:,.0f} s ({comparison['end_s'] / 3600:.4f} h). "
        "Comparison figures and mesh videos use this window."
    )
    if not bool(row["complete"]):
        st.warning(
            f"This source history ends at {float(row['tend_s']):,.1f} s "
            f"({float(row['tend_s']) / 3600:.2f} h), before the expected "
            f"{float(row['expected_duration_s']):,.0f} s (24 h)."
        )
    selected, study, spatial, differences = st.tabs(
        [
            "Selected mesh",
            "Study comparison",
            "Spatial profiles",
            "Differences",
        ]
    )
    with selected:
        render_media(CONVERGENCE_PATH, selected_run, f"Time course for {selected_run}")
        with st.expander("Mesh geometry"):
            st.image(
                str(CONVERGENCE_PATH / f"{selected_run}_mesh.png"),
                alt=f"Mesh geometry for {selected_run}",
                width="content",
            )
        with st.expander("All seven mesh resolutions"):
            result_image("meshes.png", "Comparison of all seven mesh geometries")
    with study:
        st.caption(
            "The coarsest mesh (50000) has large substrate and product values in "
            "the source results. Both scales retain all seven meshes."
        )
        st.subheader("Native time courses")
        render_native_timecourses(scale)
        st.subheader("Matched time courses")
        result_image(
            f"timecourses{suffix}.png", "Matched time courses for all seven meshes"
        )
        download_result("matched-timecourses.tsv", "Download matched time courses")
        st.subheader("Mesh resolution at 1.5 h")
        result_image(
            f"endpoints{suffix}.png", "Mesh cell counts and weighted means at 1.5 h"
        )
        with st.expander("Initial mesh properties"):
            result_image(
                "initial-properties.png", "Properties at the first native output"
            )
    with spatial:
        times = comparison["spatial_times_s"]
        selected_time = st.select_slider(
            "Comparison time",
            options=times,
            value=times[1],
            format_func=lambda time: f"{time / 3600:g} h",
            key="convergence_time",
        )
        index = times.index(selected_time)
        result_image(
            f"spatial-{index:02}{suffix}.png",
            f"Spatial profiles at {selected_time:g} s",
        )
        st.caption("Position runs from periportal (PP, 0) to perivenous (PV, 1).")
        download_result(
            "spatial-profiles.tsv", "Download volume-weighted spatial profiles"
        )
    with differences:
        st.caption(
            f"Reference: finest available mesh "
            f"{comparison['reference_run'].removeprefix('convergence_')} "
            f"({comparison['reference_num_cells']:,} lobule cells). "
            "These differences compare available meshes; "
            "no continuum solution is assumed."
        )
        result_image(
            f"convergence-errors{suffix}.png",
            "Differences from the finest available mesh",
        )
        st.caption(
            "Absolute differences of weighted means and reference-volume-weighted "
            f"spatial RMSE at {comparison['end_s']:,.0f} s. Relative differences "
            "remain missing when the reference mean is zero."
        )
        download_result("convergence-means.tsv", "Download mean differences")
        download_result("convergence-profiles.tsv", "Download spatial differences")
        download_result("analysis.nc", "Download complete matched analysis (NetCDF)")
    st.caption(
        "Quantitative plots display necrosis in percent; "
        "mesh maps and data tables retain fractions."
    )
    with st.expander("Mesh catalogue and source completion"):
        st.dataframe(runs, hide_index=True)
        download_result("convergence.tsv", "Download mesh catalogue")


def render_references() -> None:
    """Display the study and model citations in the sidebar."""
    st.sidebar.header("References")
    st.sidebar.markdown(
        "**Simulation of zonation-function relationships in the liver using coupled "
        "multiscale models: Application to drug-induced liver injury**.\n\n"
        "Steffen Gerhäusser, Lena Lambers, Luis Mandl, Julian Franquinet, "
        "Tim Ricken, Matthias König.\n\n"
        "bioRxiv 2024.03.26.586870; "
        "doi: https://doi.org/10.1101/2024.03.26.586870"
    )
    st.sidebar.markdown(
        "**SPT model (0.5.4)**.\n\nKönig, M. (2024).\n\n"
        "Zenodo. https://doi.org/10.5281/zenodo.10853538"
    )


def main() -> None:
    """Select the simulation or convergence study and render its results."""
    st.set_page_config(
        page_title="SPT app",
        page_icon="🧊",
        layout="wide",
        initial_sidebar_state="auto",
        menu_items={
            "Get help": "mailto:konigmatt@googlemail.com",
            "Report a bug": "https://github.com/matthiaskoenig/spt-app/issues/new",
            "About": "SPT web application.",
        },
    )
    st.sidebar.title("SPT model studies")
    study = st.sidebar.radio(
        "Select study", ["Simulations", "Convergence study"], key="study"
    )
    if study == "Convergence study":
        render_convergence()
    else:
        render_simulations()
    render_references()


if __name__ == "__main__":
    main()
