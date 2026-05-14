from __future__ import annotations

from collections.abc import Sequence

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.cm import get_cmap
from matplotlib.ticker import MaxNLocator
import pandas as pd


def plot(
    historical: pd.DataFrame,
    forecast: pd.DataFrame | None = None,
    columns: Sequence[str] | None = None,
    figsize: tuple[int, int] | None = None,
):
    selected = _select_series(historical, forecast, columns)
    if not selected:
        raise ValueError("No plottable columns found. Pass columns=[...] explicitly.")

    figsize = figsize or (14, max(3, 2.6 * len(selected)))
    fig, axes = plt.subplots(
        nrows=len(selected),
        ncols=1,
        figsize=figsize,
        sharex=True,
        constrained_layout=True,
    )

    if len(selected) == 1:
        axes = [axes]

    for ax, item in zip(axes, selected):
        label, hist_column, forecast_column = item

        if hist_column in historical:
            ax.plot(historical.index, historical[hist_column], label="historical", linewidth=1.8)

        if forecast is not None and forecast_column in forecast:
            ax.plot(forecast.index, forecast[forecast_column], label="forecast", linestyle="--", linewidth=1.8)

        ax.set_ylabel(label)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M"))
        ax.legend(loc="upper left")

    station = historical.attrs.get("station") or (forecast.attrs.get("station") if forecast is not None else None)
    if station:
        fig.suptitle(station.name)

    fig.autofmt_xdate()
    return fig, axes


def plot_meteogram(
    historical: pd.DataFrame,
    forecast: pd.DataFrame | None = None,
    station=None,
    figsize: tuple[int, int] = (14, 9),
    mode: str = "dark",
    show_data: Sequence[str] | None = None,
):
    theme = _theme(mode)
    panels = _panels(show_data)
    figsize = (figsize[0], max(2.5 * len(panels), 3.5)) if figsize == (14, 9) and len(panels) != 3 else figsize
    fig, axes = plt.subplots(
        nrows=len(panels),
        ncols=1,
        figsize=figsize,
        sharex=True,
        constrained_layout=True,
    )
    if len(panels) == 1:
        axes = [axes]
    fig.patch.set_facecolor(theme["figure"])

    for ax in axes:
        _style_meteogram_axis(ax, theme)

    plotters = {
        "precip": _plot_precipitation_panel,
        "temp": _plot_temperature_panel,
        "pressure": _plot_pressure_panel,
        "wind": _plot_wind_panel,
    }
    for ax, panel in zip(axes, panels):
        plotters[panel](ax, historical, forecast, theme)

    title_station = station or historical.attrs.get("station") or (forecast.attrs.get("station") if forecast is not None else None)
    if title_station is not None:
        title = getattr(title_station, "name", str(title_station))
        fig.suptitle(title, color=theme["text"], fontsize=15, fontweight="semibold")

    axes[-1].xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=10))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M"))
    fig.autofmt_xdate()
    return fig, axes


def _panels(show_data: Sequence[str] | None) -> list[str]:
    if show_data is None:
        return ["precip", "temp", "wind"]

    aliases = {
        "precipitation": "precip",
        "rain": "precip",
        "snow": "precip",
        "temperature": "temp",
        "dewpoint": "temp",
        "pressure": "pressure",
        "press": "pressure",
        "p": "pressure",
        "wind": "wind",
    }
    panels = []
    for item in show_data:
        key = aliases.get(str(item).casefold(), str(item).casefold())
        if key not in {"precip", "temp", "pressure", "wind"}:
            raise ValueError(f"Unknown show_data item {item!r}")
        if key not in panels:
            panels.append(key)
    return panels


def _select_series(
    historical: pd.DataFrame,
    forecast: pd.DataFrame | None,
    columns: Sequence[str] | None,
) -> list[tuple[str, str, str]]:
    if columns is not None:
        return [(column, column, column) for column in columns]

    hist_columns = [column for column in historical.columns if not str(column).endswith("_flag")]
    if forecast is None:
        return [(column, column, "") for column in hist_columns]

    forecast_columns = [column for column in forecast.columns if not str(column).endswith("_flag")]

    hist_by_key = historical.attrs.get("parameter_columns", {})
    forecast_by_key = forecast.attrs.get("parameter_columns", {})
    common_keys = [key for key in hist_by_key if key in forecast_by_key]
    if common_keys:
        return [
            (hist_by_key[key], hist_by_key[key], forecast_by_key[key])
            for key in common_keys
            if hist_by_key[key] in historical and forecast_by_key[key] in forecast
        ]

    intersection = [column for column in hist_columns if column in forecast_columns]
    if intersection:
        return [(column, column, column) for column in intersection]

    items = [(column, column, "") for column in hist_columns]
    items.extend((column, "", column) for column in forecast_columns if column not in hist_columns)
    return items


