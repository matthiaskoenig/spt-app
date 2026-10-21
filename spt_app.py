"""Explore the published SPT liver model simulations."""

from pathlib import Path

import pandas as pd
import streamlit as st

DATA_PATH = Path(__file__).resolve().parent / "data"


@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    """Load simulation conditions from the bundled analysis catalogue."""
    return pd.read_csv(path, sep="\t")


def main() -> None:
    """Render the selected simulation using its bundled image and video."""
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
    simulations = load_data(DATA_PATH / "simulations.tsv")

    st.sidebar.title("SPT model simulations")
    patterns = simulations["pattern_name"].drop_duplicates().tolist()
    selected_pattern = st.sidebar.selectbox(
        "Select zonation pattern",
        options=patterns,
        index=patterns.index("linear increase"),
    )
    pattern_runs = simulations[simulations["pattern_name"] == selected_pattern]
    flows = sorted(int(flow) for flow in pattern_runs["boundary_flow_key"].unique())
    selected_flow = st.sidebar.select_slider(
        "Select substrate flow",
        options=flows,
        value=3 if 3 in flows else flows[0],
    )
    row = pattern_runs[pattern_runs["boundary_flow_key"] == selected_flow].iloc[0]
    simulation_id = str(row["sim_key"])

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

    st.markdown(
        f"**simulation**: `{simulation_id}`, **pattern**: `{selected_pattern}`, "
        f"**substrate flow**: `Sv{selected_flow}`"
    )
    video_path = DATA_PATH / f"{simulation_id}_h264.mp4"
    image_path = DATA_PATH / f"{simulation_id}.png"
    for path in (video_path, image_path):
        if not path.is_file():
            st.error(f"Simulation asset is missing: {path.name}")
            st.stop()

    st.video(
        str(video_path),
        autoplay=True,
        loop=True,
        muted=True,
        alt=f"{simulation_id}: {selected_pattern}, substrate flow Sv{selected_flow}",
    )
    st.divider()
    st.image(
        str(image_path),
        width="stretch",
        alt=f"Time-course snapshots for {simulation_id}",
    )


if __name__ == "__main__":
    main()
