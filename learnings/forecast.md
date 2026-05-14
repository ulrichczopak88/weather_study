# GeoSphere Forecast API

## Datensatz

Der Datensatz `nowcast-v1-15min-1km` ist die GeoSphere-Austria-Kurzfristvorhersage auf Basis von INCA.

- Raeumliche Aufloesung: 1 km x 1 km
- Zeitliche Aufloesung: 15 Minuten
- Vorhersagehorizont: 3 Stunden
- Update-Frequenz: 15 Minuten
- Bounding Box: 45.5 - 49.48 Grad N, 8.1 - 17.74 Grad E
- Projektion des Rasters: MGI / Austria Lambert, EPSG:31287
- API-Koordinaten fuer Requests: EPSG:4326, also `lat,lon` bzw. Bounding Box in WGS84

Quelle: https://data.hub.geosphere.at/dataset/nowcast-v1-15min-1km

## AROME / NWP Forecast

Der Datensatz `nwp-v1-1h-2500m` ist das hochaufloesende Wettervorhersagemodell AROME.

- Modell: AROME, Application of Research to Operations at MEsoscale
- Raeumliche Aufloesung: 2.5 km
- Zeitliche Aufloesung: 1 Stunde
- Vorhersagehorizont: 60 Stunden
- Update-Frequenz: 3-stuendlich
- Bounding Box: 42.98 - 51.82 Grad N, 5.49 - 22.1 Grad E
- Projektion: WGS84 / EPSG:4326
- Parametergruppen: Temperatur, Niederschlag, Wind, Strahlung, Feuchtemasse, Gewitter, Bewoelkung, Druck

Quelle: https://data.hub.geosphere.at/dataset/nwp-v1-1h-2500m

## API-Endpunkte

Die Dataset-API ist nach folgendem Muster aufgebaut:

```text
https://dataset.api.hub.geosphere.at/v1/<type>/<mode>/<resource_id>
```

Fuer den Nowcast gibt es zwei relevante Forecast-Endpunkte:

```python
BASE_TS = "https://dataset.api.hub.geosphere.at/v1/timeseries/forecast/nowcast-v1-15min-1km"
BASE_GRID = "https://dataset.api.hub.geosphere.at/v1/grid/forecast/nowcast-v1-15min-1km"
```

Fuer AROME/NWP gilt analog:

```python
NWP_TS = "https://dataset.api.hub.geosphere.at/v1/timeseries/forecast/nwp-v1-1h-2500m"
NWP_GRID = "https://dataset.api.hub.geosphere.at/v1/grid/forecast/nwp-v1-1h-2500m"
```

`timeseries` ist fuer einzelne Orte am bequemsten: man uebergibt eine oder mehrere Koordinaten mit `lat_lon`, und die API liefert die Zeitreihe am naechstgelegenen Gitterpunkt.

`grid` ist fuer Raster-Ausschnitte gedacht: man uebergibt eine Bounding Box mit `bbox`.

Quellen:

- https://dataset.api.hub.geosphere.at/v1/docs/getting-started.html
- https://dataset.api.hub.geosphere.at/v1/docs/user-guide/type.html

## Wichtige Query-Parameter

Forecast-Endpunkte verwenden neben den typ-spezifischen Parametern auch Forecast-Parameter:

- `parameters`: ein oder mehrere Wetterparameter, z. B. kommasepariert
- `lat_lon`: fuer `timeseries`, Format `lat,lon`; mehrfach moeglich
- `bbox`: fuer `grid`, Format `south,west,north,east`
- `start`: optional, Format `YYYY-MM-DDThh:mm`
- `end`: optional, Format `YYYY-MM-DDThh:mm`
- `forecast_offset`: optional; `0` ist der neueste Forecast, `1` der vorherige usw.

Wenn `start` und `end` bei Forecasts fehlen, nimmt die API laut Doku den aktuellen Forecast-Zeitraum: `start` defaultet auf den letzten Forecast-Zeitpunkt vor jetzt, `end` auf das Ende des Forecasts.