def _theme(mode: str) -> dict[str, str | float]:
    tab20 = get_cmap("tab20").colors
    if mode == "bright":
        return {
            "figure": "white",
            "axes": "white",
            "grid": "#d9dee7",
            "spine": "#b9c0cc",
            "text": "#111827",
            "muted": "#4b5563",
            "legend_face": "white",
            "legend_edge": "#cbd5e1",
            "zero": "#6b7280",
            "legend_alpha": 0.96,
            "precip": tab20[0],
            "precip_fc": tab20[1],
            "temp": tab20[2],
            "temp_fc": tab20[3],
            "dew": tab20[4],
            "dew_fc": tab20[5],
            "pressure": tab20[6],
            "pressure_fc": tab20[7],
            "wind": tab20[18],
            "wind_fc": tab20[19],
            "direction": tab20[16],
            "direction_fc": tab20[17],
        }

    if mode != "dark":
        raise ValueError("mode must be 'dark' or 'bright'")

    return {
        "figure": "#111217",
        "axes": "#181a20",
        "grid": "#3f4350",
        "spine": "#3f4350",
        "text": "#f4f4f5",
        "muted": "#d7d9df",
        "legend_face": "#181a20",
        "legend_edge": "#3f4350",
        "zero": "#e5e7eb",
        "legend_alpha": 0.9,
        "precip": "#38bdf8",
        "precip_fc": "#0ea5e9",
        "temp": "#f97316",
        "temp_fc": "#fb923c",
        "dew": "#22c55e",
        "dew_fc": "#4ade80",
        "pressure": "#a78bfa",
        "pressure_fc": "#c4b5fd",
        "wind": "#00e6c3",
        "wind_fc": "#00e6c3",
        "direction": "#facc15",
        "direction_fc": "#fde047",
    }


def _style_meteogram_axis(ax, theme: dict[str, str | float]) -> None:
    ax.set_facecolor(theme["axes"])
    ax.grid(True, color=theme["grid"], alpha=0.55, linewidth=0.8)
    ax.tick_params(colors=theme["muted"], labelsize=9)
    ax.yaxis.label.set_color(theme["text"])
    ax.title.set_color(theme["text"])
    for spine in ax.spines.values():
        spine.set_color(theme["spine"])


def _plot_precipitation_panel(ax, historical: pd.DataFrame, forecast: pd.DataFrame | None, theme: dict[str, str | float]) -> None:
    plotted = False
    plotted |= _plot_line(ax, historical, ("snow", "snowfall", "SNOW", "SNO", "SA", "HS"), "#dbeafe", "snow hist")
    plotted |= _plot_bars(
        ax,
        historical,
        ("RR_RATE", "RR", "rr", "precipitation", "rain", "RRM"),
        theme["precip"],
        "precip hist",
        alpha=0.7,
        transform=_precip_to_hourly,
    )

    if forecast is not None:
        plotted |= _plot_line(ax, forecast, ("snow", "snowfall", "SNOW", "SNO", "SA", "HS"), "#f8fafc", "snow fc", linestyle="--")
        plotted |= _plot_line(ax, forecast, ("RR_RATE", "precipitation", "RR", "rr", "rr_acc", "rain", "RRM"), theme["precip_fc"], "precip fc", linestyle="--")

    ax.set_title("Niederschlag / Schnee", loc="left", fontsize=11, color=theme["precip"])
    ax.set_ylabel("mm")
    ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
    if not plotted:
        _empty_panel(ax, "No precipitation or snow columns")
    else:
        _legend(ax, theme)


