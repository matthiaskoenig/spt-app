"""Check the user-visible selection and local media for every simulation."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    "constant",
    "linear increase",
    "sharp pericentral",
    "linear decrease",
    "sharp periportal",
    "random",
)


def test_default_selection() -> None:
    """The initial view shows linear increase at substrate flow three."""
    app = AppTest.from_file(str(ROOT / "spt_app.py")).run()
    assert not app.exception
    assert app.selectbox[0].value == "linear increase"
    assert app.select_slider[0].value == 3
    assert app.select_slider[0].options == [str(flow) for flow in range(8)]
    assert "sim012" in app.markdown[0].value


@pytest.mark.parametrize("pattern_key,pattern", list(enumerate(PATTERNS)))
def test_every_simulation_selection(pattern_key: int, pattern: str) -> None:
    """All six patterns expose eight distinct, correctly paired media sets."""
    app = AppTest.from_file(str(ROOT / "spt_app.py")).run()
    app.selectbox[0].select(pattern).run()
    videos = set()
    images = set()
    for flow in range(8):
        app.select_slider[0].set_value(flow).run()
        assert not app.exception
        assert not app.error
        simulation_id = f"sim{pattern_key * 8 + flow + 1:03}"
        assert f"`{simulation_id}`" in app.markdown[0].value
        video = app.get("video")[0].proto
        assert video.url.startswith("/mock/media/")
        assert video.url.endswith(".mp4")
        assert video.autoplay and video.loop and video.muted
        assert simulation_id in video.alt
        videos.add(video.url)
        image = app.get("image")[0].proto.imgs[0]
        assert image.url.startswith("/mock/media/")
        images.add(image.url)
    assert len(videos) == len(images) == 8
