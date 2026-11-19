from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import httpx
import time

app = FastAPI(title="Transportie")

GPS_URL = "https://ckan2.multimediagdansk.pl/gpsPositions?v=2"
VEHICLE_DB_URL = "https://files.cloudgdansk.pl/d/otwarte-dane/ztm/baza-pojazdow.json?v=2"
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
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(circle at 10% 0%,#e9f1ff 0,transparent 32%),var(--bg);color:var(--ink);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}
header{position:fixed;z-index:1100;top:14px;right:16px;padding:0;display:flex;align-items:center;justify-content:flex-end;gap:12px;pointer-events:none}header .brand{display:none}header .live-pill{pointer-events:auto;box-shadow:var(--shadow)}
.brand{display:flex;align-items:center;gap:12px}.logo{width:46px;height:46px;border-radius:15px;background:linear-gradient(145deg,#5d94f3,#3267d6);display:grid;place-items:center;color:white;font-size:24px;box-shadow:0 8px 18px #3978e833}
h1{font-size:25px;margin:0;letter-spacing:-.7px}.subtitle{color:var(--muted);font-size:13px;margin-top:4px}
.live-pill{background:#e8f8ef;color:#16834b;padding:9px 13px;border-radius:30px;font-size:12px;font-weight:700;display:flex;align-items:center;gap:8px}.dot{width:7px;height:7px;background:#20b56a;border-radius:50%}
nav{position:fixed;z-index:1200;left:16px;top:16px;bottom:16px;width:214px;display:flex;flex-direction:column;gap:7px;padding:16px;background:rgba(255,255,255,.91);border:1px solid #fff;border-radius:22px;box-shadow:var(--shadow);backdrop-filter:blur(18px);overflow:auto}
nav button,nav a,.primary,.secondary,.icon-button{border:0;border-radius:12px;padding:11px 15px;font-weight:650;font-size:13px;cursor:pointer;white-space:nowrap;text-decoration:none;display:inline-block}
nav button,nav a{background:transparent;color:#66758d;text-align:left;width:100%;padding:13px 14px}nav button.active{background:var(--blue-soft);color:var(--blue);box-shadow:inset 3px 0 var(--blue)}
main{padding:0;margin:0}
section{display:none}section.active{display:block}#mapa.active{display:block;position:fixed;inset:0;z-index:1}#mapa .section-head{display:none}#mapa .map-layout{position:absolute;inset:0}#mapa .map-layout>.surface{position:absolute;inset:0;padding:0;border:0;border-radius:0;background:transparent;box-shadow:none}#mapa .map-side{position:absolute;z-index:600;right:16px;top:76px;width:230px;display:flex;flex-direction:column;gap:10px}#mapa .map-side .surface{background:rgba(255,255,255,.9);backdrop-filter:blur(14px);padding:13px;border-radius:16px}section:not(#mapa).active{position:relative;margin-left:246px;padding:88px 30px 30px}
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
.vehicle-marker{background:transparent!important;border:0!important;width:auto!important;height:auto!important}.vehicle-marker:before,.vehicle-marker:after{display:none!important}.vehicle-popup{min-width:190px;font:13px/1.5 Inter,Arial,sans-serif;color:#17243a}.vehicle-popup hr{border:0;border-top:1px solid #e6ebf2;margin:7px 0}
.leaflet-tooltip.vehicle-label:before{display:none}

.settings-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
.check{display:flex;gap:9px;align-items:center;padding:12px;background:#fff;border:1px solid var(--line);border-radius:12px;font-size:13px}
.check input{accent-color:var(--blue)}
.small-note{font-size:12px;color:var(--muted);line-height:1.5;margin-top:12px}
@media(max-width:850px){
 #map{height:100dvh;min-height:100dvh}
 #mapa .map-side{width:190px}
}
@media(max-width:520px){
 header{top:10px;right:8px}
 .live-pill{padding:7px 9px;font-size:10px}
 nav{position:fixed;z-index:1200;left:7px;top:7px;bottom:7px;right:auto;width:142px;height:auto;flex-direction:column;justify-content:flex-start;align-items:stretch;padding:9px 7px;gap:6px;border-radius:17px;overflow-y:auto}
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
<body>
<header>
 <div class="brand"><div class="logo">🚌</div><div><h1>Transportie</h1><div class="subtitle">Gdańsk · tracker komunikacji miejskiej</div></div></div>
 <div class="live-pill"><span class="dot"></span><span id="connection">Łączenie z GPS</span></div>
</header>
<nav>
 <button class="active" onclick="showSection('mapa',this)">▦ Mapa</button>
 <button onclick="showSection('ulubione',this)">⭐ Ulubione</button>
 <button onclick="showSection('wyjechalo',this)">🚌 Co wyjechało</button>
 <button onclick="showSection('linia',this)">🔎 Pojazdy na linii</button>
 <button onclick="showSection('ustawienia',this)">⚙️ Ustawienia</button>
</nav>
<main>
<section id="mapa" class="active">
 <div class="section-head"><div><h2>Mapa pojazdów</h2><div class="hint">Pozycje GPS aktualizowane automatycznie</div></div></div>
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
<section id="ustawienia">
 <div class="section-head"><div><h2>Ustawienia mapy</h2><div class="hint">Dostosuj etykiety pojazdów do swoich preferencji</div></div></div>
 <div class="surface"><div class="settings-grid">
  <label class="check"><input type="checkbox" id="showLine" checked onchange="saveLabelSettings()"> Numer linii</label>
  <label class="check"><input type="checkbox" id="showBrigade" onchange="saveLabelSettings()"> Numer brygady</label>
  <label class="check"><input type="checkbox" id="showFleet" checked onchange="saveLabelSettings()"> Numer taborowy</label>
 </div><p class="small-note">Widoczne będą wyłącznie dane potwierdzone w źródłach ZTM.</p><div class="small-note" id="dataStatus">Połączenie z danymi: oczekiwanie…</div><div class="small-note" id="lastUpdateSettings">Ostatnia aktualizacja: —</div><div class="small-note" id="vehicleCountSettings">Widoczne pojazdy: —</div></div>
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
let map=null;
function initMap(){
 try{
  if(!window.L||map)return;
  map=L.map('map').setView([54.3520,18.6466],12);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap'}).addTo(map);
 }catch(e){console.error('Map init:',e);}
}
function loadMapLibrary(){
 if(window.L){initMap();return;}
 const script=document.createElement('script');
 script.src='https://unpkg.com/leaflet/dist/leaflet.js';
 script.async=true;
 script.onload=()=>{initMap();if(typeof updateVehicles==='function')updateVehicles();};
 script.onerror=()=>console.warn('Mapa niedostępna — pozostałe funkcje działają dalej.');
 document.head.appendChild(script);
}
const markers={};let vehicles=[];
loadMapLibrary();
let labelSettings={line:true,brigade:true,fleet:true};
try{const saved=JSON.parse(localStorage.getItem('transportie-labels')||'null');if(saved)labelSettings={...labelSettings,...saved};}catch(e){}
document.getElementById('showLine').checked=labelSettings.line;
document.getElementById('showBrigade').checked=labelSettings.brigade;
document.getElementById('showFleet').checked=labelSettings.fleet;
function showSection(id,button){document.querySelectorAll('main section').forEach(s=>s.classList.remove('active'));document.querySelectorAll('nav button').forEach(b=>b.classList.remove('active'));document.getElementById(id).classList.add('active');button.classList.add('active');if(id==='mapa'&&map)setTimeout(()=>map.invalidateSize(),120);if(id==='ulubione')renderFavorites();if(id==='wyjechalo')renderActiveTable();}
 window.showSection=showSection;
function saveLabelSettings(){labelSettings={line:document.getElementById('showLine').checked,brigade:document.getElementById('showBrigade').checked,fleet:document.getElementById('showFleet').checked};localStorage.setItem('transportie-labels',JSON.stringify(labelSettings));document.getElementById('mapLabelSummary').textContent=[labelSettings.line?'Linia':null,labelSettings.brigade?'Brygada':null,labelSettings.fleet?'Tabor':null].filter(Boolean).join(' · ')||'Etykiety wyłączone';refreshTooltips();}
function brigadeFor(v){const service=String(v.vehicleService||'');const match=service.match(/-(\d{2})$/);return match?match[1]:'—';}
function labelFor(v){const parts=[];if(labelSettings.line)parts.push('Linia '+(v.routeShortName||'?'));if(labelSettings.brigade)parts.push('Brygada '+brigadeFor(v));if(labelSettings.fleet)parts.push('Tabor '+(v.vehicleCode||'?'));return parts.join(' · ')||'Pojazd';}
function vehicleIcon(v){const label=labelFor(v);const tram=String(v.vehicleType||v.type||'').toLowerCase().includes('tram')||String(v.vehicleService||'').toLowerCase().includes('tram');const color=tram?'#2878df':'#dc3545';const width=Math.max(44,Math.min(180,label.length*7+20));return L.divIcon({className:'vehicle-marker',html:'<div class="vehicle-chip" style="background:'+color+';color:#fff;border:1px solid '+color+';border-radius:6px;padding:5px 8px;box-shadow:0 2px 7px #17243a44;font-weight:800;white-space:nowrap">'+safe(label)+'</div>',iconSize:[width,28],iconAnchor:[width/2,14]});}
function vehiclePopup(v){const tram=String(v.vehicleType||v.type||'').toLowerCase().includes('tram')||String(v.vehicleService||'').toLowerCase().includes('tram');const delay=v.delay!=null?v.delay:(v.delayInSeconds!=null?Math.round(v.delayInSeconds/60):null);const next=v.nextStops||[];return '<div class="vehicle-popup"><b style="font-size:16px">'+(tram?'🚊 Tramwaj':'🚌 Autobus')+' '+safe(v.routeShortName)+'</b><div>Tabor: <b>'+safe(v.vehicleCode)+'</b></div><div>Brygada: <b>'+safe(brigadeFor(v))+'</b></div><div>Opóźnienie: <b>'+(delay==null?'brak danych':(delay>0?'+'+delay:delay)+' min')+'</b></div><hr><b>Następne przystanki</b>'+(next.length?next.slice(0,2).map(s=>'<div>'+safe(s.name||s.stopName)+' · '+safe(s.time||s.arrivalTime)+'</div>').join(''):'<div>Brak danych o kolejnych przystankach</div>')+'<hr><div>Końcowy: '+safe(v.destination||v.finalStop||'brak danych')+'</div><div>Przyjazd: '+safe(v.finalArrival||'brak danych')+'</div></div>';}
function refreshTooltips(){vehicles.forEach(v=>{const id=String(v.vehicleCode||'');if(markers[id]){markers[id].setIcon(vehicleIcon(v));markers[id].setPopupContent(vehiclePopup(v));}});}
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
document.addEventListener('click',function(event){const button=event.target.closest('[data-favorite]');if(button)toggleFavorite(button.getAttribute('data-favorite'));});
async function updateVehicles(){try{const response=await fetch('/api/live');if(!response.ok)throw new Error('API');const data=await response.json();vehicles=data.vehicles||[];document.getElementById('connection').textContent='GPS aktywny';document.getElementById('vehicleCountSettings').textContent='Widoczne pojazdy: '+vehicles.length;document.getElementById('lastUpdateSettings').textContent='Ostatnia aktualizacja: '+(data.lastUpdate||'brak danych');document.getElementById('dataStatus').textContent='Połączenie z danymi: aktywne';const active=new Set();vehicles.forEach(v=>{const id=String(v.vehicleCode||'');const lat=Number(v.lat),lon=Number(v.lon);if(!id||!Number.isFinite(lat)||!Number.isFinite(lon))return;active.add(id);if(!map)return;const label=labelFor(v);const icon=vehicleIcon(v);if(markers[id]){markers[id].setLatLng([lat,lon]);markers[id].setIcon(icon);markers[id].setPopupContent(vehiclePopup(v));}else{markers[id]=L.marker([lat,lon],{icon:icon}).addTo(map).bindPopup(vehiclePopup(v));}});if(map)Object.keys(markers).forEach(id=>{if(!active.has(id)){map.removeLayer(markers[id]);delete markers[id];}});renderActiveTable();if(document.getElementById('ulubione').classList.contains('active'))renderFavorites();}catch(error){document.getElementById('connection').textContent='Brak połączenia GPS';document.getElementById('vehicleCountSettings').textContent='Widoczne pojazdy: —';document.getElementById('lastUpdateSettings').textContent='Ostatnia aktualizacja: —';document.getElementById('dataStatus').textContent='Połączenie z danymi: błąd';}}
document.getElementById('mapLabelSummary').textContent=[labelSettings.line?'Linia':null,labelSettings.brigade?'Brygada':null,labelSettings.fleet?'Tabor':null].filter(Boolean).join(' · ')||'Etykiety wyłączone';
updateVehicles();setInterval(updateVehicles,20000);
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