def _plot_temperature_panel(ax, historical: pd.DataFrame, forecast: pd.DataFrame | None, theme: dict[str, str | float]) -> None:
    plotted = False
    plotted |= _plot_line(ax, historical, ("TL", "T2M", "t2m", "temperature", "temp"), theme["temp"], "temp hist")
    plotted |= _plot_line(ax, historical, ("TD", "TD2M", "td2m", "dewpoint", "dew point"), theme["dew"], "dew hist")

    if forecast is not None:
        plotted |= _plot_line(ax, forecast, ("TL", "T2M", "t2m", "temperature", "temp"), theme["temp_fc"], "temp fc", linestyle="--")
        plotted |= _plot_line(ax, forecast, ("TD", "TD2M", "td2m", "dewpoint", "dew point"), theme["dew_fc"], "dew fc", linestyle="--")

    ax.axhline(0, color=theme["zero"], linewidth=0.8, alpha=0.55)
    ax.set_title("Temperatur / Taupunkt", loc="left", fontsize=11, color=theme["temp"])
    ax.set_ylabel("deg C")
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    if not plotted:
        _empty_panel(ax, "No temperature columns")
    else:
        _legend(ax, theme)


def _plot_pressure_panel(ax, historical: pd.DataFrame, forecast: pd.DataFrame | None, theme: dict[str, str | float]) -> None:
    plotted = False
    hist_column = _find_column(historical, ("P", "P0", "sp", "pressure", "luftdruck"))
    forecast_column = _find_column(forecast, ("P", "P0", "sp", "pressure", "luftdruck")) if forecast is not None else None

    hist_values = None
    if hist_column is not None:
        hist_values = _pressure_to_hpa(pd.to_numeric(historical[hist_column], errors="coerce"))
        ax.plot(historical.index, hist_values, color=theme["pressure"], label="pressure hist", linewidth=1.8)
        plotted = True

    if forecast is not None and forecast_column is not None:
        forecast_values = _pressure_to_hpa(pd.to_numeric(forecast[forecast_column], errors="coerce"))
        if hist_values is not None and hist_values.dropna().size and forecast_values.dropna().size:
            offset = _pressure_offset(historical.index, hist_values, forecast.index, forecast_values)
            forecast_values = forecast_values + offset
        ax.plot(forecast.index, forecast_values, color=theme["pressure_fc"], label="pressure fc offset", linewidth=1.8, linestyle="--")
        plotted = True

    ax.set_title("Luftdruck", loc="left", fontsize=11, color=theme["pressure"])
    ax.set_ylabel("hPa")
    ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
    if not plotted:
        _empty_panel(ax, "No pressure columns")
    else:
        _legend(ax, theme)


def _plot_wind_panel(ax, historical: pd.DataFrame, forecast: pd.DataFrame | None, theme: dict[str, str | float]) -> None:
    plotted = False
    plotted |= _plot_line(ax, historical, ("FFAM", "FF", "ff", "wind_speed", "wind speed"), theme["wind"], "wind hist", transform=_wind_to_kmh)
    if forecast is not None:
        plotted |= _plot_line(ax, forecast, ("FFAM", "FF", "ff", "wind_speed", "wind speed"), theme["wind_fc"], "wind fc", linestyle="--", transform=_wind_to_kmh)

    direction_ax = None
    if _has_any_column(historical, ("DD", "dd", "wind_direction", "wind direction")) or (
        forecast is not None and _has_any_column(forecast, ("DD", "dd", "wind_direction", "wind direction"))
    ):
        direction_ax = ax.twinx()
        _style_meteogram_axis(direction_ax, theme)
        direction_ax.grid(False)
        plotted |= _plot_line(direction_ax, historical, ("DD", "dd", "wind_direction", "wind direction"), theme["direction"], "dir hist", linewidth=1.1)
        if forecast is not None:
            plotted |= _plot_line(
                direction_ax,
                forecast,
                ("DD", "dd", "wind_direction", "wind direction"),
                theme["direction_fc"],
                "dir fc",
                linestyle="--",
                linewidth=1.1,
            )
        direction_ax.set_ylim(0, 360)
        direction_ax.set_yticks([0, 45, 90, 135, 180, 225, 270, 315, 360])
        direction_ax.set_yticklabels(["N", "NO", "O", "SO", "S", "SW", "W", "NW", "N"])
        direction_ax.set_ylabel("Richtung")

    ax.set_title("Wind-Geschwindigkeit / Wind-Richtung", loc="left", fontsize=11, color=theme["wind"])
    ax.set_ylabel("km/h")
    ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
    if not plotted:
        _empty_panel(ax, "No wind columns")
        return

    handles, labels = ax.get_legend_handles_labels()
    if direction_ax is not None:
        dir_handles, dir_labels = direction_ax.get_legend_handles_labels()
        handles.extend(dir_handles)
        labels.extend(dir_labels)
    _legend(ax, theme, handles=handles, labels=labels)


