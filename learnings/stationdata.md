# GeoSphere Stationsdaten API

## Ueberblick

Die Gruppe `Stationsdaten` enthaelt Punktmessungen der GeoSphere-Austria-Messstationen. Fuer flexible Projekte sind vor allem die geprueften `klima-v2-*` Datensaetze interessant:

| Aufloesung | Datensatz | Resource ID | API-Endpunkt |
| --- | --- | --- | --- |
| 10 Minuten | Messstationen Zehnminutendaten v2 | `klima-v2-10min` | `/station/historical/klima-v2-10min` |
| Stunde | Messstationen Stundendaten v2 | `klima-v2-1h` | `/station/historical/klima-v2-1h` |
| Tag | Messstationen Tagesdaten v2 | `klima-v2-1d` | `/station/historical/klima-v2-1d` |

Die Syntax ist fuer diese drei Datensaetze praktisch gleich: `type=station`, `mode=historical`, `station_ids`, `parameters`, `start`, `end`. Wechseln muss man in erster Linie die `resource_id`.

Quelle: https://data.hub.geosphere.at/group/stationsdaten

## API-Struktur

Die Dataset-API folgt diesem Muster:

```text
https://dataset.api.hub.geosphere.at/v1/<type>/<mode>/<resource_id>
```

Fuer Stationsdaten ist der `type` immer `station`. Historische Daten verwenden `mode=historical`.

```python
BASE = "https://dataset.api.hub.geosphere.at/v1/station/historical"

ENDPOINTS = {
    "10min": f"{BASE}/klima-v2-10min",
    "1h": f"{BASE}/klima-v2-1h",
    "1d": f"{BASE}/klima-v2-1d",
}
```

Quellen:

- https://dataset.api.hub.geosphere.at/v1/docs/getting-started.html
- https://dataset.api.hub.geosphere.at/v1/docs/user-guide/type.html
- https://dataset.api.hub.geosphere.at/v1/docs/user-guide/mode.html

## Gemeinsame Query-Parameter

Typische Parameter fuer `station/historical/...`:

- `station_ids`: eine oder mehrere Stations-IDs, z. B. `11348` oder `11348,11035`
- `parameters`: ein oder mehrere Parameterkuerzel, z. B. `TL,RF,RR`
- `start`: Startzeitpunkt, Format `YYYY-MM-DDThh:mm`; bei Tagesdaten reicht auch `YYYY-MM-DD`
- `end`: Endzeitpunkt, Format `YYYY-MM-DDThh:mm`; bei Tagesdaten reicht auch `YYYY-MM-DD`

Array-Parameter koennen kommasepariert oder mehrfach uebergeben werden:

```text
parameters=TL,RF
parameters=TL&parameters=RF
```

## Metadaten

Jeder Endpunkt hat eigene Metadaten. Dort stehen Stationsliste, Parameter, Einheiten, Datenverfuegbarkeit und Qualitaetsflags.

```python
import requests

meta_url = "https://dataset.api.hub.geosphere.at/v1/station/historical/klima-v2-10min/metadata"
meta = requests.get(meta_url, timeout=120).json()
```

Beim Wechsel der Aufloesung immer die passenden Metadaten pruefen:

```python
resolution = "1h"  # "10min", "1h", "1d"
meta = requests.get(f"{ENDPOINTS[resolution]}/metadata", timeout=120).json()
```

Wichtig: Nicht jedes Parameterkuerzel ist in jeder Aufloesung gleich vorhanden oder gleich definiert. Besonders Tagesdaten enthalten oft abgeleitete Werte wie Minima, Maxima, Mittelwerte oder Summen.

Die GPS-Koordinaten einer Station stehen nicht "in" der Stations-ID selbst, sondern in der Stationsliste der `/metadata`. Die ID ist der stabile Schluessel fuer Stationsdaten; Latitude/Longitude aus denselben Metadaten kann man fuer Raster-/Forecast-Endpunkte verwenden.

## Lokale Helper-API

Im Projekt gibt es jetzt das Paket `geosphere_api`. Ziel ist, dass das Notebook nur noch die gewuenschte Station und den Zeitraum ausdruecken muss:

```python
from geosphere_api import plot, station

matches = station("Lienz")
matches
```

Wenn mehrere Stationen gefunden werden, zeigt `matches` eine Liste mit Index, Name, ID und Koordinaten. Dann:

```python
lienz = matches.select(0)
```

Wenn nur ein Treffer existiert, kommt direkt eine `Station` zurueck. Alternativ kann man direkt auswaehlen:

```python
lienz = station("Lienz", choose=0)
```

Historie und Forecast:

```python
hist = lienz.historical(time="12h", resolution="10min", parameters=["TL", "RR"])
fc = lienz.forecast(parameters=["TL", "RR"])

fig, axes = plot(hist, fc)
```

Die Forecast-Abfrage verwendet automatisch `lienz.lat` und `lienz.lon` aus den Stationsmetadaten und fragt damit den naechstgelegenen Nowcast-Gitterpunkt ab.

Fuer ein aktuelles Meteogramm mit den letzten 12 Stunden ist der TAWES-Rohdaten-Endpunkt oft passender:

```python
from geosphere_api import meteogram

result = meteogram(
    station="Lienz",
    history="12h",
    forecast=None,
    mode="bright",
    output="outputs/lienz_meteogram_bright.png",
)
```

Dabei bedeutet:

