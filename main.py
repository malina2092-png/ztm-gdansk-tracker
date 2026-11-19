
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import httpx

app = FastAPI(title="Transportie")

GPS_URL = "https://ckan2.multimediagdansk.pl/gpsPositions?v=2"


@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Transportie</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css">

<style>
* { box-sizing: border-box; }

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #101827;
    color: white;
}

header {
    padding: 18px;
    background: #17243a;
}

h1 { margin: 0; font-size: 25px; }

nav {
    display: flex;
    gap: 8px;
    padding: 12px;
    overflow-x: auto;
    background: #17243a;
}

nav button {
    border: 0;
    border-radius: 10px;
    padding: 12px 15px;
    background: #263750;
    color: white;
    white-space: nowrap;
    cursor: pointer;
}

nav button.active { background: #2878e8; }

section {
    display: none;
    padding: 15px;
}

section.active { display: block; }

#map {
    height: 68vh;
    width: 100%;
    border-radius: 12px;
}

#status { padding: 12px 0; }

.panel {
    background: #1b2a40;
    padding: 15px;
    margin: 10px 0;
    border-radius: 12px;
}

input, select {
    padding: 12px;
    border-radius: 8px;
    border: 0;
    width: 100%;
    margin: 8px 0;
}

.vehicle-label {
    background: #17243a;
    color: white;
    border: 1px solid #2878e8;
    border-radius: 6px;
    padding: 4px 7px;
    font-weight: bold;
    box-shadow: none;
}

.leaflet-tooltip.vehicle-label:before {
    display: none;
}
</style>
</head>

<body>

<header>
    <h1>🚌 Transportie</h1>
    <div>Twój tracker komunikacji miejskiej</div>
</header>

<nav>
    <button class="active" onclick="showSection('mapa', this)">🗺️ Mapa</button>
    <button onclick="showSection('ulubione', this)">⭐ Ulubione</button>
    <button onclick="showSection('wyjechalo', this)">🚌 Co wyjechało</button>
    <button onclick="showSection('linia', this)">🔎 Pojazdy na linii</button>
</nav>

<section id="mapa" class="active">
    <div id="status">Ładowanie pojazdów...</div>
    <div id="map"></div>
</section>

<section id="ulubione">
    <h2>⭐ Ulubione pojazdy</h2>
    <div class="panel">
        <p>Twoje ulubione pojazdy pojawią się tutaj po podłączeniu konta.</p>
    </div>
</section>

<section id="wyjechalo">
    <h2>🚌 Co wyjechało?</h2>
    <div class="panel">
        <p>Lista aktualnie widocznych pojazdów GPS.</p>
        <div id="activeList">Ładowanie...</div>
    </div>
</section>

<section id="linia">
    <h2>🔎 Pojazdy na linii</h2>
    <input id="lineSearch" placeholder="Wpisz numer linii, np. 167">
    <button onclick="filterLine()">Szukaj</button>
    <div id="lineResults"></div>
</section>

<script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>

<script>
const map = L.map('map').setView([54.3520, 18.6466], 12);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap'
}).addTo(map);

const markers = {};
let vehicles = [];

function showSection(id, button) {
    document.querySelectorAll('section').forEach(s =>
        s.classList.remove('active')
    );
    document.querySelectorAll('nav button').forEach(b =>
        b.classList.remove('active')
    );

    document.getElementById(id).classList.add('active');
    button.classList.add('active');

    if (id === 'mapa') {
        setTimeout(() => map.invalidateSize(), 100);
    }
}

function vehicleLabel(v) {
    return 'Linia: ' + (v.routeShortName || '?') +
        ' | Brygada: brak danych' +
        ' | Tabor: ' + (v.vehicleCode || '?');
}

async function updateVehicles() {
    try {
        const response = await fetch('/api/live');
        if (!response.ok) throw new Error('Błąd API');

        const data = await response.json();
        vehicles = data.vehicles || [];

        document.getElementById('status').innerText =
            'Pojazdy na mapie: ' + vehicles.length;

        const active = new Set();

        vehicles.forEach(v => {
            const id = String(v.vehicleCode || '');
            const lat = Number(v.lat);
            const lon = Number(v.lon);

            if (!id || !Number.isFinite(lat) || !Number.isFinite(lon)) return;

            active.add(id);
            const label = vehicleLabel(v);

            if (markers[id]) {
                markers[id].setLatLng([lat, lon]);
                markers[id].setTooltipContent(label);
                markers[id].setPopupContent(label);
            } else {
                markers[id] = L.marker([lat, lon])
                    .addTo(map)
                    .bindPopup(label)
                    .bindTooltip(label, {
                        permanent: true,
                        direction: 'top',
                        className: 'vehicle-label'
                    });
            }
        });

        Object.keys(markers).forEach(id => {
            if (!active.has(id)) {
                map.removeLayer(markers[id]);
                delete markers[id];
            }
        });

        document.getElementById('activeList').innerHTML =
            vehicles.map(v =>
                '<div class="panel">Linia: ' +
                (v.routeShortName || '?') +
                '<br>Tabor: ' + (v.vehicleCode || '?') +
                '</div>'
            ).join('') || 'Brak pojazdów';

    } catch (error) {
        document.getElementById('status').innerText =
            'Nie udało się pobrać danych GPS';
    }
}

function filterLine() {
    const line = document.getElementById('lineSearch')
        .value.trim().toLowerCase();

    const found = vehicles.filter(v =>
        String(v.routeShortName || '').toLowerCase() === line
    );

    document.getElementById('lineResults').innerHTML =
        found.map(v =>
            '<div class="panel">Linia: ' +
            (v.routeShortName || '?') +
            '<br>Tabor: ' + (v.vehicleCode || '?') +
            '</div>'
        ).join('') || 'Nie znaleziono pojazdów na tej linii.';
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