def _legend(ax, theme: dict[str, str | float], handles=None, labels=None) -> None:
    kwargs = {
        "loc": "upper left",
        "facecolor": theme["legend_face"],
        "edgecolor": theme["legend_edge"],
        "labelcolor": theme["text"],
        "fontsize": 8,
        "framealpha": theme["legend_alpha"],
    }
    if handles is not None and labels is not None:
        ax.legend(handles, labels, **kwargs)
    else:
        ax.legend(**kwargs)


def _plot_line(ax, frame: pd.DataFrame, keys: Sequence[str], color: str, label: str, transform=None, **kwargs) -> bool:
    column = _find_column(frame, keys)
    if column is None:
        return False

    values = pd.to_numeric(frame[column], errors="coerce")
    if transform is not None:
        values = transform(values)

    ax.plot(frame.index, values, color=color, label=label, linewidth=kwargs.pop("linewidth", 1.8), **kwargs)
    return True


def _plot_bars(ax, frame: pd.DataFrame, keys: Sequence[str], color: str, label: str, alpha: float = 0.72, transform=None) -> bool:
    column = _find_column(frame, keys)
    if column is None:
        return False

    values = pd.to_numeric(frame[column], errors="coerce")
    index = frame.index
    if transform is not None:
        index, values = transform(index, values)

    if values.dropna().empty:
        return False

    width = _bar_width(index)
    ax.bar(index, values, width=width, color=color, alpha=alpha, label=label, align="center")
    return True


def _find_column(frame: pd.DataFrame, keys: Sequence[str]) -> str | None:
    parameter_columns = frame.attrs.get("parameter_columns", {})
    for key in keys:
        column = parameter_columns.get(key)
        if column in frame:
            return column

    column_by_casefold = {str(column).casefold(): column for column in frame.columns}
    for key in keys:
        column = column_by_casefold.get(str(key).casefold())
        if column is not None:
            return column

    for key in keys:
        needle = str(key).casefold()
        for column in frame.columns:
            if needle in str(column).casefold():
                return column

    return None


def _has_any_column(frame: pd.DataFrame, keys: Sequence[str]) -> bool:
    return _find_column(frame, keys) is not None


def _bar_width(index: pd.Index) -> float:
    if len(index) < 2:
        return 0.03

    timestamps = mdates.date2num(pd.to_datetime(index).to_pydatetime())
    intervals = pd.Series(timestamps).diff().dropna()
    if intervals.empty:
        return 0.03
    return max(float(intervals.median()) * 0.8, 0.005)


def _empty_panel(ax, message: str) -> None:
    color = ax.yaxis.label.get_color()
    ax.text(
        0.5,
        0.5,
        message,
        transform=ax.transAxes,
        ha="center",
        va="center",
        color=color,
        fontsize=10,
    )


def _wind_to_kmh(series: pd.Series) -> pd.Series:
    name = str(series.name).casefold()
    if "km/h" in name or "kmh" in name:
        return series
    return series * 3.6


def _precip_to_hourly(index: pd.Index, values: pd.Series) -> tuple[pd.Index, pd.Series]:
    if values.dropna().empty:
        return index, values

    series = pd.Series(values.to_numpy(), index=index)
    if len(series.index) < 2:
        return index, values

    median_minutes = series.index.to_series().diff().dropna().dt.total_seconds().median() / 60
    if median_minutes >= 45:
        return index, values

    hourly = series.resample("1h").sum(min_count=1)
    return hourly.index, hourly


def _pressure_to_hpa(series: pd.Series) -> pd.Series:
    name = str(series.name).casefold()
    if "pa" in name and "hpa" not in name:
        return series / 100
    if series.mean(skipna=True) > 2000:
        return series / 100
    return series


def _pressure_offset(
    hist_index: pd.Index,
    hist_values: pd.Series,
    forecast_index: pd.Index,
    forecast_values: pd.Series,
) -> float:
    hist = pd.Series(hist_values.to_numpy(), index=hist_index).dropna()
    fc = pd.Series(forecast_values.to_numpy(), index=forecast_index).dropna()
    if hist.empty or fc.empty:
        return 0.0

    first_fc_time = fc.index[0]
    nearby_hist = hist[hist.index <= first_fc_time].tail(6)
    if nearby_hist.empty:
        nearby_hist = hist.tail(6)

    return float(nearby_hist.median() - fc.iloc[0])