- `source="tawes"`: aktuelle ungepruefte 10-min-Rohdaten der letzten Monate.
- `model="nwp"`: AROME-Forecast (`nwp-v1-1h-2500m`) mit 60 Stunden Vorhersage.
- `forecast_params=["TL", "RF", "RR", "FFAM", "DD"]`: Notebook-freundliche Stationskuerzel; die lokale API uebersetzt fuer AROME zu `t2m,rh2m,rr_acc,u10m,v10m`.
- `mode="bright"`: weisser Hintergrund; `mode="dark"`: dunkler Hintergrund.
- `forecast=None`: laengst verfuegbarer Forecast. Alternativ kann ein Endzeitpunkt gesetzt werden.

## Minimaler Request

```python
import requests

resolution = "10min"  # "10min", "1h", "1d"
url = ENDPOINTS[resolution]

q = {
    "station_ids": lienz_id,
    "parameters": "TL,RF,P,FFAM,FFX,RR",
    "start": "2026-05-01T00:00",
    "end": "2026-05-14T00:00",
}

r = requests.get(url, params=q, timeout=120)
r.raise_for_status()
data = r.json()
```

Fuer Tagesdaten wuerde ich Datumswerte ohne Uhrzeit verwenden:

```python
resolution = "1d"
url = ENDPOINTS[resolution]

q = {
    "station_ids": lienz_id,
    "parameters": "TL,RR",
    "start": "2026-05-01",
    "end": "2026-05-14",
}
```

## Wechsel zwischen 10 Minuten, Stunden und Tagen

Fuer ein Projekt kann man die Aufloesung gut kapseln:

```python
RESOURCE_BY_RESOLUTION = {
    "10min": "klima-v2-10min",
    "1h": "klima-v2-1h",
    "1d": "klima-v2-1d",
}

def station_endpoint(resolution):
    resource_id = RESOURCE_BY_RESOLUTION[resolution]
    return f"https://dataset.api.hub.geosphere.at/v1/station/historical/{resource_id}"
```

Dann bleibt der restliche Request fast identisch:

```python
url = station_endpoint("1h")

q = {
    "station_ids": lienz_id,
    "parameters": ",".join(params),
    "start": start.strftime("%Y-%m-%dT%H:%M"),
    "end": end.strftime("%Y-%m-%dT%H:%M"),
}
```

## Unterschiede der Datensaetze

### `klima-v2-10min`

- Messdaten von 1992 bis heute in 10-minuetiger Aufloesung.
- Wird alle 10 Minuten aktualisiert.
- Grossteil der Messdaten ab 2006 qualitaetsgeprueft.
- Qualitaetsstatus steht in Parametern mit Namensendung `_flag`.

Quelle: https://data.hub.geosphere.at/dataset/klima-v2-10min

### `klima-v2-1h`

- Stundenwerte vieler meteorologischer und klimatologischer Parameter.
- Je nach Parameter: Momentanwert zur vollen Stunde, Mittelwert, Extremwert oder Summe der letzten Stunde.
- Daten reichen bei einzelnen Parametern sehr weit zurueck; Update alle 10 Minuten.
- Qualitaetsflags verwenden ebenfalls die Namensendung `_flag`.

Quelle: https://data.hub.geosphere.at/dataset/klima-v2-1h

### `klima-v2-1d`

- Tages- und Terminwerte.
- Tageswerte sind je nach Parameter Summen, Mittelwerte, Minima oder Maxima ueber 24 Stunden.
- Teilweise sehr lange historische Reihen, aber alte Reihen koennen Luecken enthalten.
- Beobachtete/abgeleitete Tagesdaten koennen laengere Pruefprozesse haben.

Quelle: https://data.hub.geosphere.at/dataset/klima-v2-1d

## TAWES Rohdaten

Neben den geprueften `klima-v2-*` Daten gibt es `tawes-v1-10min`.

- Resource ID: `tawes-v1-10min`
- Historisch und current verfuegbar
- 10-minuetige Rohdaten, ungeprueft
- Deckt laut Datensatzbeschreibung jeweils die letzten 3 Monate bis heute ab
- Sinnvoll, wenn Echtzeitnaehe wichtiger ist als gepruefte/archivierte Daten

```python
CURRENT_TAWES = "https://dataset.api.hub.geosphere.at/v1/station/current/tawes-v1-10min"
HIST_TAWES = "https://dataset.api.hub.geosphere.at/v1/station/historical/tawes-v1-10min"
```

Quelle: https://data.hub.geosphere.at/dataset/tawes-v1-10min

## Praktische Empfehlung

Fuer Analysen und reproduzierbare Projekte:

```python
"10min" -> "klima-v2-10min"
"1h"    -> "klima-v2-1h"
"1d"    -> "klima-v2-1d"
```

Fuer Live-nahe Dashboards:

```python
"current" -> "station/current/tawes-v1-10min"
```

Beim Wechsel der Aufloesung sollte man nicht blind dieselben Parameterkuerzel verwenden, sondern kurz die jeweiligen `/metadata` pruefen. Die Request-Mechanik bleibt gleich, aber die meteorologische Bedeutung der Werte kann sich aendern: 10-Minutenwerte sind Mess-/Aggregationswerte auf kurzem Intervall, Stundenwerte koennen Momentanwerte oder Stundenaggregate sein, Tageswerte sind haeufig Tagesaggregate.
