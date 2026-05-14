from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.cm import get_cmap
import pandas as pd

from .plotting import _find_column, _pressure_to_hpa, _theme
from .stations import Station, station as find_station


def foehndiagramm(
    south: str | Station = "Lienz",
    north: str | Station = "Zell am See",
    history: str = "72h",
    forecast: str | None = None,
    output: str | Path | None = "outputs/foehndiagramm.png",
    mode: str = "bright",
    choose_south: int | None = 0,
    choose_north: int | None = 0,
    threshold: float = -3.0,
    strong_threshold: float = -6.0,
    title: str | None = None,
    wind_stations: list[str | Station] | tuple[str | Station, ...] | None = None,
    include_gusts: bool = True,
    show: bool = True,
):
    south_station = _station(south, choose=choose_south)
    north_station = _station(north, choose=choose_north)

    south_hist = south_station.historical(time=history, source="tawes", parameters=["PRED"])
    north_hist = north_station.historical(time=history, source="tawes", parameters=["PRED"])
    south_fc = south_station.forecast(model="nwp", max_time=forecast, parameters=["PRED"])
    north_fc = north_station.forecast(model="nwp", max_time=forecast, parameters=["PRED"])

    hist_diff = _pressure_difference(south_hist, north_hist, preferred=("PRED", "pred", "reduced_pressure", "P"))
    forecast_diff = _pressure_difference(south_fc, north_fc, preferred=("PRED", "pred", "sp", "pressure", "P"))
    forecast_diff = _offset_forecast_difference(hist_diff, forecast_diff)
    wind_data = _wind_data(wind_stations, history, forecast, include_gusts) if wind_stations else None

    fig, axes = plot_foehndiagramm(
        hist_diff,
        forecast_diff,
        south_station=south_station,
        north_station=north_station,
        mode=mode,
        threshold=threshold,
        strong_threshold=strong_threshold,
        title=title,
        wind_data=wind_data,
        include_gusts=include_gusts,
    )

    output_path = _save(fig, output)
    if not show:
        plt.close(fig)

    return {
        "south": south_station,
        "north": north_station,
        "historical": hist_diff,
        "forecast": forecast_diff,
        "wind": wind_data,
        "fig": fig,
        "axes": axes,
        "output": output_path,
    }


