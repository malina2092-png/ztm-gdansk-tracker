from fastapi import FastAPI, Header
from fastapi.responses import HTMLResponse, JSONResponse
import httpx
import time
import os

app = FastAPI(title="Transportie")

GPS_URL = "https://ckan2.multimediagdansk.pl/gpsPositions?v=2"
VEHICLE_DB_URL = "https://files.cloudgdansk.pl/d/otwarte-dane/ztm/baza-pojazdow.json?v=2"
STOPS_URL = "https://ckan.multimediagdansk.pl/dataset/c24aa637-3619-4dc2-a171-a23eec8f2172/resource/d3e96eb6-25ad-4d6c-8651-b1eb39155945/download/stopsingdansk.json"
DEPARTURES_URL = "https://ckan2.multimediagdansk.pl/departures"
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
# On Render plans with a low environment-variable limit, the existing
# SUPABASE_KEY may contain: publishable_key|service_role_key|owner_username
_supabase_parts = os.getenv("SUPABASE_KEY", "").split("|")
SUPABASE_KEY = _supabase_parts[0].strip() if _supabase_parts else ""
SUPABASE_SERVICE_ROLE_KEY = (
    _supabase_parts[1].strip()
    if len(_supabase_parts) > 1
    else os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
)
OWNER_USERNAME = (
    _supabase_parts[2].strip().lower()
    if len(_supabase_parts) > 2
    else os.getenv("OWNER_USERNAME", "").strip().lower()
)
_stops_cache = []
_stops_loaded_at = 0
_vehicle_db = {}
_vehicle_db_loaded_at = 0


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
:root{--bg:#f4f7fb;--surface:rgba(255,255,255,.88);--ink:#17243a;--muted:#718096;--line:#e7edf5;--blue:#3978e8;--blue-soft:#eaf1ff;--shadow:0 12px 34px rgba(34,55,91,.08)}
*{box-sizing:border-box}\n#mapBrand{position:fixed;z-index:1500;top:13px;left:66px;padding:10px 14px;border:1px solid rgba(255,255,255,.9);border-radius:12px;background:rgba(255,255,255,.94);color:#17243a;font-size:15px;font-weight:850;letter-spacing:-.3px;box-shadow:0 5px 18px rgba(34,55,91,.12);backdrop-filter:blur(12px);pointer-events:none}
body{margin:0;background:radial-gradient(circle at 10% 0%,#e9f1ff 0,transparent 32%),var(--bg);color:var(--ink);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}
header{position:fixed;z-index:1100;top:14px;right:16px;padding:0;display:flex;align-items:center;justify-content:flex-end;gap:12px;pointer-events:none}header .brand{display:none}header .live-pill{pointer-events:auto;box-shadow:var(--shadow)}
.brand{display:flex;align-items:center;gap:12px}.logo{width:46px;height:46px;border-radius:15px;background:linear-gradient(145deg,#5d94f3,#3267d6);display:grid;place-items:center;color:white;font-size:24px;box-shadow:0 8px 18px #3978e833}
h1{font-size:25px;margin:0;letter-spacing:-.7px}.subtitle{color:var(--muted);font-size:13px;margin-top:4px}
.live-pill{background:#e8f8ef;color:#16834b;padding:9px 13px;border-radius:30px;font-size:12px;font-weight:700;display:flex;align-items:center;gap:8px}.dot{width:7px;height:7px;background:#20b56a;border-radius:50%}
 .nav-brand{display:flex;align-items:center;gap:11px;padding:8px 8px 16px;margin-bottom:5px;border-bottom:1px solid #e8edf4;color:#17243a}.nav-brand-icon{width:39px;height:39px;display:grid;place-items:center;border-radius:12px;background:#eaf1ff;font-size:21px}.nav-brand strong{display:block;font-size:16px;letter-spacing:-.3px}.nav-brand small{display:block;margin-top:3px;color:#718096;font-size:10px}.nav-instagram{display:flex;align-items:center;gap:9px;margin-top:auto;padding:12px 10px;border-top:1px solid #e8edf4;color:#b04483!important;text-decoration:none;font-size:12px;font-weight:750}.instagram-glyph{width:23px;height:23px;display:grid;place-items:center;border:2px solid #b04483;border-radius:7px;font-size:19px;line-height:1}body.map-search-active #menuToggle{display:none!important}nav{position:fixed;z-index:1200;left:16px;top:62px;bottom:16px;width:214px;transition:transform .22s ease;display:flex;flex-direction:column;gap:7px;padding:16px;background:rgba(255,255,255,.91);border:1px solid #fff;border-radius:22px;box-shadow:var(--shadow);backdrop-filter:blur(18px);overflow:auto}
nav button,nav a,.primary,.secondary,.icon-button{border:0;border-radius:12px;padding:11px 15px;font-weight:650;font-size:13px;cursor:pointer;white-space:nowrap;text-decoration:none;display:inline-block}
nav button,nav a{background:transparent;color:#66758d;text-align:left;width:100%;padding:13px 14px}nav button.active{background:var(--blue-soft);color:var(--blue);box-shadow:inset 3px 0 var(--blue)}
body.menu-closed nav{transform:translateX(calc(-100% - 28px));pointer-events:none}body:not(.menu-closed) nav{transform:translateX(0);pointer-events:auto}body.menu-closed section:not(#mapa).active{margin-left:0;padding-left:30px}#menuToggle{position:fixed;z-index:1600;left:12px;top:12px;border:0;border-radius:11px;background:#fff;color:#263957;width:44px;height:44px;padding:0;font-size:21px;box-shadow:var(--shadow);cursor:pointer}#myLocation{position:fixed;z-index:1400;right:12px;left:auto;top:auto;bottom:12px;transform:none;display:grid;place-items:center;border:1px solid #fff;border-radius:12px;background:#1765d1;color:#fff;padding:0;box-shadow:0 4px 15px #123b7466;width:44px;height:44px;font-size:0;font-weight:800;cursor:pointer}#myLocation .loc-icon{display:grid;place-items:center;background:#fff;color:#1765d1;width:29px;height:29px;border-radius:9px;font-size:21px}#myLocation:disabled{opacity:.75;cursor:wait}#myLocation:active{transform:scale(.96)}#mapZoom{position:fixed;z-index:1600;right:12px;left:auto;top:64px;display:flex;flex-direction:column;overflow:hidden;border-radius:11px;background:#fff;box-shadow:var(--shadow);border:1px solid #e4eaf2}#mapZoom button{width:44px;height:42px;border:0;background:#fff;color:#263957;font-size:25px;font-weight:600;line-height:1;cursor:pointer}#mapZoom button+button{border-top:1px solid #e7edf5}#mapZoom button:active{background:#edf3ff}#locationStatus{position:fixed;z-index:1400;right:12px;left:auto;top:auto;bottom:62px;transform:none;background:#fff;padding:8px 10px;border:1px solid #dbe5f2;border-radius:11px;box-shadow:0 5px 22px #17345b25;font-size:12px;font-weight:600;display:block;max-width:230px;color:#29415f;pointer-events:none}#locationStatus:empty{display:none}main{padding:0;margin:0}
section{display:none}section.active{display:block}#mapa.active{display:block;position:fixed;inset:0;z-index:1}#mapVehicleSearchPanel{position:fixed;z-index:3000;top:22px;left:50%;transform:translateX(-50%);width:min(490px,calc(100vw - 210px));padding:8px;background:rgba(255,255,255,.97);border:1px solid #e3eaf4;border-radius:15px;box-shadow:0 8px 28px rgba(24,45,78,.2);backdrop-filter:blur(16px)}.map-search-input-wrap{display:flex;align-items:center;gap:9px;padding:0 10px;color:#52709a}.map-search-input-wrap>span{font-size:22px;line-height:1}.map-search-input-wrap input{flex:1;min-width:0;width:100%;border:0!important;outline:0!important;box-shadow:none!important;background:transparent;padding:10px 0;font-size:14px}.map-search-input-wrap button{border:0;background:#edf2f8;color:#52647e;border-radius:8px;width:29px;height:29px;font-size:20px;cursor:pointer;flex:none}#mapVehicleSearchResults{border-top:1px solid #e8edf4}#mapVehicleSearchResults button{cursor:pointer;border-radius:8px}#mapVehicleSearchResults button:hover{background:#edf4ff!important}#mapa .section-head{display:none}#mapa .map-layout{position:absolute;inset:0}#mapa .map-layout>.surface{position:absolute;inset:0;padding:0;border:0;border-radius:0;background:transparent;box-shadow:none}#mapa .map-side{position:absolute;z-index:600;right:16px;top:76px;width:230px;display:flex;flex-direction:column;gap:10px}#mapa .map-side .surface{background:rgba(255,255,255,.9);backdrop-filter:blur(14px);padding:13px;border-radius:16px}section:not(#mapa).active{position:relative;margin-left:246px;padding:88px 30px 30px}
.section-head{display:flex;justify-content:space-between;align-items:end;gap:12px;flex-wrap:wrap;margin:8px 0 16px}
h2{font-size:21px;letter-spacing:-.4px;margin:0 0 5px}.hint{font-size:13px;color:var(--muted)}
.surface{background:var(--surface);border:1px solid #fff;border-radius:20px;box-shadow:var(--shadow);padding:17px;backdrop-filter:blur(12px)}
.map-layout{display:block}
#map{height:100dvh;min-height:100dvh;width:100%;border-radius:0;z-index:1}
.map-side{display:flex;flex-direction:column;gap:12px}.stat{padding:15px;border:1px solid var(--line);border-radius:15px;background:#fff}.stat strong{display:block;font-size:25px;margin-top:6px}.stat span{font-size:12px;color:var(--muted)}
.primary{background:var(--blue);color:#fff}.secondary{background:var(--blue-soft);color:var(--blue)}.icon-button{background:var(--blue-soft);color:var(--blue);font-size:19px;padding:7px 12px}
input[type=text],input:not([type]),select{width:100%;border:1px solid var(--line);border-radius:12px;padding:12px 13px;background:#fff;color:var(--ink);outline:none;font-size:14px}
input:focus{border-color:#8bb1fa;box-shadow:0 0 0 3px #3978e81a}
.toolbar{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-bottom:13px}.toolbar input{max-width:330px}
.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:14px;background:#fff}
table{width:100%;border-collapse:collapse;min-width:560px;text-align:left;font-size:13px}
th{background:#f7f9fc;color:#738198;font-size:11px;text-transform:uppercase;letter-spacing:.5px;padding:13px 14px}
td{padding:13px 14px;border-top:1px solid #edf1f6}tbody tr:hover{background:#fafcff}
.tag{display:inline-flex;padding:5px 9px;background:#edf3ff;color:#326bd2;border-radius:20px;font-weight:700;font-size:12px}
.empty{padding:28px;text-align:center;color:var(--muted);font-size:13px}
.vehicle-label{background:#fff;color:#1d3151;border:1px solid #dce7f8;border-radius:9px;padding:5px 8px;font-weight:700;box-shadow:0 4px 12px #23395b20}
.vehicle-marker{background:transparent!important;border:0!important;width:auto!important;height:auto!important}.vehicle-dot{width:10px;height:10px;border-radius:50%;border:2px solid #fff;box-shadow:0 1px 5px #17243a88}.stop-icon{width:17px;height:17px;border-radius:50%;font-size:0;border:2px solid #fff;background:#1765a8;box-shadow:0 1px 5px #142b4570}.stop-marker{background:transparent!important;border:0!important}.vehicle-marker:before,.vehicle-marker:after{display:none!important}.vehicle-chip{font-size:10px!important;padding:3px 5px!important;border-radius:5px!important;box-shadow:0 1px 4px #17243a33!important}.stop-marker{stroke:#fff;stroke-width:2;fill:#64748b;fill-opacity:.95}.stop-icon{display:block;width:10px;height:10px;border-radius:50%;background:#1765a8;border:2px solid #fff;box-shadow:0 1px 4px #142b4560;font-size:0}.leaflet-tooltip.stop-label{background:#fff;border:1px solid #b9cce0;border-radius:6px;color:#203b5c;padding:3px 6px;font-size:10px;font-weight:700;box-shadow:0 2px 6px #142b4525}.leaflet-tooltip.stop-label:before{display:none}.stop-popup{min-width:220px;font:13px/1.45 Inter,Arial,sans-serif}.stop-action{display:block;width:100%;margin-top:9px;padding:10px 12px;border:0;border-radius:9px;background:#1765d1;color:#fff;font-weight:800;font-size:13px;cursor:pointer}.departures-card{max-width:850px}.stop-search-results{display:grid;gap:7px;margin-top:12px}.stop-search-results button{padding:10px 12px;text-align:left;border:1px solid #e0e8f3;background:#fff;border-radius:10px;color:#243c5c;cursor:pointer}.departures-list{margin-top:12px}.departure-row{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px solid #edf1f6}.vehicle-popup{min-width:190px;font:13px/1.5 Inter,Arial,sans-serif;color:#17243a}.vehicle-popup hr{border:0;border-top:1px solid #e6ebf2;margin:7px 0}
.leaflet-tooltip.vehicle-label:before{display:none}

.settings-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
.check{display:flex;gap:9px;align-items:center;padding:12px;background:#fff;border:1px solid var(--line);border-radius:12px;font-size:13px}
.check input{accent-color:var(--blue)}
.small-note{font-size:12px;color:var(--muted);line-height:1.5;margin-top:12px}
@media(max-width:850px){
 #map{height:100dvh;min-height:100dvh}
 #mapa .map-side{width:190px}
}
@media(max-width:520px){#mapVehicleSearchPanel{top:74px;left:19px;right:19px;transform:none;width:auto;padding:6px;border-radius:12px}.map-search-input-wrap input{font-size:13px}.map-search-input-wrap{gap:7px}
 #myLocation{right:12px;left:auto;top:auto;bottom:12px;width:44px;height:44px;min-width:44px;min-height:44px;padding:0;font-size:0}#myLocation .loc-icon{width:29px;height:29px;font-size:21px}#locationStatus{right:12px;left:auto;bottom:62px;max-width:calc(100vw - 30px);text-align:center}
 header{top:10px;right:8px}
 .live-pill{padding:7px 9px;font-size:10px}
 nav{position:fixed;z-index:1200;left:7px;top:64px;bottom:7px;right:auto;width:150px;height:auto;flex-direction:column;justify-content:flex-start;align-items:stretch;padding:9px 7px;gap:6px;border-radius:17px;overflow-y:auto}
 nav button{width:100%;flex:none;text-align:left;padding:12px 8px;font-size:11px;white-space:normal}
 nav button.active{box-shadow:inset 3px 0 var(--blue)}
 #mapa .map-side{top:58px;right:7px;width:135px;gap:6px}
 #mapa .map-side .surface{padding:8px;border-radius:11px}
 #mapa .map-side .stat strong{font-size:17px}
 #mapa .map-side .stat span{font-size:9px}
 #mapa .map-side .surface:nth-child(3){display:none}
 section:not(#mapa).active{margin-left:150px;padding:68px 9px 20px}
 section:not(#mapa).active .section-head{display:block}
 section:not(#mapa).active .surface{padding:10px}
 section:not(#mapa).active table{font-size:11px}
}
</style>
</head>
<body class="menu-closed">
<button id="menuToggle" onclick="toggleMenu()" aria-label="Otwórz lub zamknij menu">☰</button>\n
<div id="mapZoom" aria-label="Przybliżenie mapy"><button type="button" onclick="zoomMap(1)" aria-label="Przybliż">+</button><button type="button" onclick="zoomMap(-1)" aria-label="Oddal">−</button></div>
<button id="myLocation" onclick="locateUser()" aria-label="Pokaż moją lokalizację"><span class="loc-icon">◎</span><span>Moja lokalizacja</span></button><div id="locationStatus" aria-live="polite">Kliknij, aby pokazać swoją pozycję na mapie.</div>
<header>
 <div class="brand"><div class="logo">🚌</div><div><h1>Transportie</h1><div class="subtitle">Gdańsk · tracker komunikacji miejskiej</div></div></div>
 <div class="live-pill"><span class="dot"></span><span id="connection">Łączenie z GPS</span></div>
</header>
<nav>
 <div class="nav-brand"><div class="nav-brand-icon">🚌</div><div><strong>Transportie</strong><small>Gdańsk · komunikacja miejska</small></div></div>
 <button class="active" onclick="showSection('mapa',this)">▦ Mapa</button>
 <button onclick="showSection('ulubione',this)">⭐ Ulubione</button>
 <button onclick="showSection('wyjechalo',this)">🚌 Co wyjechało</button>
 <button onclick="showSection('linia',this)">🔎 Pojazdy na linii</button>
 <button onclick="showSection('odjazdy',this)">🚏 Odjazdy z przystanku</button>
 <button onclick="showSection('ustawienia',this)">⚙️ Ustawienia</button>
 <button onclick="showSection('konto',this)">👤 Konto</button>
 <button id="adminNavButton" style="display:none" onclick="showSection('administracja',this)">🛡️ Administracja</button>
 <a class="nav-instagram" href="https://www.instagram.com/boruwkowlosa/" target="_blank" rel="noopener noreferrer"><span class="instagram-glyph">◎</span><span>@boruwkowlosa</span></a>
</nav>
<main>
<section id="mapa" class="active">
 <div class="section-head"><div><h2>Mapa pojazdów</h2><div class="hint">Pozycje GPS aktualizowane automatycznie</div></div></div>
 <div id="mapVehicleSearchPanel">
  <div class="map-search-input-wrap"><span aria-hidden="true">⌕</span><input id="mapVehicleSearch" type="search" placeholder="Szukaj pojazdu: linia, brygada, numer taborowy…" autocomplete="off" oninput="searchMapVehicles()" aria-label="Wyszukiwarka pojazdów na mapie"><button type="button" id="clearMapVehicleSearch" onclick="clearMapVehicleSearch()" aria-label="Wyczyść wyszukiwanie">×</button></div>
  <div id="mapVehicleSearchResults" style="display:none;max-height: min(48vh,360px);overflow-y:auto;margin-top:7px"></div>
 </div>
 <div class="map-layout">
  <div class="surface"><div id="map"></div></div>
  <aside class="map-side">
   
  </aside>
 </div>
</section>
<section id="ulubione">
 <div class="section-head"><div><h2>Ulubione pojazdy</h2><div class="hint">Twoja prywatna lista zapisanych numerów taborowych</div></div></div>
 <div class="surface"><div class="toolbar"><input id="favoriteInput" placeholder="Wpisz numer taborowy"><button class="primary" onclick="addFavorite()">＋ Dodaj pojazd</button></div><div id="favoritesTable"></div><div class="small-note">Na tym etapie lista zapisuje się lokalnie w tej przeglądarce. Konto i synchronizację między urządzeniami dodamy w kolejnym etapie.</div></div>
</section>
<section id="wyjechalo">
 <div class="section-head"><div><h2>Co wyjechało?</h2><div class="hint">Pojazdy aktualnie raportujące pozycję GPS</div></div></div>
 <div class="surface"><div class="toolbar"><input id="fleetFilter" placeholder="Filtruj po numerze taborowym lub linii" oninput="renderActiveTable()"></div><div id="activeTable"></div></div>
</section>
<section id="linia">
 <div class="section-head"><div><h2>Pojazdy na linii</h2><div class="hint">Wyszukaj pojazdy przypisane aktualnie do wybranej linii</div></div></div>
 <div class="surface"><div class="toolbar"><input id="lineSearch" placeholder="Numer linii, np. 167"><button class="primary" onclick="filterLine()">Szukaj</button></div><div id="lineResults"></div></div>
</section>
<section id="odjazdy">
 <div class="section-head"><div><h2>Odjazdy z przystanku</h2><div class="hint">Wyszukaj przystanek i sprawdź najbliższe kursy</div></div></div>
 <div class="surface departures-card"><input id="stopSearch" type="text" placeholder="Wpisz nazwę przystanku…" oninput="searchStops()"><div id="stopSearchResults" class="stop-search-results"><div class="empty">Ładowanie przystanków…</div></div><div id="selectedStopDepartures" class="departures-list"></div></div>
</section>
<section id="ustawienia">
 <div class="section-head"><div><h2>Ustawienia mapy</h2><div class="hint">Dostosuj etykiety pojazdów do swoich preferencji</div></div></div>
 <div class="surface"><div class="settings-grid">
  <label class="check"><input type="checkbox" id="showLine" checked onchange="saveLabelSettings()"> Numer linii</label>
  <label class="check"><input type="checkbox" id="showBrigade" onchange="saveLabelSettings()"> Numer brygady</label>
  <label class="check"><input type="checkbox" id="showFleet" checked onchange="saveLabelSettings()"> Numer taborowy</label>
 </div><p class="small-note">Widoczne będą wyłącznie dane potwierdzone w źródłach ZTM.</p><div class="small-note" id="mapLabelSummary">Etykiety: —</div><div class="small-note" id="dataStatus">Połączenie z danymi: oczekiwanie…</div><div class="small-note" id="lastUpdateSettings">Ostatnia aktualizacja: —</div><div class="small-note" id="vehicleCountSettings">Widoczne pojazdy: —</div></div>
</section>
<section id="konto">
 <div class="section-head"><div><h2>Konto użytkownika</h2><div class="hint">Konto Transportie — bez adresu e-mail</div></div></div>
 <div class="surface" style="max-width:520px">
  <div id="authStatus" class="small-note">Sprawdzanie konfiguracji konta…</div>
  <div id="authForms"><label class="small-note" for="authUsername">Nazwa użytkownika</label><input id="authUsername" type="text" autocomplete="username" autocapitalize="none" placeholder="np. pasjonat_ztm" maxlength="24" style="width:100%;margin:6px 0 12px"><label class="small-note" for="authPassword">Hasło</label><input id="authPassword" type="password" autocomplete="current-password" placeholder="Minimum 8 znaków" style="width:100%;margin:6px 0 12px"><div class="toolbar"><button class="primary" onclick="loginUser()">Zaloguj się</button><button class="secondary" onclick="registerUser()">Utwórz konto</button></div><p class="small-note">Nazwa: 3–24 znaki, litery bez polskich znaków, cyfry, kropka lub podkreślenie. Hasło: minimum 8 znaków. Nie ma odzyskiwania hasła przez e-mail.</p></div>
  <div id="accountPanel" style="display:none"><b id="accountUsername"></b><p class="small-note">Jesteś zalogowany/a.</p><button class="secondary" onclick="logoutUser()">Wyloguj</button></div>
 </div>
</section>
<section id="administracja">
 <div class="section-head"><div><h2>Panel administracyjny</h2><div class="hint">Zarządzanie użytkownikami i rangami Transportie</div></div><button class="secondary" onclick="loadAdminUsers()">Odśwież listę</button></div>
 <div class="surface"><div id="adminStatus" class="small-note">Panel dostępny tylko dla właściciela.</div><div id="adminUsers"></div></div>
</section>
</main>
<div id="appError" style="display:none;position:fixed;z-index:99999;left:10px;right:10px;bottom:10px;background:#fff0f0;color:#8b1e1e;border:1px solid #e6aaaa;border-radius:12px;padding:12px;font:13px/1.4 system-ui;max-height:35vh;overflow:auto"><b>Błąd aplikacji</b><div id="appErrorText"></div></div>
<script>
(function(){
 function report(message){
  const box=document.getElementById('appError');
  const out=document.getElementById('appErrorText');
  if(box&&out){box.style.display='block';out.textContent=String(message||'Nieznany błąd');}
 }
 window.addEventListener('error',function(e){report((e.message||'Błąd JavaScript')+(e.filename?' · '+e.filename.split('/').pop():'')+(e.lineno?':'+e.lineno:''));});
 window.addEventListener('unhandledrejection',function(e){report('Promise: '+(e.reason&&e.reason.message||e.reason||'błąd'));});
})();
</script>
<script>
let map=null;let allStops=[];
function initMap(){
 try{
  if(!window.L||map)return;
  map=L.map('map',{zoomControl:false,attributionControl:false}).setView([54.3520,18.6466],12);L.control.attribution({prefix:'🇵🇱'}).addTo(map);map.on('zoomend',refreshTooltips);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap'}).addTo(map);
 }catch(e){console.error('Map init:',e);}
}
function loadMapLibrary(){
 if(window.L){initMap();if(typeof updateVehicles==='function')updateVehicles();if(typeof loadStops==='function')loadStops();return;}
 const script=document.createElement('script');
 script.src='https://unpkg.com/leaflet/dist/leaflet.js';
 script.async=true;
 script.onload=()=>{initMap();if(typeof updateVehicles==='function')updateVehicles();if(typeof loadStops==='function')loadStops();};
 script.onerror=()=>console.warn('Mapa niedostępna — pozostałe funkcje działają dalej.');
 document.head.appendChild(script);
}
const markers={};let stopMarkers={};let vehicles=[];let userLocationMarker=null;
loadMapLibrary();
let labelSettings={line:true,brigade:true,fleet:true};
try{const saved=JSON.parse(localStorage.getItem('transportie-labels')||'null');if(saved)labelSettings={...labelSettings,...saved};}catch(e){}
document.getElementById('showLine').checked=labelSettings.line;
document.getElementById('showBrigade').checked=labelSettings.brigade;
document.getElementById('showFleet').checked=labelSettings.fleet;
function showSection(id,button){document.querySelectorAll('main section').forEach(s=>s.classList.remove('active'));document.querySelectorAll('nav button').forEach(b=>b.classList.remove('active'));document.getElementById(id).classList.add('active');if(button)button.classList.add('active');if(window.innerWidth<=850)document.body.classList.add('menu-closed');if(id==='mapa'&&map)setTimeout(()=>map.invalidateSize(),180);if(id==='ulubione')renderFavorites();if(id==='wyjechalo')renderActiveTable();if(id==='konto')refreshAccount();if(id==='odjazdy'){if(!allStops.length)loadStops();searchStops();}}
 window.showSection=showSection;
function toggleMenu(){document.body.classList.toggle('menu-closed');if(map)setTimeout(()=>map.invalidateSize(),260);}
function zoomMap(delta){if(map)map.setZoom(map.getZoom()+delta);}
window.zoomMap=zoomMap;
function locateUser(){const status=document.getElementById('locationStatus'),button=document.getElementById('myLocation');button.disabled=true;button.style.opacity='.7';status.textContent='Pobieram lokalizację…';if(!navigator.geolocation){status.textContent='Ta przeglądarka nie obsługuje lokalizacji.';button.disabled=false;button.style.opacity='1';return;}navigator.geolocation.getCurrentPosition(pos=>{const lat=pos.coords.latitude,lon=pos.coords.longitude;if(map){if(userLocationMarker)map.removeLayer(userLocationMarker);userLocationMarker=L.circleMarker([lat,lon],{radius:10,color:'#fff',weight:4,fillColor:'#1765d1',fillOpacity:1}).addTo(map).bindPopup('Twoja lokalizacja');map.setView([lat,lon],16);userLocationMarker.openPopup();}status.textContent='Twoja lokalizacja jest widoczna na mapie.';button.disabled=false;button.style.opacity='1';},err=>{status.textContent=err.code===1?'Nie przyznano zgody. Zezwól Safari na dostęp do lokalizacji.':err.code===3?'Pobieranie lokalizacji trwało zbyt długo. Spróbuj ponownie.':'Nie udało się pobrać lokalizacji.';button.disabled=false;button.style.opacity='1';},{enableHighAccuracy:true,timeout:15000,maximumAge:30000});}
function saveLabelSettings(){labelSettings={line:document.getElementById('showLine').checked,brigade:document.getElementById('showBrigade').checked,fleet:document.getElementById('showFleet').checked};localStorage.setItem('transportie-labels',JSON.stringify(labelSettings));const summary=document.getElementById('mapLabelSummary');if(summary)summary.textContent='Etykiety: '+([labelSettings.line?'Linia':null,labelSettings.brigade?'Brygada':null,labelSettings.fleet?'Tabor':null].filter(Boolean).join(' · ')||'wyłączone');refreshTooltips();}
async function loadStops(){try{const response=await fetch('/api/stops');if(!response.ok)throw new Error('Nie udało się pobrać przystanków');const data=await response.json();allStops=Array.isArray(data.stops)?data.stops:[];if(!map){searchStops();return;}allStops.forEach(stop=>{const id=String(stop.stopId||''),lat=Number(stop.lat),lon=Number(stop.lon),name=stop.stopName||stop.stopDesc||'Przystanek';if(!id||!Number.isFinite(lat)||!Number.isFinite(lon)||stopMarkers[id])return;const marker=L.marker([lat,lon],{icon:L.divIcon({className:'stop-marker',html:'<div class="stop-icon" aria-label="Przystanek"></div>',iconSize:[14,14],iconAnchor:[7,7]})}).addTo(map);marker.bindTooltip(safe(name),{direction:'top',offset:[0,-10],className:'stop-label'});marker.bindPopup('<div class="stop-popup"><b>'+safe(name)+'</b><div class="small-note">Pobieranie najbliższych odjazdów…</div></div>');marker.on('popupopen',()=>loadStopDepartures(id,marker,name));stopMarkers[id]=marker;});searchStops();refreshTooltips();const results=document.getElementById('stopSearchResults');if(results&&!allStops.length)results.innerHTML='<div class="empty">ZTM nie zwrócił listy przystanków. Spróbuj odświeżyć stronę.</div>';}catch(e){console.warn('Przystanki:',e);const results=document.getElementById('stopSearchResults');if(results)results.innerHTML='<div class="empty">Nie udało się pobrać przystanków ZTM.</div>';}}
async function loadStopDepartures(id,marker,name){try{const response=await fetch('/api/departures/'+encodeURIComponent(id));if(!response.ok)throw new Error('API odjazdów');const data=await response.json();const rows=(data.departures||[]).slice(0,12);const html=rows.length?rows.map(d=>{const rawTime=d.estimatedTime||d.departureTime||d.time||d.scheduledTime;const dt=rawTime?new Date(rawTime):null;const t=dt&&!isNaN(dt.getTime())?dt.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'}):'—';const wait=dt&&!isNaN(dt.getTime())?Math.max(0,Math.round((dt.getTime()-Date.now())/60000)):null;const mins=wait!==null?(wait===0?'teraz':'za '+wait+' min'):(d.delayInSeconds==null?'':(d.delayInSeconds>0?'+':'')+Math.round(d.delayInSeconds/60)+' min');return '<div class="departure-row"><span><b>'+safe(d.routeShortName||d.route)+'</b> · '+safe(d.headsign||d.direction||'kierunek nieznany')+'</span><span><b>'+safe(mins||'—')+'</b><br><small>'+safe(t)+'</small></span></div>';}).join(''):'<div>Brak zaplanowanych odjazdów.</div>';marker.setPopupContent('<div class="stop-popup"><b>'+safe(name||'Przystanek')+'</b><div class="small-note">Najbliższe odjazdy · dane ZTM</div>'+html+'</div>');}catch(e){marker.setPopupContent('<div class="stop-popup"><b>'+safe(name||'Przystanek')+'</b><div>Nie udało się pobrać odjazdów.</div></div>');}}
async function showStopDepartures(id,name){const box=document.getElementById('selectedStopDepartures');if(box)box.innerHTML='<div class="empty">Pobieranie odjazdów…</div>';try{const response=await fetch('/api/departures/'+encodeURIComponent(id));if(!response.ok)throw new Error('API');const data=await response.json();const rows=(data.departures||[]).slice(0,20);const html=rows.length?rows.map(d=>{const raw=d.estimatedTime||d.departureTime||d.time||d.scheduledTime;const dt=raw?new Date(raw):null;const tm=dt&&!isNaN(dt.getTime())?dt.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'}):'—';const mins=dt&&!isNaN(dt.getTime())?Math.max(0,Math.round((dt.getTime()-Date.now())/60000)):null;return '<div class="departure-row"><span><b>'+safe(d.routeShortName||d.route||'—')+'</b> · '+safe(d.headsign||d.direction||'kierunek nieznany')+'</span><span><b>'+(mins===null?'—':mins===0?'teraz':'za '+mins+' min')+'</b><br><small>'+safe(tm)+'</small></span></div>';}).join(''):'<div class="empty">Brak odjazdów w odpowiedzi ZTM.</div>';if(box)box.innerHTML='<h3>'+safe(name)+'</h3>'+html;}catch(e){if(box)box.innerHTML='<div class="empty">Nie udało się pobrać odjazdów.</div>';}}
async function authRequest(path,body,token){const headers={'Content-Type':'application/json'};if(token)headers.Authorization='Bearer '+token;const response=await fetch(path,{method:body?'POST':'GET',headers,body:body?JSON.stringify(body):undefined});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.msg||data.message||data.error_description||data.error||'Błąd połączenia z kontem');return data;}
function getSession(){try{return JSON.parse(localStorage.getItem('transportie-session')||'null');}catch(e){return null;}}
function showAuthMessage(msg){document.getElementById('authStatus').textContent=msg;}
function validUsername(username){return /^[a-zA-Z0-9._]{3,24}$/.test(username);}
async function refreshAccount(){const session=getSession();const forms=document.getElementById('authForms'),panel=document.getElementById('accountPanel');if(session&&session.access_token){forms.style.display='none';panel.style.display='block';document.getElementById('accountUsername').textContent=localStorage.getItem('transportie-username')||'Zalogowane konto';showAuthMessage('Konto aktywne');}else{forms.style.display='block';panel.style.display='none';try{const cfg=await authRequest('/api/auth/config');showAuthMessage(cfg.enabled?'Zaloguj się lub utwórz konto, używając nazwy użytkownika.':'Logowanie wymaga konfiguracji Supabase w Render.');}catch(e){showAuthMessage(e.message);}}await updateAdminAccess();}
async function loginUser(){const username=document.getElementById('authUsername').value.trim().toLowerCase(),password=document.getElementById('authPassword').value;if(!validUsername(username)||!password){showAuthMessage('Wpisz poprawną nazwę użytkownika i hasło.');return;}try{const data=await authRequest('/api/auth/login',{username,password});localStorage.setItem('transportie-session',JSON.stringify(data));localStorage.setItem('transportie-username',username);document.getElementById('authPassword').value='';await refreshAccount();await updateAdminAccess();}catch(e){showAuthMessage(e.message);}}
async function registerUser(){const username=document.getElementById('authUsername').value.trim().toLowerCase(),password=document.getElementById('authPassword').value;if(!validUsername(username)){showAuthMessage('Nazwa musi mieć 3–24 znaki: litery a–z, cyfry, kropka lub podkreślenie.');return;}if(password.length<8){showAuthMessage('Hasło musi mieć co najmniej 8 znaków.');return;}try{const data=await authRequest('/api/auth/signup',{username,password});if(data.access_token){localStorage.setItem('transportie-session',JSON.stringify(data));localStorage.setItem('transportie-username',username);await refreshAccount();await updateAdminAccess();}else{showAuthMessage('Supabase nie zwrócił sesji. W panelu Supabase trzeba wyłączyć potwierdzanie adresu e-mail (Confirm email), ponieważ konta Transportie nie używają e-maila.');}}catch(e){showAuthMessage(e.message);}}
async function logoutUser(){const session=getSession();try{if(session?.access_token)await authRequest('/api/auth/logout',{},session.access_token);}catch(e){}localStorage.removeItem('transportie-session');localStorage.removeItem('transportie-username');await refreshAccount();updateAdminAccess();}
async function updateAdminAccess(){const button=document.getElementById('adminNavButton');if(!button)return;const session=getSession();if(!session?.access_token){button.style.display='none';return;}try{const info=await authRequest('/api/admin/me',null,session.access_token);button.style.display=info.is_owner?'block':'none';if(info.is_owner)loadAdminUsers();}catch(e){button.style.display='none';}}
async function loadAdminUsers(){const session=getSession(),status=document.getElementById('adminStatus'),box=document.getElementById('adminUsers');if(!session?.access_token){status.textContent='Zaloguj się na konto właściciela.';return;}status.textContent='Pobieranie użytkowników…';try{const data=await authRequest('/api/admin/users',null,session.access_token);status.textContent='Liczba kont: '+data.users.length;box.innerHTML=data.users.map(u=>{const username=safe(u.username||'bez nazwy'),role=u.role||'user';const options=['user','vip','moderator','admin'].map(r=>'<option value="'+r+'" '+(r===role?'selected':'')+'>'+({user:'Użytkownik',vip:'VIP',moderator:'Moderator',admin:'Administrator'}[r])+'</option>').join('');return '<div class="departure-row" style="align-items:center;flex-wrap:wrap"><span><b>'+username+'</b><br><small>'+safe(u.created_at||'')+'</small></span><span style="display:flex;gap:7px;align-items:center"><select data-admin-role="'+safe(u.id)+'" style="width:auto;min-width:135px">'+options+'</select><button class="secondary" data-save-role="'+safe(u.id)+'">Zapisz</button></span></div>';}).join('')||'<div class="empty">Brak kont.</div>';}catch(e){status.textContent=e.message;box.innerHTML='';}}
async function saveUserRole(userId){const session=getSession(),select=document.querySelector('[data-admin-role="'+CSS.escape(userId)+'"]');if(!session?.access_token||!select)return;const button=document.querySelector('[data-save-role="'+CSS.escape(userId)+'"]');if(button)button.disabled=true;try{await authRequest('/api/admin/users/'+encodeURIComponent(userId)+'/role',{role:select.value},session.access_token);document.getElementById('adminStatus').textContent='Ranga została zmieniona.';await loadAdminUsers();}catch(e){document.getElementById('adminStatus').textContent=e.message;if(button)button.disabled=false;}}
document.addEventListener('click',e=>{const b=e.target.closest('[data-save-role]');if(b)saveUserRole(b.getAttribute('data-save-role'));});
window.toggleMenu=toggleMenu;window.locateUser=locateUser;window.searchStops=searchStops;window.loginUser=loginUser;window.registerUser=registerUser;window.logoutUser=logoutUser;window.loadAdminUsers=loadAdminUsers;
function brigadeFor(v){const service=String(v.vehicleService||'');const match=service.match(/-(\d{2})$/);return match?match[1]:'—';}
function labelFor(v){const parts=[];if(labelSettings.line)parts.push('Linia '+(v.routeShortName||'?'));if(labelSettings.brigade)parts.push('Brygada '+brigadeFor(v));if(labelSettings.fleet)parts.push('Tabor '+(v.vehicleCode||'?'));return parts.join(' · ')||'Pojazd';}
function isTram(v){const route=String(v.routeShortName||'').trim();const service=String(v.vehicleType||v.type||v.vehicleService||'').toLowerCase();return service.includes('tram')||/^(2|3|4|5|6|7|8|9|10|11|12)$/.test(route);}
function vehicleIcon(v){const label=labelFor(v);const tram=isTram(v);const color=tram?'#2878df':'#dc3545';const zoom=map?map.getZoom():14;if(zoom<=12)return L.divIcon({className:'vehicle-marker',html:'<div class="vehicle-dot" style="background:'+color+'"></div>',iconSize:[12,12],iconAnchor:[6,6]});const compact=zoom<=14;const shown=compact?(v.routeShortName||'•'):label;const width=Math.max(28,Math.min(150,shown.length*5.7+14));return L.divIcon({className:'vehicle-marker',html:'<div class="vehicle-chip" style="background:'+color+';color:#fff;border:1px solid '+color+';border-radius:5px;padding:'+(compact?'2px 4px':'3px 5px')+';font-size:'+(compact?'9px':'10px')+';box-shadow:0 1px 4px #17243a33;font-weight:800;white-space:nowrap">'+safe(shown)+'</div>',iconSize:[width,compact?16:20],iconAnchor:[width/2,compact?8:10]});}
function vehiclePopup(v){const tram=isTram(v);const delay=v.delay!=null?v.delay:(v.delayInSeconds!=null?Math.round(v.delayInSeconds/60):null);const next=v.nextStops||[];return '<div class="vehicle-popup"><b style="font-size:16px">'+(tram?'🚊 Tramwaj':'🚌 Autobus')+' '+safe(v.routeShortName)+'</b><div>Tabor: <b>'+safe(v.vehicleCode)+'</b></div><div>Brygada: <b>'+safe(brigadeFor(v))+'</b></div><div>Opóźnienie: <b>'+(delay==null?'brak danych':(delay>0?'+'+delay:delay)+' min')+'</b></div><hr><b>Następne przystanki</b>'+(next.length?next.slice(0,2).map(s=>'<div>'+safe(s.name||s.stopName)+' · '+safe(s.time||s.arrivalTime)+'</div>').join(''):'<div>Brak danych o kolejnych przystankach</div>')+'<hr><div>Końcowy: '+safe(v.destination||v.finalStop||'brak danych')+'</div><div>Przyjazd: '+safe(v.finalArrival||'brak danych')+'</div></div>';}
function refreshTooltips(){vehicles.forEach(v=>{const id=String(v.vehicleCode||'');if(markers[id]){markers[id].setIcon(vehicleIcon(v));markers[id].setPopupContent(vehiclePopup(v));}});const zoom=map?map.getZoom():12;Object.values(stopMarkers).forEach(marker=>{if(zoom>=15){marker.openTooltip&&marker.openTooltip();}else{marker.closeTooltip&&marker.closeTooltip();}});}
function searchStops(){const results=document.getElementById('stopSearchResults');if(!results)return;const q=(document.getElementById('stopSearch')?.value||'').trim().toLowerCase();const matches=allStops.filter(s=>String(s.stopName||'').toLowerCase().includes(q)).slice(0,40);results.innerHTML=matches.length?matches.map(s=>'<button type="button" data-stop-select="'+safe(s.stopId)+'" data-stop-name="'+safe(s.stopName)+'">🚏 '+safe(s.stopName)+'</button>').join(''):'<div class="empty">Nie znaleziono przystanku.</div>';}
const mapSearchInput=document.getElementById("mapVehicleSearch");if(mapSearchInput){mapSearchInput.addEventListener("focus",()=>document.body.classList.add("map-search-active"));mapSearchInput.addEventListener("blur",()=>{if(!mapSearchInput.value.trim())document.body.classList.remove("map-search-active");});}
function clearMapVehicleSearch(){const input=document.getElementById('mapVehicleSearch');if(input){input.value='';input.blur();}document.body.classList.remove('map-search-active');searchMapVehicles();}window.clearMapVehicleSearch=clearMapVehicleSearch;
function searchMapVehicles(){const input=document.getElementById('mapVehicleSearch'),box=document.getElementById('mapVehicleSearchResults');if(!input||!box)return;const q=input.value.trim().toLowerCase();if(!q){box.style.display='none';box.innerHTML='';return;}const matches=vehicles.filter(v=>(String(v.vehicleCode||'')+' '+String(v.routeShortName||'')+' '+String(brigadeFor(v))+' '+String(v.destination||v.finalStop||'')).toLowerCase().includes(q)).slice(0,15);box.style.display='block';box.innerHTML=matches.length?matches.map(v=>'<button type="button" data-map-vehicle="'+safe(v.vehicleCode)+'" style="display:block;width:100%;text-align:left;padding:10px;border:0;border-top:1px solid #e6eaf0;background:transparent;color:inherit"><b>🚌 '+safe(v.vehicleCode)+'</b> · linia '+safe(v.routeShortName)+' · brygada '+safe(brigadeFor(v))+'<br><small>'+safe(v.destination||v.finalStop||'Kierunek niedostępny')+'</small></button>').join(''):'<div class="empty">Nie znaleziono aktywnych pojazdów.</div>';}
function safe(value){return String(value==null?'—':value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function table(rows,emptyText){if(!rows.length)return '<div class="empty">'+safe(emptyText)+'</div>';return '<div class="table-wrap"><table><thead><tr><th>Tabor</th><th>Linia</th><th>Brygada</th><th>Przewoźnik</th><th>Akcja</th></tr></thead><tbody>'+rows.map(v=>'<tr><td><b>'+safe(v.vehicleCode)+'</b></td><td><span class="tag">'+safe(v.routeShortName)+'</span></td><td>'+safe(brigadeFor(v))+'</td><td>'+safe(v.carrier)+'</td><td><button class="secondary" data-favorite="'+safe(v.vehicleCode)+'">☆ Ulubione</button></td></tr>').join('')+'</tbody></table></div>';}
function renderActiveTable(){const q=(document.getElementById('fleetFilter')?.value||'').trim().toLowerCase();const rows=vehicles.filter(v=>(String(v.vehicleCode||'')+' '+String(v.routeShortName||'')).toLowerCase().includes(q)).slice().sort((a,b)=>String(a.vehicleCode||'').localeCompare(String(b.vehicleCode||''),undefined,{numeric:true}));document.getElementById('activeTable').innerHTML=table(rows,'Brak pojazdów GPS');}
function getFavorites(){try{return JSON.parse(localStorage.getItem('transportie-favorites')||'[]');}catch(e){return [];}}
function saveFavorites(items){localStorage.setItem('transportie-favorites',JSON.stringify([...new Set(items)]));}
function addFavorite(){const input=document.getElementById('favoriteInput');const code=input.value.trim();if(!code)return;saveFavorites([...getFavorites(),code]);input.value='';renderFavorites();}
function toggleFavorite(code){if(!code)return;const list=getFavorites();saveFavorites(list.includes(String(code))?list.filter(x=>x!==String(code)):[...list,String(code)]);renderFavorites();}
function renderFavorites(){const list=getFavorites();const rows=list.map(code=>{const v=vehicles.find(x=>String(x.vehicleCode)===String(code));return '<tr><td><b>'+safe(code)+'</b></td><td>'+safe(v?.routeShortName||'Poza aktualnym GPS')+'</td><td><button class="secondary" data-favorite="'+safe(code)+'">Usuń</button></td></tr>';}).join('');document.getElementById('favoritesTable').innerHTML=list.length?'<div class="table-wrap"><table><thead><tr><th>Tabor</th><th>Linia</th><th></th></tr></thead><tbody>'+rows+'</tbody></table></div>':'<div class="empty">Nie masz jeszcze ulubionych pojazdów. Dodaj pierwszy numer powyżej.</div>';}
function filterLine(){const q=document.getElementById('lineSearch').value.trim().toLowerCase();const rows=vehicles.filter(v=>String(v.routeShortName||'').toLowerCase()===q).slice().sort((a,b)=>String(a.vehicleCode||'').localeCompare(String(b.vehicleCode||''),undefined,{numeric:true}));document.getElementById('lineResults').innerHTML=table(rows,q?'Nie znaleziono pojazdów na tej linii.':'Wpisz numer linii.');}
window.addFavorite=addFavorite;window.toggleFavorite=toggleFavorite;window.filterLine=filterLine;window.renderActiveTable=renderActiveTable;window.saveLabelSettings=saveLabelSettings;
document.addEventListener('click',function(event){const button=event.target.closest('[data-favorite]');if(button)toggleFavorite(button.getAttribute('data-favorite'));const stopButton=event.target.closest('[data-stop-departures]');if(stopButton)showStopDepartures(stopButton.getAttribute('data-stop-departures'),stopButton.getAttribute('data-stop-name'));const stopChoice=event.target.closest('[data-stop-select]');if(stopChoice)showStopDepartures(stopChoice.getAttribute('data-stop-select'),stopChoice.getAttribute('data-stop-name'));const vehicleChoice=event.target.closest('[data-map-vehicle]');if(vehicleChoice){const id=vehicleChoice.getAttribute('data-map-vehicle'),v=vehicles.find(item=>String(item.vehicleCode||'')===id);if(v&&map&&Number.isFinite(Number(v.lat))&&Number.isFinite(Number(v.lon))){map.setView([Number(v.lat),Number(v.lon)],16);if(markers[id])markers[id].openPopup();}const box=document.getElementById('mapVehicleSearchResults'),input=document.getElementById('mapVehicleSearch');if(box)box.style.display='none';if(input)input.value=v?(String(v.vehicleCode||'')+' · linia '+String(v.routeShortName||'')):id;}});
async function updateVehicles(){try{const response=await fetch('/api/live');if(!response.ok)throw new Error('API');const data=await response.json();vehicles=data.vehicles||[];document.getElementById('connection').textContent='GPS aktywny';document.getElementById('vehicleCountSettings').textContent='Widoczne pojazdy: '+vehicles.length;document.getElementById('lastUpdateSettings').textContent='Ostatnia aktualizacja: '+(data.lastUpdate||'brak danych');document.getElementById('dataStatus').textContent='Połączenie z danymi: aktywne';const active=new Set();vehicles.forEach(v=>{const id=String(v.vehicleCode||'');const lat=Number(v.lat),lon=Number(v.lon);if(!id||!Number.isFinite(lat)||!Number.isFinite(lon))return;active.add(id);if(!map)return;const label=labelFor(v);const icon=vehicleIcon(v);if(markers[id]){markers[id].setLatLng([lat,lon]);markers[id].setIcon(icon);markers[id].setPopupContent(vehiclePopup(v));}else{markers[id]=L.marker([lat,lon],{icon:icon}).addTo(map).bindPopup(vehiclePopup(v));}});if(map)Object.keys(markers).forEach(id=>{if(!active.has(id)){map.removeLayer(markers[id]);delete markers[id];}});renderActiveTable();searchMapVehicles();if(document.getElementById('ulubione').classList.contains('active'))renderFavorites();}catch(error){document.getElementById('connection').textContent='Brak połączenia GPS';document.getElementById('vehicleCountSettings').textContent='Widoczne pojazdy: —';document.getElementById('lastUpdateSettings').textContent='Ostatnia aktualizacja: —';document.getElementById('dataStatus').textContent='Połączenie z danymi: błąd';}}
const summary=document.getElementById('mapLabelSummary');if(summary)summary.textContent='Etykiety: '+([labelSettings.line?'Linia':null,labelSettings.brigade?'Brygada':null,labelSettings.fleet?'Tabor':null].filter(Boolean).join(' · ')||'wyłączone');
updateVehicles();if(map)loadStops();refreshAccount();setInterval(updateVehicles,20000);
</script>
</body>
</html>
"""


@app.get("/api/live")
async def live():
    global _vehicle_db, _vehicle_db_loaded_at
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(GPS_URL)
            response.raise_for_status()
            data = response.json()

            # Static fleet data is refreshed at most once per hour.
            if time.time() - _vehicle_db_loaded_at > 3600:
                try:
                    fleet_response = await client.get(VEHICLE_DB_URL)
                    fleet_response.raise_for_status()
                    fleet_data = fleet_response.json()
                    _vehicle_db = {
                        str(item.get("vehicleCode")): item
                        for item in fleet_data.get("results", [])
                        if item.get("vehicleCode") is not None
                    }
                    _vehicle_db_loaded_at = time.time()
                except Exception:
                    pass

        vehicles = data.get("vehicles", [])
        for vehicle in vehicles:
            fleet = _vehicle_db.get(str(vehicle.get("vehicleCode")), {})
            vehicle["carrier"] = (
                fleet.get("carrirer")
                or fleet.get("carrier")
                or fleet.get("operator")
                or "—"
            )
        return {
            "lastUpdate": data.get("lastUpdate"),
            "vehicles": vehicles
        }
    except Exception as error:
        return {
            "lastUpdate": None,
            "vehicles": [],
            "error": str(error)
        }

@app.get("/api/auth/config")
def auth_config():
    # Safe diagnostics only: never return secret values.
    return {
        "enabled": bool(SUPABASE_URL and SUPABASE_KEY),
        "has_service_role": bool(SUPABASE_SERVICE_ROLE_KEY),
        "owner_configured": bool(OWNER_USERNAME),
        "supabase_key_parts": len(_supabase_parts),
    }


@app.post("/api/auth/signup")
async def auth_signup(payload: dict):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return JSONResponse(status_code=503, content={"message": "Logowanie nie jest skonfigurowane w Render."})
    if not SUPABASE_SERVICE_ROLE_KEY:
        return JSONResponse(status_code=503, content={"message": "Brakuje klucza administracyjnego. W istniejącej zmiennej SUPABASE_KEY ustaw wartość w formacie: klucz_publishable|klucz_secret|mallytransportie. Nie dodawaj nowej zmiennej. Klucz secret pozostaje wyłącznie po stronie serwera."})
    username = str(payload.get("username", "")).strip().lower()
    password = str(payload.get("password", ""))
    if not __import__("re").fullmatch(r"[a-z0-9._]{3,24}", username) or len(password) < 8:
        return JSONResponse(status_code=400, content={"message": "Nazwa użytkownika musi mieć 3–24 znaki (a–z, cyfry, kropka lub podkreślenie), a hasło minimum 8 znaków."})
    internal_email = username + "@users.transportie.invalid"
    admin_headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": "Bearer " + SUPABASE_SERVICE_ROLE_KEY,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            created = await client.post(
                SUPABASE_URL + "/auth/v1/admin/users",
                headers=admin_headers,
                json={
                    "email": internal_email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {"username": username},
                    "app_metadata": {"transportie_role": "user"},
                },
            )
        except httpx.HTTPError:
            return JSONResponse(status_code=502, content={"message": "Nie udało się połączyć z usługą kont. Spróbuj ponownie."})
        if created.status_code in (409, 422):
            return JSONResponse(status_code=409, content={"message": "Ta nazwa użytkownika jest już zajęta. Wybierz inną."})
        if created.status_code not in (200, 201):
            return JSONResponse(status_code=502, content={"message": "Supabase odrzucił utworzenie konta. Sprawdź klucz administracyjny i konfigurację projektu."})
        try:
            signed_in = await client.post(
                SUPABASE_URL + "/auth/v1/token?grant_type=password",
                headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"},
                json={"email": internal_email, "password": password},
            )
            data = signed_in.json()
        except (httpx.HTTPError, ValueError):
            return JSONResponse(status_code=502, content={"message": "Konto utworzono, ale automatyczne logowanie się nie powiodło. Zaloguj się ręcznie."})
    if signed_in.status_code != 200:
        return JSONResponse(status_code=502, content={"message": "Konto utworzono, ale automatyczne logowanie się nie powiodło. Zaloguj się ręcznie."})
    return JSONResponse(status_code=200, content=data)


@app.post("/api/auth/login")
async def auth_login(payload: dict):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return JSONResponse(status_code=503, content={"message": "Logowanie nie jest skonfigurowane w Render."})
    username = str(payload.get("username", "")).strip().lower()
    password = str(payload.get("password", ""))
    if not __import__("re").fullmatch(r"[a-zA-Z0-9._]{3,24}", username) or not password:
        return JSONResponse(status_code=400, content={"message": "Podaj poprawną nazwę użytkownika i hasło."})
    internal_email = username + "@users.transportie.invalid"
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            SUPABASE_URL + "/auth/v1/token?grant_type=password",
            headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"},
            json={"email": internal_email, "password": password},
        )
    try:
        data = response.json()
    except Exception:
        data = {"message": "Nie udało się odczytać odpowiedzi usługi kont."}
    return JSONResponse(status_code=response.status_code, content=data)


@app.post("/api/auth/logout")
async def auth_logout(authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "", 1) if authorization.startswith("Bearer ") else ""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {"ok": True}
    if token:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(
                SUPABASE_URL + "/auth/v1/logout",
                headers={"apikey": SUPABASE_KEY, "Authorization": "Bearer " + token},
            )
    return {"ok": True}


async def get_authenticated_user(authorization: str):
    token = authorization.replace("Bearer ", "", 1) if authorization.startswith("Bearer ") else ""
    if not token or not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Zaloguj się ponownie.")
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            SUPABASE_URL + "/auth/v1/user",
            headers={"apikey": SUPABASE_KEY, "Authorization": "Bearer " + token},
        )
    if response.status_code != 200:
        raise ValueError("Sesja wygasła. Zaloguj się ponownie.")
    return response.json()


async def require_owner(authorization: str):
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Brakuje SUPABASE_SERVICE_ROLE_KEY w zmiennych Render.")
    owner_name = OWNER_USERNAME.strip().lower()
    if not owner_name:
        raise RuntimeError("Ustaw OWNER_USERNAME w zmiennych Render na swoją nazwę użytkownika.")
    user = await get_authenticated_user(authorization)
    username = str((user.get("user_metadata") or {}).get("username", "")).strip().lower()
    if username != owner_name:
        raise PermissionError("Brak uprawnień właściciela.")
    return user


@app.get("/api/admin/me")
async def admin_me(authorization: str = Header(default="")):
    try:
        user = await require_owner(authorization)
        return {"is_owner": True, "username": (user.get("user_metadata") or {}).get("username", "")}
    except Exception:
        return {"is_owner": False}


@app.get("/api/admin/users")
async def admin_users(authorization: str = Header(default="")):
    try:
        await require_owner(authorization)
    except PermissionError as error:
        return JSONResponse(status_code=403, content={"message": str(error)})
    except Exception as error:
        return JSONResponse(status_code=503, content={"message": str(error)})
    headers = {"apikey": SUPABASE_SERVICE_ROLE_KEY, "Authorization": "Bearer " + SUPABASE_SERVICE_ROLE_KEY}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(SUPABASE_URL + "/auth/v1/admin/users", params={"page": 1, "per_page": 100}, headers=headers)
            response.raise_for_status()
            payload = response.json()
        users = payload.get("users", []) if isinstance(payload, dict) else []
        result = []
        for item in users:
            metadata = item.get("user_metadata") or {}
            app_metadata = item.get("app_metadata") or {}
            result.append({
                "id": item.get("id"),
                "username": metadata.get("username") or str(item.get("email", "")).split("@")[0],
                "role": app_metadata.get("transportie_role", "user"),
                "created_at": item.get("created_at", ""),
            })
        result.sort(key=lambda item: item["username"].lower())
        return {"users": result}
    except Exception:
        return JSONResponse(status_code=502, content={"message": "Nie udało się pobrać listy kont z Supabase."})


@app.post("/api/admin/users/{user_id}/role")
async def admin_set_role(user_id: str, payload: dict, authorization: str = Header(default="")):
    try:
        await require_owner(authorization)
    except PermissionError as error:
        return JSONResponse(status_code=403, content={"message": str(error)})
    except Exception as error:
        return JSONResponse(status_code=503, content={"message": str(error)})
    role = str(payload.get("role", ""))
    if role not in ("user", "vip", "moderator", "admin"):
        return JSONResponse(status_code=400, content={"message": "Nieprawidłowa ranga."})
    headers = {"apikey": SUPABASE_SERVICE_ROLE_KEY, "Authorization": "Bearer " + SUPABASE_SERVICE_ROLE_KEY, "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.put(
                SUPABASE_URL + "/auth/v1/admin/users/" + user_id,
                headers=headers,
                json={"app_metadata": {"transportie_role": role}},
            )
            response.raise_for_status()
        return {"ok": True, "role": role}
    except Exception:
        return JSONResponse(status_code=502, content={"message": "Nie udało się zmienić rangi. Sprawdź identyfikator konta i konfigurację Supabase."})


@app.get("/api/stops")
async def get_stops():
    global _stops_cache, _stops_loaded_at
    if _stops_cache and time.time() - _stops_loaded_at < 86400:
        return {"stops": _stops_cache}
    try:
        async with httpx.AsyncClient(timeout=40) as client:
            response = await client.get(STOPS_URL)
            response.raise_for_status()
            raw = response.json()
        records = raw if isinstance(raw, list) else []
        if isinstance(raw, dict):
            # ZTM wraps static resources in a date-keyed object: {"YYYY-MM-DD": {"stops": [...]}}.
            records = raw.get("stops") or raw.get("results") or raw.get("data") or []
            if not records:
                dated = [
                    (key, value.get("stops"))
                    for key, value in raw.items()
                    if isinstance(value, dict) and isinstance(value.get("stops"), list)
                ]
                if dated:
                    records = sorted(dated, key=lambda entry: entry[0])[-1][1]
        stops = []
        for item in records:
            if not isinstance(item, dict):
                continue
            stop_id = item.get("stopId", item.get("stop_id", item.get("id")))
            name = item.get("stopName") or item.get("stopDesc") or item.get("stop_name") or item.get("name") or "Przystanek"
            lat = item.get("stopLat", item.get("stop_lat", item.get("lat", item.get("latitude"))))
            lon = item.get("stopLon", item.get("stop_lon", item.get("lon", item.get("longitude"))))
            try:
                lat, lon = float(lat), float(lon)
            except (TypeError, ValueError):
                continue
            if str(item.get("virtual", "0")) == "1" or str(item.get("nonpassenger", "0")) == "1" or str(item.get("depot", "0")) == "1":
                continue
            if stop_id is not None and 53.8 <= lat <= 54.8 and 18.0 <= lon <= 19.2:
                stops.append({"stopId": str(stop_id), "stopName": str(name), "lat": lat, "lon": lon})
        _stops_cache = stops
        _stops_loaded_at = time.time()
        return {"stops": stops}
    except Exception as error:
        return JSONResponse(status_code=502, content={"stops": [], "error": str(error)})


@app.get("/api/departures/{stop_id}")
async def get_departures(stop_id: str):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(DEPARTURES_URL, params={"stopId": stop_id})
            response.raise_for_status()
            data = response.json()
        item = data if isinstance(data, dict) else {}
        departures = item.get("departures", [])
        if not isinstance(departures, list):
            departures = []
        return {
            "lastUpdate": item.get("lastUpdate"),
            "departures": departures[:20],
        }
    except Exception as error:
        return JSONResponse(status_code=502, content={"departures": [], "error": str(error)})
