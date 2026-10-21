![spt-app logo](https://github.com/matthiaskoenig/spt-app/raw/main/docs/images/spt-app.png)


# spt-app: web application of SPT model

This project provides the visualization of the simulation results at [https://sptmodel.streamlit.app](https://sptmodel.streamlit.app).

Simulation of zonation-function relationships in the liver using coupled multiscale models: Application to drug-induced liver injury
Steffen Gerhäusser, Lena Lambers, Luis Mandl, Julian Franquinet, Tim Ricken, Matthias König
bioRxiv 2024.03.26.586870; doi: [10.1101/2024.03.26.586870](https://doi.org/10.1101/2024.03.26.586870)


## Run app
Install [uv](https://docs.astral.sh/uv/getting-started/installation/) 0.13.4 or
newer. The app uses Python 3.14 and the committed dependency lockfile.

```bash
uv sync --locked --no-dev
uv run --no-sync streamlit run spt_app.py
```

All 48 simulation images and videos are bundled with the app. Select one of six
zonation patterns and substrate flows 0 through 7. Media is served by the app,
so a local checkout displays its own simulation results.

See [development and data updates](docs/development.md) for checks and refreshing
the bundled media from the porous_media SPT analysis.

## License
- Source Code: [MIT](https://opensource.org/license/MIT)
- Documentation: [CC BY-SA 4.0](http://creativecommons.org/licenses/by-sa/4.0/)

## Funding
Matthias König is supported and by the German Research Foundation (DFG) within the Research Unit Programme FOR 5151
"QuaLiPerF (Quantifying Liver Perfusion-Function Relationship in Complex Resection -
A Systems Medicine Approach)" by grant number 436883643 and by grant number
465194077 (Priority Programme SPP 2311, Subproject SimLivA).

© 2024-2026 Matthias König