Quelle: https://dataset.api.hub.geosphere.at/v1/docs/user-guide/mode.html

## Minimaler Timeseries-Request

Beispiel fuer eine Punkt-Zeitreihe bei Lienz. Die Parameterkuerzel sollten vorher aus `/metadata` geprueft werden.

```python
import requests

url = "https://dataset.api.hub.geosphere.at/v1/timeseries/forecast/nowcast-v1-15min-1km"

q = {
    "parameters": "t2m,rr",
    "lat_lon": "46.83,12.77",
    "forecast_offset": 0,
}

r = requests.get(url, params=q, timeout=120)
r.raise_for_status()
data = r.json()
```

Beispiel fuer AROME/NWP:

```python
url = "https://dataset.api.hub.geosphere.at/v1/timeseries/forecast/nwp-v1-1h-2500m"

q = {
    "parameters": "t2m,rr_acc",
    "lat_lon": "46.83,12.77",
    "forecast_offset": 0,
}

r = requests.get(url, params=q, timeout=120)
r.raise_for_status()
data = r.json()
```

## Metadaten pruefen

Die erlaubten Parameter und aktuellen Forecast-Zeiten stehen in den Metadaten des Endpunkts:

```python
meta_url = "https://dataset.api.hub.geosphere.at/v1/timeseries/forecast/nowcast-v1-15min-1km/metadata"
meta = requests.get(meta_url, timeout=120).json()
```

Bei Forecast-Datensaetzen sind laut Doku besonders diese Metadaten relevant:

- `available_forecast_reftimes`: verfuegbare Forecast-Referenzzeiten
- `last_forecast_reftime`: neueste Forecast-Referenzzeit
- `max_forecast_offset`: groesster erlaubter `forecast_offset`
- `forecast_length`: Anzahl der Zeitschritte in einem Forecast

Praktisch wichtig: Der Nowcast nutzt andere Parameterkuerzel als die Stationsdaten. Fuer Temperatur und Niederschlag sind im Nowcast Beispiele mit lowercase Codes bekannt:

```python
"t2m"  # 2-m-Temperatur im Nowcast
"rr"   # Niederschlag im Nowcast
```

Die lokale `geosphere_api` uebersetzt deshalb fuer einfache Notebook-Nutzung `TL -> t2m` und `RR -> rr`, wenn Forecast-Daten abgefragt werden.

Bei AROME/NWP sind die Parameterkuerzel lowercase. Ein funktionierendes Beispiel aus der Community nutzt u. a. `t2m`, `rh2m`, `rr_acc`, `sy`, `u10m`, `v10m`. Die lokale `geosphere_api` uebersetzt deshalb je Modell:

```python
model="nowcast"  # TL -> t2m, RR -> rr
model="nwp"      # TL -> t2m, RR -> rr_acc
```

Hinweis: Ich konnte die Live-Metadaten hier nicht per lokalem `curl` abrufen, weil der Netzwerkzugriff im Workspace nicht freigegeben wurde. Im Notebook sollte der Request genauso funktionieren wie deine bisherigen GeoSphere-Requests.

## Bezug zum bestehenden Notebook

Im Notebook `notebooks/import_weather_data.ipynb` wird bisher der Stations-Endpunkt verwendet:

```python
https://dataset.api.hub.geosphere.at/v1/station/historical/klima-v2-10min
```

Der Nowcast ist kein Stationsdatensatz, sondern ein Rasterdatensatz. Fuer einen vergleichbaren Workflow mit einem Ort ist deshalb der `timeseries/forecast`-Endpunkt die naechste Entsprechung.

Der wichtigste Wechsel ist:

```python
# bisher: station_ids
"station_ids": lienz_id

# nowcast: Koordinate
"lat_lon": "46.83,12.77"
```

Und:

```python
# bisher: historical mit start/end im Rueckblick
"/station/historical/..."

# nowcast: forecast, optional mit forecast_offset
"/timeseries/forecast/..."
```
