
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import httpx

app = FastAPI(title="ZTM Gdańsk Tracker")

GPS_URL = "https://ckan2.multimediagdansk.pl/gpsPositions?v=2"


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>ZTM Gdańsk Tracker</title>
        <link rel="stylesheet"
        href="https://unpkg.com/leaflet/dist/leaflet.css">
        <style>
            body {
                margin: 0;
                font-family: Arial, sans-serif;
                background: #101827;
                color: white;
            }
            header {
                padding: 20px;
                background: #17243a;
            }
            h1 { margin: 0; font-size: 22px; }
            #status { padding: 12px 20px; }
            #map { height: 75vh; width: 100%; }
        </style>
    </head>
    <body>
        <header>
            <h1>🚌 ZTM Gdańsk Tracker</h1>
        </header>
        <div id="status">Ładowanie pojazdów...</div>
        <div id="map"></div>

        <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
        <script>
            const map = L.map('map').setView([54.3520, 18.6466], 12);

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap'
            }).addTo(map);

            const markers = {};

            async function updateVehicles() {
                try {
                    const response = await fetch('/api/live');
                    const data = await response.json();

                    document.getElementById('status').innerText =
                        'Pojazdy na mapie: ' + data.vehicles.length;

                    const active = new Set();

                    data.vehicles.forEach(v => {
                        const id = String(v.vehicleCode);
                        const lat = Number(v.lat);
                        const lon = Number(v.lon);

                        if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

                        active.add(id);

                        const label =
                            'Linia: ' + (v.routeShortName || '?') +
                            ' | Tabor: ' + id;

                        if (markers[id]) {
                            markers[id].setLatLng([lat, lon]);
                            markers[id].setPopupContent(label);
                        } else {
                            markers[id] = L.marker([lat, lon])
                                .addTo(map)
                                .bindPopup(label);
                        }
                    });

                    Object.keys(markers).forEach(id => {
                        if (!active.has(id)) {
                            map.removeLayer(markers[id]);
                            delete markers[id];
                        }
                    });

                } catch (error) {
                    document.getElementById('status').innerText =
                        'Błąd pobierania danych GPS';
                }
            }

            updateVehicles();
            setInterval(updateVehicles, 20000);
        </script>
    </body>
    </html>
    """


@app.get("/api/live")
async def live():
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(GPS_URL)
            response.raise_for_status()
            data = response.json()

        return {
            "lastUpdate": data.get("lastUpdate"),
            "vehicles": data.get("vehicles", [])
        }

    except Exception as error:
        return {
            "lastUpdate": None,
            "vehicles": [],
            "error": str(error)
        }