def plot_foehndiagramm(
    historical: pd.Series,
    forecast: pd.Series | None = None,
    south_station: Station | None = None,
    north_station: Station | None = None,
    mode: str = "bright",
    threshold: float = -3.0,
    strong_threshold: float = -6.0,
    title: str | None = None,
    wind_data: list[dict[str, Any]] | None = None,
    include_gusts: bool = True,
):
    theme = _theme(mode)
    if wind_data:
        fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, constrained_layout=True, gridspec_kw={"height_ratios": [2.2, 1]})
        ax = axes[0]
        wind_ax = axes[1]
    else:
        fig, ax = plt.subplots(figsize=(14, 6), constrained_layout=True)
        axes = [ax]
        wind_ax = None
    fig.patch.set_facecolor(theme["figure"])
    _style_axis(ax, theme)

    all_values = historical
    if forecast is not None:
        all_values = pd.concat([historical, forecast])
    y_min = min(-10, float(all_values.min(skipna=True) - 1))
    y_max = max(10, float(all_values.max(skipna=True) + 1))

    ax.axhspan(threshold, 0, color="#7ec8f5", alpha=0.45, zorder=0)
    ax.axhspan(strong_threshold, threshold, color="#7ec8f5", alpha=0.25, zorder=0)
    ax.axhline(0, color="#94a3b8", linewidth=1.0)
    ax.axhline(threshold, color="#3fa9f5", linewidth=1.6)
    ax.axhline(strong_threshold, color="#3fa9f5", linewidth=1.6)

    ax.plot(historical.index, historical, color="#111827", linewidth=2.2, label="historical")
    if forecast is not None:
        ax.plot(forecast.index, forecast, color="#111827", linewidth=2.2, linestyle="--", label="forecast")

    label = _title(south_station, north_station, title)
    ax.set_title(label, fontsize=16, fontweight="bold", color=theme["text"])
    ax.set_ylabel("hPa", color=theme["text"])
    ax.set_ylim(y_min, y_max)
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.xaxis.set_major_formatter(_GermanDayFormatter())
    ax.legend(loc="upper left", facecolor=theme["legend_face"], edgecolor=theme["legend_edge"], labelcolor=theme["text"])

    if wind_ax is not None and wind_data:
        _plot_wind_panel(wind_ax, wind_data, theme, include_gusts=include_gusts)

    x_mid = historical.index[len(historical) // 2] if len(historical) else 0.5
    ax.text(
        x_mid,
        (threshold + strong_threshold) / 2,
        "↓ NORDFÖHN ↓",
        ha="center",
        va="center",
        fontsize=18,
        fontweight="bold",
        color="#3fa9f5",
        alpha=0.85,
    )
    fig.autofmt_xdate()
    return fig, axes


class _GermanDayFormatter(mdates.DateFormatter):
    def __init__(self):
        super().__init__("%Y-%m-%d")
        self.days = ["Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So."]

    def __call__(self, x, pos=None):
        dt = mdates.num2date(x)
        return f"{self.days[dt.weekday()]}\n{dt:%d.%m.}"


def _pressure_difference(south_frame: pd.DataFrame, north_frame: pd.DataFrame, preferred: tuple[str, ...]) -> pd.Series:
    south_col = _find_column(south_frame, preferred)
    north_col = _find_column(north_frame, preferred)
    if south_col is None or north_col is None:
        raise ValueError(f"Could not find pressure columns for difference. South={south_frame.columns}, north={north_frame.columns}")

    south_pressure = _pressure_to_hpa(pd.to_numeric(south_frame[south_col], errors="coerce"))
    north_pressure = _pressure_to_hpa(pd.to_numeric(north_frame[north_col], errors="coerce"))
    aligned = pd.concat([south_pressure, north_pressure], axis=1, join="inner").dropna()
    if aligned.empty:
        raise ValueError("Pressure series do not overlap or are empty.")
    return aligned.iloc[:, 0] - aligned.iloc[:, 1]


def _wind_data(
    stations: list[str | Station] | tuple[str | Station, ...],
    history: str,
    forecast: str | None,
    include_gusts: bool,
) -> list[dict[str, Any]]:
    data = []
    params = ["FFAM", "FFX"] if include_gusts else ["FFAM"]
    for item in stations:
        selected = _station(item, choose=0)
        hist = selected.historical(time=history, source="tawes", parameters=params)
        fc = selected.forecast(model="nwp", max_time=forecast, parameters=params)
        data.append({"station": selected, "historical": hist, "forecast": fc})
    return data


def _plot_wind_panel(ax, wind_data: list[dict[str, Any]], theme: dict[str, str | float], include_gusts: bool) -> None:
    _style_axis(ax, theme)
    colors = get_cmap("tab20").colors
    for index, item in enumerate(wind_data):
        color = colors[(index * 2) % len(colors)]
        gust_color = colors[(index * 2 + 1) % len(colors)]
        name = item["station"].name
        hist_speed = _speed(item["historical"], ("FFAM", "FF", "wind_speed"))
        fc_speed = _speed(item["forecast"], ("FFAM", "FF", "wind_speed"))
        if hist_speed is not None:
            ax.plot(hist_speed.index, hist_speed, color=color, linewidth=1.8, label=f"{name} wind hist")
        if fc_speed is not None:
            ax.plot(fc_speed.index, fc_speed, color=color, linewidth=1.8, linestyle="--", label=f"{name} wind fc")

        if include_gusts:
            hist_gust = _speed(item["historical"], ("FFX", "gust"))
            fc_gust = _speed(item["forecast"], ("FFX", "gust"))
            if hist_gust is not None:
                ax.plot(hist_gust.index, hist_gust, color=gust_color, linewidth=1.2, alpha=0.75, label=f"{name} boe hist")
            if fc_gust is not None:
                ax.plot(fc_gust.index, fc_gust, color=gust_color, linewidth=1.2, alpha=0.75, linestyle="--", label=f"{name} boe fc")

    ax.set_title("Wind / Böen", loc="left", color=theme["text"], fontweight="bold")
    ax.set_ylabel("km/h", color=theme["text"])
    ax.legend(loc="upper left", ncols=2, fontsize=8, facecolor=theme["legend_face"], edgecolor=theme["legend_edge"], labelcolor=theme["text"])


def _speed(frame: pd.DataFrame, preferred: tuple[str, ...]) -> pd.Series | None:
    column = _find_column(frame, preferred)
    if column is None:
        return None
    values = pd.to_numeric(frame[column], errors="coerce")
    if values.dropna().empty:
        return None
    name = str(column).casefold()
    if "km/h" not in name and "kmh" not in name:
        values = values * 3.6
    return values


def _style_axis(ax, theme: dict[str, str | float]) -> None:
    ax.set_facecolor(theme["axes"])
    ax.grid(True, color=theme["grid"], alpha=0.6)
    for spine in ax.spines.values():
        spine.set_color(theme["spine"])
    ax.tick_params(colors=theme["muted"])


def _offset_forecast_difference(historical: pd.Series, forecast: pd.Series) -> pd.Series:
    hist = historical.dropna()
    fc = forecast.dropna()
    if hist.empty or fc.empty:
        return forecast

    nearby_hist = hist[hist.index <= fc.index[0]].tail(6)
    if nearby_hist.empty:
        nearby_hist = hist.tail(6)

    return forecast + (nearby_hist.median() - fc.iloc[0])


def _station(value: str | Station, choose: int | None) -> Station:
    if isinstance(value, Station):
        return value
    result = find_station(value, choose=choose)
    if isinstance(result, Station):
        return result
    raise ValueError(f"Multiple stations found for {value!r}. Use choose=...; matches:\n{result}")


def _title(south: Station | None, north: Station | None, title: str | None) -> str:
    if title:
        return title
    south_name = south.name if south else "south"
    north_name = north.name if north else "north"
    return f"Luftdruckdifferenz {south_name} - {north_name}"


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
