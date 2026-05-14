from __future__ import annotations

from pathlib import Path
from typing import Any

from .plotting import plot_meteogram
from .stations import Station, station as find_station


METEOGRAM_PARAMETERS = ["TL", "RF", "RR", "FFAM", "DD", "P"]


def meteogram(
    station: str | Station = "Lienz",
    history: str = "12h",
    forecast: str | None = None,
    mode: str = "bright",
    output: str | Path | None = "outputs/lienz_meteogram.png",
    forecast_model: str = "nwp",
    show_data: list[str] | tuple[str, ...] | None = None,
    choose: int | None = 0,
    show: bool = True,
    **plot_kwargs: Any,
):
    selected_station = _station(station, choose=choose)

    hist = selected_station.historical(
        time=history,
        resolution="10min",
        source="tawes",
        parameters=METEOGRAM_PARAMETERS,
    )

    fc = selected_station.forecast(
        model=forecast_model,
        max_time=forecast,
        parameters=METEOGRAM_PARAMETERS,
        forecast_offset=0,
    )

    fig, axes = plot_meteogram(hist, fc, station=selected_station, mode=mode, show_data=show_data, **plot_kwargs)

    output_path = _save(fig, output)
    if not show:
        import matplotlib.pyplot as plt

        plt.close(fig)

    return {
        "station": selected_station,
        "historical": hist,
        "forecast": fc,
        "fig": fig,
        "axes": axes,
        "output": output_path,
    }


def _station(value: str | Station, choose: int | None) -> Station:
    if isinstance(value, Station):
        return value

    result = find_station(value, choose=choose)
    if isinstance(result, Station):
        return result

    raise ValueError(f"Multiple stations found for {value!r}. Use choose=...; matches:\n{result}")


def _save(fig, output: str | Path | None) -> Path | None:
    if output is None:
        return None

    path = Path(output)
    if not path.is_absolute():
        path = Path.cwd() / path
        if path.parent.name == "outputs" and path.parent.parent.name == "notebooks":
            path = path.parent.parent.parent / "outputs" / path.name

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
    return path
