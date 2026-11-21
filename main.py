from fastapi import FastAPI, Header
from fastapi.responses import HTMLResponse, JSONResponse
import httpx
import time
import os
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

app = FastAPI(title="Transportie")

GPS_URL = "https://ckan2.multimediagdansk.pl/gpsPositions?v=2"
VEHICLE_DB_URL = "https://files.cloudgdansk.pl/d/otwarte-dane/ztm/baza-pojazdow.json?v=2"
STOPS_URL = "https://ckan.multimediagdansk.pl/dataset/c24aa637-3619-4dc2-a171-a23eec8f2172/resource/d3e96eb6-25ad-4d6c-8651-b1eb39155945/download/stopsingdansk.json"
STOPS_IN_TRIPS_URL = "https://ckan.multimediagdansk.pl/dataset/c24aa637-3619-4dc2-a171-a23eec8f2172/resource/3115d29d-b763-4af5-93f6-763b835967d6/download/stopsintrips.json"
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
_stops_in_trips_cache = []
_stops_in_trips_loaded_at = 0
_stop_times_cache = {}
_vehicle_db = {}
_vehicle_db_loaded_at = 0


@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
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
 .nav-brand{display:flex;align-items:center;gap:11px;padding:8px 8px 16px;margin-bottom:5px;border-bottom:1px solid #e8edf4;color:#17243a}.nav-brand-icon{width:39px;height:39px;display:grid;place-items:center;border-radius:12px;background:#eaf1ff;font-size:21px}.nav-brand strong{display:block;font-size:16px;letter-spacing:-.3px}.nav-brand small{display:block;margin-top:3px;color:#718096;font-size:10px}.nav-instagram{display:flex;align-items:center;gap:9px;margin-top:auto;padding:12px 10px;border-top:1px solid #e8edf4;color:#b04483!important;text-decoration:none;font-size:12px;font-weight:750}.instagram-glyph{width:25px;height:25px;display:block;flex:none}.nav-instagram{color:#c13584!important}body.map-search-active #menuToggle{display:none!important}nav{position:fixed;z-index:1200;left:16px;top:62px;bottom:16px;width:280px;transition:transform .22s ease;display:flex;flex-direction:column;gap:7px;padding:16px;background:rgba(255,255,255,.91);border:1px solid #fff;border-radius:0;box-shadow:var(--shadow);backdrop-filter:blur(18px);overflow:auto}
nav button,nav a,.primary,.secondary,.icon-button{border:0;border-radius:12px;padding:11px 15px;font-weight:650;font-size:13px;cursor:pointer;white-space:nowrap;text-decoration:none;display:inline-block}
nav button,nav a{background:transparent;color:#66758d;text-align:left;width:100%;padding:13px 14px}nav button.active{background:var(--blue-soft);color:var(--blue);box-shadow:inset 3px 0 var(--blue)}
body.menu-closed nav{transform:translateX(calc(-100% - 28px));pointer-events:none}body:not(.menu-closed) nav{transform:translateX(0);pointer-events:auto}body.menu-closed section:not(#mapa).active{margin-left:0;padding-left:30px}#menuToggle{position:fixed;z-index:1600;left:12px;top:12px;border:0;border-radius:11px;background:#fff;color:#263957;width:44px;height:44px;padding:0;font-size:21px;box-shadow:var(--shadow);cursor:pointer}#myLocation{position:fixed;z-index:1400;right:12px;left:auto;top:auto;bottom:12px;transform:none;display:grid;place-items:center;border:1px solid #fff;border-radius:12px;background:#1765d1;color:#fff;padding:0;box-shadow:0 4px 15px #123b7466;width:44px;height:44px;font-size:0;font-weight:800;cursor:pointer}#myLocation .loc-icon{display:grid;place-items:center;background:#fff;color:#1765d1;width:29px;height:29px;border-radius:9px;font-size:21px}#myLocation:disabled{opacity:.75;cursor:wait}#myLocation:active{transform:scale(.96)}#mapZoom{position:fixed;z-index:1600;right:12px;left:auto;top:112px;display:flex;flex-direction:column;overflow:hidden;border-radius:11px;background:#fff;box-shadow:var(--shadow);border:1px solid #e4eaf2}#mapZoom button{width:44px;height:42px;border:0;background:#fff;color:#263957;font-size:25px;font-weight:600;line-height:1;cursor:pointer}#mapZoom button+button{border-top:1px solid #e7edf5}#mapZoom button:active{background:#edf3ff}#locationStatus{position:fixed;z-index:1400;right:12px;left:auto;top:auto;bottom:62px;transform:none;background:#fff;padding:8px 10px;border:1px solid #dbe5f2;border-radius:11px;box-shadow:0 5px 22px #17345b25;font-size:12px;font-weight:600;display:block;max-width:230px;color:#29415f;pointer-events:none}#locationStatus:empty{display:none}main{padding:0;margin:0}
section{display:none}section.active{display:block}#mapa.active{display:block;position:fixed;inset:0;z-index:1}#mapVehicleSearchPanel{position:fixed;z-index:3000;top:22px;left:50%;transform:translateX(-50%);width:min(490px,calc(100vw - 210px));padding:8px;background:rgba(255,255,255,.97);border:1px solid #e3eaf4;border-radius:15px;box-shadow:0 8px 28px rgba(24,45,78,.2);backdrop-filter:blur(16px)}.map-search-input-wrap{display:flex;align-items:center;gap:9px;padding:0 10px;color:#52709a}.map-search-input-wrap>span{font-size:22px;line-height:1}.map-search-input-wrap input{flex:1;min-width:0;width:100%;border:0!important;outline:0!important;box-shadow:none!important;background:transparent;padding:10px 0;font-size:14px}.map-search-input-wrap button{border:0;background:#edf2f8;color:#52647e;border-radius:8px;width:29px;height:29px;font-size:20px;cursor:pointer;flex:none}#mapVehicleSearchResults{border-top:1px solid #e8edf4}#mapVehicleSearchResults button{cursor:pointer;border-radius:8px}#mapVehicleSearchResults button:hover{background:#edf4ff!important}#mapa .section-head{display:none}#mapa .map-layout{position:absolute;inset:0}#mapa .map-layout>.surface{position:absolute;inset:0;padding:0;border:0;border-radius:0;background:transparent;box-shadow:none}#mapa .map-side{position:absolute;z-index:600;right:16px;top:76px;width:230px;display:flex;flex-direction:column;gap:10px}#mapa .map-side .surface{background:rgba(255,255,255,.9);backdrop-filter:blur(14px);padding:13px;border-radius:16px}section:not(#mapa).active{position:relative;margin-left:312px;padding:88px 30px 30px}
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
.vehicle-marker{background:transparent!important;border:0!important;width:auto!important;height:auto!important}.vehicle-dot{width:10px;height:10px;border-radius:50%;border:2px solid #fff;box-shadow:0 1px 5px #17243a88}.stop-icon{width:17px;height:17px;border-radius:50%;font-size:0;border:2px solid #fff;background:#1765a8;box-shadow:0 1px 5px #142b4570}.stop-marker{background:transparent!important;border:0!important}.vehicle-marker:before,.vehicle-marker:after{display:none!important}.vehicle-chip{font-size:10px!important;padding:3px 5px!important;border-radius:5px!important;box-shadow:0 1px 4px #17243a33!important}.stop-marker{stroke:#fff;stroke-width:2;fill:#64748b;fill-opacity:.95}.stop-icon{display:block;width:10px;height:10px;border-radius:50%;background:#1765a8;border:2px solid #fff;box-shadow:0 1px 4px #142b4560;font-size:0}.leaflet-tooltip.stop-label{background:#fff;border:1px solid #b9cce0;border-radius:6px;color:#203b5c;padding:3px 6px;font-size:10px;font-weight:700;box-shadow:0 2px 6px #142b4525}.leaflet-tooltip.stop-label:before{display:none}.stop-popup{min-width:220px;font:13px/1.45 Inter,Arial,sans-serif}.stop-action{display:block;width:100%;margin-top:9px;padding:10px 12px;border:0;border-radius:9px;background:#1765d1;color:#fff;font-weight:800;font-size:13px;cursor:pointer}.departures-card{max-width:850px}.stop-search-results{display:grid;gap:7px;margin-top:12px}.stop-search-results button{padding:10px 12px;text-align:left;border:1px solid #e0e8f3;background:#fff;border-radius:10px;color:#243c5c;cursor:pointer}.departures-list{margin-top:12px}.departure-row{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px solid #edf1f6}.departure-fleet{display:inline-block;margin-left:7px;padding:2px 6px;border:0;border-radius:0;background:#eaf1ff;color:#245db3;font:inherit;font-size:10px;font-weight:800;white-space:nowrap;cursor:pointer}.departure-fleet:hover{background:#d9e8ff}.vehicle-popup{min-width:190px;font:13px/1.5 Inter,Arial,sans-serif;color:#17243a}.vehicle-popup hr{border:0;border-top:1px solid #e6ebf2;margin:7px 0}.course-stops{max-height:220px;overflow-y:auto;overscroll-behavior:contain;padding:3px 5px 3px 0;margin-top:7px}.course-stop{display:flex;align-items:flex-start;gap:8px;padding:7px 2px;border-bottom:1px solid #edf1f6}.course-stop-index{display:grid;place-items:center;flex:none;width:21px;height:21px;border-radius:50%;background:#eaf1ff;color:#245db3;font-size:10px;font-weight:800}.course-stop small{display:block;color:#718096;margin-top:2px;font-size:10px}
.leaflet-tooltip.vehicle-label:before{display:none}
.vehicle-detail-overlay{position:fixed;inset:0;z-index:5000;display:none;align-items:flex-end;justify-content:center;padding:18px;pointer-events:none}.vehicle-detail-overlay.open{display:flex;pointer-events:auto}.vehicle-detail-backdrop{position:absolute;inset:0;background:rgba(12,24,42,.35);backdrop-filter:blur(2px)}.vehicle-detail-card{position:relative;width:min(620px,100%);max-height:min(82vh,850px);overflow:auto;background:#fff;border:1px solid rgba(255,255,255,.9);border-radius:24px;box-shadow:0 24px 80px rgba(12,24,42,.28);padding:20px;color:#17243a;animation:vehicleCardIn .2s ease-out}.vehicle-detail-grabber{display:none}.vehicle-detail-close{position:absolute;right:15px;top:14px;width:36px;height:36px;border:0;border-radius:50%;background:#f0f3f8;color:#34445d;font-size:25px;line-height:1;cursor:pointer}.vehicle-detail-head{display:flex;align-items:center;gap:14px;padding:5px 46px 17px 0;border-bottom:1px solid #e9eef5}.vehicle-detail-line{display:grid;place-items:center;flex:none;min-width:66px;height:66px;padding:0 8px;border-radius:18px;background:#eaf1ff;color:#1c61c7;font-size:25px;font-weight:900}.vehicle-detail-type{font-size:11px;color:#718096;font-weight:750;text-transform:uppercase;letter-spacing:.7px}.vehicle-detail-title{font-size:22px;font-weight:850;letter-spacing:-.6px;margin-top:3px}.vehicle-detail-subtitle{font-size:12px;color:#718096;margin-top:4px}.vehicle-live-status{display:inline-flex;align-items:center;gap:6px;margin-top:9px;padding:5px 9px;border-radius:20px;background:#e9f8ef;color:#16834b;font-size:11px;font-weight:800}.vehicle-live-status:before{content:"";width:6px;height:6px;border-radius:50%;background:#20b56a}.vehicle-detail-section{padding:16px 0 2px}.vehicle-detail-section h3{margin:0 0 10px;font-size:13px;color:#66758d;text-transform:uppercase;letter-spacing:.65px}.vehicle-detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.vehicle-detail-field{min-width:0;padding:11px 12px;border:1px solid #edf1f6;border-radius:13px;background:#f9fbfe}.vehicle-detail-field span{display:block;color:#78869b;font-size:10px;font-weight:700;margin-bottom:5px}.vehicle-detail-field b{display:block;font-size:13px;overflow-wrap:anywhere}.vehicle-delay{color:#1765d1}.vehicle-detail-stops{position:relative;padding:3px 5px 3px 0;margin-top:7px;max-height:260px;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;scrollbar-color:#c7d5e8 transparent}.vehicle-detail-stops .course-stop{display:flex;align-items:center;gap:9px;padding:9px 3px;border-bottom:1px solid #edf1f6}.course-stop-marker{position:relative;display:flex;align-items:center;justify-content:center;align-self:stretch;flex:none;width:16px;min-height:38px;margin:0 2px}.course-stop-marker:before{content:'';position:absolute;top:-10px;bottom:-10px;left:50%;width:2px;transform:translateX(-50%);background:#a9bdd8}.course-stop-marker:after{content:'';position:relative;z-index:1;width:9px;height:9px;border:2px solid #fff;border-radius:50%;background:#2874d0;box-shadow:0 0 0 1px #2874d0}.course-stop:first-child .course-stop-marker:before{top:50%}.course-stop:last-child .course-stop-marker:before{bottom:50%}.course-stop-name{min-width:0;flex:1}.course-stop-name b{display:block;font-size:12px}.course-stop-number{display:inline-block;margin-right:5px;color:#1765d1;font-size:11px;font-weight:900}.course-stop-name small{display:block;color:#718096;margin-top:3px;font-size:10px}.course-stop{max-height:90px;overflow:hidden;transition:max-height .65s ease,opacity .65s ease,padding .65s ease,border-color .65s ease}.course-stop.passed{max-height:0!important;opacity:0;padding-top:0!important;padding-bottom:0!important;border-color:transparent!important}.course-stop-time{flex:none;display:flex;align-items:center;gap:5px;font-size:11px;font-weight:800;color:#344a68;white-space:nowrap}.course-stop-time s{color:#98a3b3;font-weight:600}.course-stop-time strong{color:#1765d1}.vehicle-detail-empty{padding:12px;border-radius:12px;background:#f7f9fc;color:#718096;font-size:12px;line-height:1.5}.vehicle-technical-list{display:grid;grid-template-columns:1fr 1fr;gap:7px}.vehicle-technical-list div{padding:8px 10px;background:#f8fafc;border-radius:9px;min-width:0}.vehicle-technical-list small{display:block;color:#7b8798;font-size:10px}.vehicle-technical-list b{display:block;margin-top:3px;font-size:11px;overflow-wrap:anywhere}@keyframes vehicleCardIn{from{transform:translateY(18px);opacity:.7}to{transform:translateY(0);opacity:1}}
@media(min-width:850px){.vehicle-detail-overlay{align-items:center;justify-content:flex-end;padding:18px 22px}.vehicle-detail-card{width:min(510px,calc(100vw - 340px));max-height:calc(100vh - 36px);border-radius:22px}}
@media(max-width:520px){.vehicle-detail-overlay{padding:0;align-items:flex-end}.vehicle-detail-backdrop{background:rgba(12,24,42,.32)}.vehicle-detail-card{width:100%;max-height:80dvh;border-radius:22px 22px 0 0;padding:12px 16px calc(20px + env(safe-area-inset-bottom));animation:vehicleCardIn .2s ease-out}.vehicle-detail-grabber{display:block;width:38px;height:4px;border-radius:8px;background:#d8dee8;margin:0 auto 12px}.vehicle-detail-close{top:12px;right:15px}.vehicle-detail-head{gap:11px;padding-top:3px}.vehicle-detail-line{min-width:58px;height:58px;border-radius:15px;font-size:22px}.vehicle-detail-title{font-size:19px}.vehicle-detail-grid{gap:7px}.vehicle-detail-field{padding:9px}.vehicle-detail-field b{font-size:12px}.vehicle-technical-list{grid-template-columns:1fr 1fr}}


.settings-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
.check{display:flex;gap:9px;align-items:center;padding:12px;background:#fff;border:1px solid var(--line);border-radius:12px;font-size:13px}
.check input{accent-color:var(--blue)}
.small-note{font-size:12px;color:var(--muted);line-height:1.5;margin-top:12px}
@media(max-width:850px){
 #map{height:100dvh;min-height:100dvh}
 #mapa .map-side{width:190px}
}

/* Czynaczas-inspired dark vehicle card */
.vehicle-detail-overlay{padding:0;align-items:flex-end;justify-content:center}
.vehicle-detail-backdrop{background:rgba(0,0,0,.16);backdrop-filter:none}
.vehicle-detail-card{width:100%;max-width:none;max-height:53dvh;overflow-y:auto;overscroll-behavior:contain;background:#111;color:#eee;border:0;border-radius:20px 20px 0 0;padding:12px 0 calc(16px + env(safe-area-inset-bottom));box-shadow:0 -10px 35px #0007}
.vehicle-detail-grabber{display:block;width:38px;height:4px;border-radius:8px;background:#555;margin:0 auto 12px}
.vehicle-detail-close{top:10px;right:14px;background:transparent;color:#eee;font-size:28px;z-index:2}
.vehicle-detail-head{gap:12px;padding:4px 58px 12px 16px;border:0}
.vehicle-detail-line{min-width:58px;height:48px;border-radius:8px;background:#008e68;color:#fff;font-size:23px}
.vehicle-detail-type{color:#aaa;font-size:10px}
.vehicle-detail-title{color:#f4f4f4;font-size:19px}
.vehicle-live-status{margin-top:5px;background:#087b25;color:#dfffe5;font-size:11px}
.vehicle-detail-section h3{color:#999}
.vehicle-detail-grid{gap:7px}
.vehicle-detail-field{background:#191919;border:1px solid #303030;border-radius:9px;color:#eee}
.vehicle-detail-field span{color:#999}.vehicle-detail-field b{color:#eee}
.vehicle-detail-stops{max-height:none;overflow:visible;padding:2px 0;margin-top:4px}
.vehicle-detail-stops .course-stop{min-height:58px;gap:12px;padding:9px 0;border-bottom:1px solid #292929}
.course-stop-marker{width:22px;min-height:44px}.course-stop-marker:before{width:3px;background:#00a56a}
.course-stop-marker:after{width:13px;height:13px;background:#00a56a;box-shadow:0 0 0 2px #111,0 0 0 3px #00a56a}
.course-stop-name b{color:#e7e7e7;font-size:14px}.course-stop-name small{color:#999}
.course-stop-time{color:#ddd;font-size:13px}.course-stop-time s{color:#aaa}.course-stop-time strong{color:#00c477}
.vehicle-detail-empty{background:#1b1b1b;color:#aaa}
@media(min-width:850px){.vehicle-detail-overlay{align-items:flex-end;justify-content:center;padding:0}.vehicle-detail-card{width:min(100%,850px);max-height:55vh;border-radius:20px 20px 0 0}}
@media(max-width:520px){.vehicle-detail-overlay{padding:0}.vehicle-detail-card{width:100%;max-height:53dvh;border-radius:20px 20px 0 0;padding:10px 0 calc(14px + env(safe-area-inset-bottom))}.vehicle-detail-close{top:8px;right:12px}.vehicle-detail-head{padding:2px 52px 10px 16px}}


.vehicle-detail-meta{display:flex;flex-wrap:wrap;align-items:center;gap:7px;padding:0 16px 10px;color:#bdbdbd;font-size:12px}
.vehicle-detail-meta strong{color:#eee}
.vehicle-detail-tabs{display:flex;gap:0;border-bottom:1px solid #292929;margin:0 0 8px;position:sticky;top:-12px;background:#111;z-index:3}
.vehicle-detail-tabs button{flex:1;min-width:0;padding:13px 4px 11px;border:0;border-bottom:3px solid transparent;background:transparent;color:#888;font-size:clamp(10px,2.7vw,14px);font-weight:750;white-space:nowrap;cursor:pointer}
.vehicle-detail-tabs button.active{color:#00a85a;border-bottom-color:#00a85a}
.vehicle-tab-panel{display:none;padding:0 16px 12px}
.vehicle-tab-panel.active{display:block}
.vehicle-brigade-note{padding:12px;border:1px solid #303030;border-radius:10px;background:#191919;color:#bbb;font-size:12px;line-height:1.5;margin-bottom:9px}

@media(max-width:520px){#mapVehicleSearchPanel{top:74px;left:19px;right:19px;transform:none;width:auto;padding:6px;border-radius:12px}.map-search-input-wrap input{font-size:13px}.map-search-input-wrap{gap:7px}
 #mapZoom{top:154px}#myLocation{right:12px;left:auto;top:auto;bottom:12px;width:44px;height:44px;min-width:44px;min-height:44px;padding:0;font-size:0}#myLocation .loc-icon{width:29px;height:29px;font-size:21px}#locationStatus{right:12px;left:auto;bottom:62px;max-width:calc(100vw - 30px);text-align:center}
 header{top:10px;right:8px}
 .live-pill{padding:7px 9px;font-size:10px}
 nav{position:fixed;z-index:1200;left:7px;top:64px;bottom:7px;right:auto;width:230px;height:auto;flex-direction:column;justify-content:flex-start;align-items:stretch;padding:9px 7px;gap:6px;border-radius:0;overflow-y:auto}
 nav button{width:100%;flex:none;text-align:left;padding:12px 8px;font-size:11px;white-space:normal}
 nav button.active{box-shadow:inset 3px 0 var(--blue)}
 #mapa .map-side{top:58px;right:7px;width:135px;gap:6px}
 #mapa .map-side .surface{padding:8px;border-radius:11px}
 #mapa .map-side .stat strong{font-size:17px}
 #mapa .map-side .stat span{font-size:9px}
 #mapa .map-side .surface:nth-child(3){display:none}
 section:not(#mapa).active{margin-left:230px;padding:68px 9px 20px}
 section:not(#mapa).active .section-head{display:block}
 section:not(#mapa).active .surface{padding:10px}
 section:not(#mapa).active table{font-size:11px}
}

/* Responsywne panele tabel — bez przewijania poziomego */
@media(max-width:850px){
 section:not(#mapa).active{
  margin-left:0!important;
  width:100%!important;
  max-width:100vw!important;
  min-width:0!important;
  padding:76px 12px 22px!important;
  overflow-x:hidden!important;
 }
 section:not(#mapa).active .surface{
  width:100%;max-width:100%;min-width:0;padding:12px!important;
 }
 section:not(#mapa).active .section-head{margin:0 0 12px}
 section:not(#mapa).active .toolbar{width:100%;gap:8px}
 section:not(#mapa).active .toolbar input{width:100%;max-width:none;min-width:0;flex:1 1 100%}
 section:not(#mapa).active .toolbar button{flex:1 1 auto}
 .table-wrap{width:100%;max-width:100%;overflow-x:hidden}
 .table-wrap table{width:100%;min-width:0!important;table-layout:fixed;font-size:12px}
 .table-wrap th,.table-wrap td{padding:10px 6px;overflow-wrap:anywhere;word-break:break-word}
 .table-wrap th{font-size:9px;letter-spacing:0}
}
@media(max-width:520px){
 section:not(#mapa).active{padding:72px 10px 18px!important}
 section:not(#mapa).active .surface{padding:10px!important;border-radius:14px}
 section:not(#mapa).active h2{font-size:19px}
 section:not(#mapa).active .hint{font-size:11px;line-height:1.4}
 /* Pokaż także przewoźnika; ukryj tylko kolumnę akcji, by zmieścić dane */
 #activeTable .table-wrap th:nth-child(5),#activeTable .table-wrap td:nth-child(5),
 #lineResults .table-wrap th:nth-child(5),#lineResults .table-wrap td:nth-child(5){display:none}
 #activeTable .table-wrap th:nth-child(1),#lineResults .table-wrap th:nth-child(1){width:19%}
 #activeTable .table-wrap th:nth-child(2),#lineResults .table-wrap th:nth-child(2){width:14%}
 #activeTable .table-wrap th:nth-child(3),#lineResults .table-wrap th:nth-child(3){width:19%}
 #activeTable .table-wrap th:nth-child(4),#lineResults .table-wrap th:nth-child(4){width:48%}
 #activeTable .table-wrap th,#lineResults .table-wrap th{padding:6px 3px;font-size:8px}
 #activeTable .table-wrap td,#lineResults .table-wrap td{font-size:10px;padding:6px 3px;line-height:1.2}
 #activeTable .table-wrap,#lineResults .table-wrap{border-radius:10px}
 #activeTable .tag,#lineResults .tag{padding:3px 5px;font-size:10px}
}


/* Final mobile sizing overrides */
.vehicle-detail-overlay{padding:0;align-items:flex-end;justify-content:center}
.vehicle-detail-card{width:100%;max-width:none;max-height:53dvh;background:#111;color:#eee;border:0;border-radius:20px 20px 0 0;padding:10px 0 calc(14px + env(safe-area-inset-bottom))}
@media(min-width:850px){.vehicle-detail-overlay{padding:0;align-items:flex-end;justify-content:center}.vehicle-detail-card{width:min(100%,850px);max-height:55vh;border-radius:20px 20px 0 0}}
@media(max-width:520px){.vehicle-detail-card{max-height:53dvh;width:100%;border-radius:20px 20px 0 0;padding:10px 0 calc(14px + env(safe-area-inset-bottom))}}


/* Prostokątna karta pojazdu */
.vehicle-detail-overlay{padding:0;align-items:flex-end;justify-content:center}
.vehicle-detail-card{width:100%;max-width:850px;height:58dvh;max-height:72dvh;min-height:360px;border-radius:0;background:#111;color:#eee;border:0;overflow-y:auto;padding:12px 0 calc(16px + env(safe-area-inset-bottom))}
.vehicle-detail-line{border-radius:3px}
.vehicle-duty-courses{display:grid;gap:12px;padding:4px 0 12px}
.vehicle-duty-course{border:1px solid #303030;background:#191919;padding:11px 12px;border-radius:3px}
.vehicle-duty-course-head{display:flex;justify-content:space-between;gap:10px;align-items:center;color:#eee;font-weight:800;font-size:13px;padding-bottom:8px;border-bottom:1px solid #303030}
.vehicle-duty-course-head small{color:#9ca3af;font-weight:600;white-space:nowrap}
.vehicle-duty-stop{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;padding:7px 0;border-bottom:1px solid #292929;color:#ddd;font-size:12px}
.vehicle-duty-stop:last-child{border-bottom:0}
.vehicle-duty-stop time{color:#c8f7dc;font-weight:800;font-variant-numeric:tabular-nums}
.vehicle-duty-stop small{color:#8d969f;margin-left:5px}
@media(min-width:850px){.vehicle-detail-card{height:62vh;max-height:75vh;width:min(850px,calc(100vw - 300px));border-radius:0}}
@media(max-width:520px){.vehicle-detail-card{height:58dvh;max-height:72dvh;min-height:350px;width:100%;border-radius:0;padding:10px 0 calc(14px + env(safe-area-inset-bottom))}}

/* Stabilny widok mobilny: bez poziomego przesuwania i komunikatow lokalizacji */
html,body{width:100%;max-width:100%;overflow-x:hidden;overscroll-behavior-x:none}
#myLocation{width:52px;height:52px;min-width:52px;min-height:52px;border:0;border-radius:50%;background:#fff;color:#1677e8;box-shadow:0 4px 16px rgba(20,50,90,.22);display:grid;place-items:center;padding:0}
#myLocation .loc-icon{width:32px;height:32px;border-radius:0;background:transparent;color:#1677e8;display:grid;place-items:center}
#myLocation .loc-icon svg{display:block;width:30px;height:30px}
#myLocation:disabled{opacity:.7}
#locationStatus{display:none!important}
.vehicle-detail-overlay{width:100%;max-width:100vw;overflow-x:hidden}
.vehicle-detail-card{width:100%;max-width:100vw;overflow-x:hidden;overscroll-behavior-x:none;touch-action:pan-y}
@media(max-width:520px){.vehicle-detail-card{width:100vw;max-width:100vw;min-width:0;overflow-x:hidden;touch-action:pan-y}}


/* Motyw jasny/ciemny Transportie */
:root{color-scheme:light}
:root[data-theme="dark"]{color-scheme:dark;--bg:#0c0d0f;--surface:rgba(25,26,29,.96);--ink:#f1f2f4;--muted:#a0a4ad;--line:#303238;--blue:#70a7ff;--blue-soft:#202d40;--shadow:0 12px 34px rgba(0,0,0,.34)}
:root[data-theme="dark"] body{background:#0c0d0f;color:var(--ink)}
:root[data-theme="dark"] .leaflet-tile{filter:none!important}
:root[data-theme="dark"] nav,:root[data-theme="dark"] .surface,:root[data-theme="dark"] .card,:root[data-theme="dark"] .settings-grid,:root[data-theme="dark"] .theme-setting{background:#191a1d!important;color:var(--ink);border-color:#303238!important}
:root[data-theme="dark"] #mapa .map-side .surface{background:rgba(25,26,29,.94)!important;color:var(--ink)}
:root[data-theme="dark"] .check{background:#222429;color:var(--ink);border-color:#383b42}
:root[data-theme="dark"] .table-wrap{background:#191a1d;border-color:#383b42}
:root[data-theme="dark"] .primary{color:#fff}
:root[data-theme="dark"] .section-head h2{color:var(--ink)}
:root[data-theme="dark"] .empty{color:#a0a4ad}
:root[data-theme="dark"] .departure-row,:root[data-theme="dark"] .course-stop{border-color:#34373e}
:root[data-theme="dark"] .departure-fleet{background:#26384f;color:#a9caff}
:root[data-theme="dark"] #menuToggle{background:#202226;color:#f1f2f4;border:1px solid #41444b}

:root[data-theme="dark"] input,:root[data-theme="dark"] select,:root[data-theme="dark"] textarea{background:#222429!important;color:#f1f2f4!important;border-color:#41444b!important}
:root[data-theme="dark"] input::placeholder,:root[data-theme="dark"] textarea::placeholder{color:#9298a3}
:root[data-theme="dark"] table,:root[data-theme="dark"] th,:root[data-theme="dark"] td{color:var(--ink);border-color:#35383f!important}
:root[data-theme="dark"] th{background:#222429!important}
:root[data-theme="dark"] .toolbar button,:root[data-theme="dark"] .secondary{background:#292c32;color:#f1f2f4;border-color:#41444b}
:root[data-theme="dark"] nav button{color:#d7d9de}
:root[data-theme="dark"] nav button.active{background:#263c32;color:#56d49a}
:root[data-theme="dark"] .vehicle-popup,:root[data-theme="dark"] .leaflet-popup-content-wrapper,:root[data-theme="dark"] .leaflet-popup-tip{background:#202226;color:#f1f2f4}
:root[data-theme="dark"] .leaflet-control-zoom a{background:#202226;color:#f1f2f4;border-color:#41444b}
:root[data-theme="dark"] .vehicle-detail-card{background:#111!important;color:#eee!important}
:root[data-theme="dark"] .vehicle-detail-card input,:root[data-theme="dark"] .vehicle-detail-card select{background:#222!important;color:#eee!important}
.theme-setting{margin:18px 0;padding:16px;border:1px solid var(--line);border-radius:14px;background:var(--surface)}
.theme-setting h3{margin:0 0 5px;font-size:16px}
.theme-options{display:flex;gap:9px;flex-wrap:wrap;margin-top:12px}
.theme-options button{border:1px solid var(--line);background:var(--bg);color:var(--ink);border-radius:11px;padding:10px 14px;font-weight:700;cursor:pointer}
.theme-options button.selected{border-color:var(--blue);background:var(--blue-soft);color:var(--blue)}
#fleetDatabaseTable{margin-top:12px}
#fleetDatabaseTable .table-wrap{overflow-x:auto}
@media(max-width:520px){.theme-options button{flex:1 1 30%;padding:10px 7px;font-size:12px}}


/* Pelny ciemny motyw — bez bialych powierzchni i komorek tabel */
:root[data-theme="dark"] body{background:#0b0c0e!important;color:#f1f2f4!important}
:root[data-theme="dark"] main,:root[data-theme="dark"] section:not(#mapa){background:#0b0c0e;color:#f1f2f4}
:root[data-theme="dark"] .surface,:root[data-theme="dark"] .card,:root[data-theme="dark"] .table-wrap,:root[data-theme="dark"] .stat,:root[data-theme="dark"] .settings-grid,:root[data-theme="dark"] .theme-setting{background:#191a1d!important;color:#f1f2f4!important;border-color:#303238!important}
:root[data-theme="dark"] table,:root[data-theme="dark"] thead,:root[data-theme="dark"] tbody,:root[data-theme="dark"] tr,:root[data-theme="dark"] td{background:#191a1d!important;color:#f1f2f4!important}
:root[data-theme="dark"] th{background:#24262b!important;color:#c4c8d0!important}
:root[data-theme="dark"] td{border-top:1px solid #35383f!important}
:root[data-theme="dark"] tbody tr:hover,:root[data-theme="dark"] tbody tr:hover td{background:#25282e!important}
:root[data-theme="dark"] .tag{background:#26384f!important;color:#a9caff!important}
:root[data-theme="dark"] .check{background:#222429!important;color:#f1f2f4!important;border-color:#383b42!important}
:root[data-theme="dark"] #mapVehicleSearchPanel{background:rgba(25,26,29,.97)!important;border-color:#383b42!important}
:root[data-theme="dark"] .map-search-input-wrap,:root[data-theme="dark"] .map-search-input-wrap input{color:#f1f2f4!important}
:root[data-theme="dark"] .map-search-input-wrap button{background:#30343b!important;color:#f1f2f4!important}
:root[data-theme="dark"] #mapBrand{background:rgba(25,26,29,.95)!important;color:#f1f2f4!important;border-color:#383b42!important}
:root[data-theme="dark"] #mapZoom,:root[data-theme="dark"] #mapZoom button{background:#202226!important;color:#f1f2f4!important;border-color:#41444b!important}
:root[data-theme="dark"] #myLocation{background:#fff!important;color:#1677e8!important}
:root[data-theme="dark"] .leaflet-popup-content-wrapper,:root[data-theme="dark"] .leaflet-popup-tip{background:#202226!important;color:#f1f2f4!important}
:root[data-theme="dark"] .leaflet-control-zoom a{background:#202226!important;color:#f1f2f4!important;border-color:#41444b!important}
:root[data-theme="dark"] .nav-brand{color:#f1f2f4;border-color:#383b42}
:root[data-theme="dark"] .nav-brand small{color:#a0a4ad}
:root[data-theme="dark"] .nav-instagram{border-color:#383b42}
:root[data-theme="dark"] .live-pill{background:#173b2c;color:#7de0ae}
:root[data-theme="dark"] .vehicle-label{background:#202226;color:#f1f2f4;border-color:#41444b}
:root[data-theme="dark"] .vehicle-detail-card{background:#111!important;color:#eee!important}

/* Mobilne menu na dole ekranu */
@media(max-width:850px){
  nav{position:fixed!important;z-index:5000!important;left:0!important;right:0!important;top:auto!important;bottom:0!important;width:100%!important;height:calc(70px + env(safe-area-inset-bottom))!important;min-height:70px;max-height:90px;padding:6px 5px calc(6px + env(safe-area-inset-bottom))!important;display:flex!important;flex-direction:row!important;align-items:stretch!important;gap:3px!important;overflow-x:auto!important;overflow-y:hidden!important;border:1px solid var(--line)!important;border-bottom:0!important;border-radius:16px 16px 0 0!important;background:rgba(255,255,255,.97)!important;box-shadow:0 -7px 26px rgba(0,0,0,.12)!important;backdrop-filter:blur(18px)}
  nav .nav-brand,nav .nav-instagram{display:none!important}
  nav button,nav a{display:flex!important;flex:1 0 72px!important;min-width:72px!important;width:auto!important;height:100%!important;align-items:center!important;justify-content:center!important;flex-direction:column!important;gap:3px!important;padding:6px 4px!important;border-radius:10px!important;text-align:center!important;white-space:normal!important;line-height:1.12!important;font-size:10px!important;font-weight:700!important}
  nav button.active{box-shadow:inset 0 2px var(--blue)!important}
  body.menu-closed nav,body:not(.menu-closed) nav{transform:none!important;pointer-events:auto!important}
  #menuToggle{display:none!important}
  section:not(#mapa).active,body.menu-closed section:not(#mapa).active{margin-left:0!important;padding:78px 16px calc(100px + env(safe-area-inset-bottom))!important}
  #myLocation{bottom:calc(84px + env(safe-area-inset-bottom))!important}
  #mapa .map-side{bottom:calc(84px + env(safe-area-inset-bottom))}
}
@media(max-width:850px){
  :root[data-theme="dark"] nav{background:rgba(20,21,24,.98)!important;border-color:#303238!important;box-shadow:0 -7px 26px rgba(0,0,0,.45)!important}
  :root[data-theme="dark"] nav button{color:#c7cbd3!important;background:transparent!important}
  :root[data-theme="dark"] nav button.active{background:#202d40!important;color:#8bb9ff!important}
}


/* Stabilne kafelki OSM bez klucza API CARTO; filtr tylko dla warstwy ciemnej */
.transportie-dark-tiles{filter:invert(1) hue-rotate(180deg) brightness(.78) contrast(.88) saturate(.78)!important}
:root[data-theme="dark"] .transportie-dark-tiles{filter:invert(1) hue-rotate(180deg) brightness(.78) contrast(.88) saturate(.78)!important}
:root[data-theme="light"] .transportie-dark-tiles{filter:none!important}
.leaflet-container{background:#202426!important}
.leaflet-tile{max-width:none!important}
/* Mapa zachowuje oryginalne kafelki i kolory */
#mapa,#mapa .map-layout,#mapa .map-layout>.surface,#map{background:#e8e5dc}
.leaflet-container{background:#e8e5dc}
:root[data-theme="dark"] #mapa .map-layout>.surface{background:transparent!important}
:root[data-theme="dark"] .leaflet-tile{filter:none!important}
@media(max-width:850px){
  #mapa .map-side{top:76px;right:12px;bottom:auto;max-height:38vh;overflow:auto}
  #mapVehicleSearchPanel{top:78px;width:calc(100vw - 92px);max-width:490px}
  #mapZoom{top:145px}
  #map{height:100dvh;min-height:100dvh}
}


/* Mapa w stylu czynaczas.pl */
#mapa,#mapa .map-layout,#mapa .map-layout>.surface,#map,.leaflet-container{background:#17191a!important}
.leaflet-tile{filter:none!important}
.stop-icon{width:27px!important;height:27px!important;display:grid!important;place-items:center!important;border-radius:50%!important;background:#07996d!important;border:2px solid #d8fff0!important;color:#fff!important;box-shadow:0 2px 8px #0008!important}
.stop-icon svg{width:17px;height:17px;display:block}
.leaflet-tooltip.stop-label{background:#202426!important;color:#f1f3f4!important;border:1px solid #59615e!important;border-radius:5px!important;box-shadow:0 2px 8px #0008!important}
.vehicle-chip{border-radius:16px!important;padding:4px 8px!important;font-size:11px!important;box-shadow:0 2px 8px #0009!important}
#mapTools{position:fixed;z-index:1600;right:12px;top:50%;transform:translateY(-50%);display:flex;flex-direction:column;overflow:hidden;border-radius:9px;background:#171819;border:1px solid #3a3c3d;box-shadow:0 4px 18px #0008}
#mapTools button{width:48px;height:48px;border:0;border-bottom:1px solid #454748;background:#171819;color:#e5e7e8;font-size:23px;cursor:pointer}
#mapTools button:last-child{border-bottom:0}
#mapTools button:active,#mapTools button.tool-off{background:#303536;color:#9ba3a5}
#mapZoom{top:auto!important;bottom:calc(88px + env(safe-area-inset-bottom))!important;right:12px!important;background:#171819!important;border:1px solid #3a3c3d!important;box-shadow:0 4px 18px #0008!important}
#mapZoom button{background:#171819!important;color:#eee!important;border-color:#454748!important}
#myLocation{bottom:calc(190px + env(safe-area-inset-bottom))!important;right:12px!important}
#mapVehicleSearchPanel{background:rgba(31,33,34,.96)!important;border-color:#424647!important}
#mapVehicleSearchPanel input{color:#f1f3f4!important}
.map-search-input-wrap{color:#c5cbcd!important}
#mapVehicleSearchResults{color:#f1f3f4}
#mapVehicleSearchResults button{color:#f1f3f4!important}
.bottom-nav{display:none}
@media(max-width:850px){
 nav{display:none!important}
 body.mobile-menu-open nav{display:flex!important;position:fixed!important;z-index:5100!important;left:8px!important;right:8px!important;top:12px!important;bottom:calc(82px + env(safe-area-inset-bottom))!important;width:auto!important;height:auto!important;max-height:none!important;min-height:0!important;flex-direction:column!important;align-items:stretch!important;overflow:auto!important;padding:12px!important;border:1px solid #3b3e40!important;border-radius:14px!important;background:rgba(25,27,28,.98)!important;box-shadow:0 12px 36px #0009!important}
 body.mobile-menu-open nav .nav-brand{display:flex!important}
 body.mobile-menu-open nav .nav-instagram{display:flex!important}
 body.mobile-menu-open nav button,body.mobile-menu-open nav a{display:flex!important;flex:0 0 auto!important;min-width:0!important;width:100%!important;height:auto!important;flex-direction:row!important;justify-content:flex-start!important;padding:12px!important;font-size:13px!important;color:#e9ecec!important}
 body.mobile-menu-open nav button.active{background:#173e32!important;color:#65d8a8!important}
 .bottom-nav{position:fixed;z-index:5000;left:0;right:0;bottom:0;height:calc(72px + env(safe-area-inset-bottom));padding:5px 4px calc(5px + env(safe-area-inset-bottom));display:flex;align-items:stretch;justify-content:space-around;gap:2px;background:#242627;border-top:1px solid #3b3e40;box-shadow:0 -5px 22px #0005}
 .bottom-nav button{flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;border:0;border-radius:8px;background:transparent;color:#aeb3b5;font-size:22px;cursor:pointer}
 .bottom-nav button small{font-size:10px;line-height:1.1;color:inherit}
 .bottom-nav button.active{color:#16a36b}
 #mapTools{right:10px;top:46%;transform:translateY(-50%)}
 #mapTools button{width:43px;height:43px}
 #mapZoom{bottom:calc(83px + env(safe-area-inset-bottom))!important;right:10px!important}
 #mapZoom button{width:43px;height:39px}
 #myLocation{bottom:calc(176px + env(safe-area-inset-bottom))!important;right:10px!important;width:44px!important;height:44px!important;min-width:44px!important;min-height:44px!important}
 #mapVehicleSearchPanel{top:78px;width:calc(100vw - 92px);max-width:490px}
 #mapa .map-side{display:none!important}
 body.mobile-menu-open #mapTools,body.mobile-menu-open #mapZoom,body.mobile-menu-open #myLocation{pointer-events:none;opacity:.35}
}
#mapTools{display:flex!important}\n#mapTools button{border:0!important}
.vehicle-duty-source{color:#8eaaa0;font-size:11px;font-weight:700;padding:4px 0 9px}
#odjazdy .departures-card{min-height:55vh}
#odjazdy .stop-search-results button{width:100%;text-align:left;padding:11px 12px;border:0;border-bottom:1px solid var(--line);background:transparent;color:var(--ink);font-size:14px}
#odjazdy .stop-search-results button:active{background:var(--blue-soft)}

/* Przystanki na mapie — styl inspirowany widokiem czynaczas.pl */
.stop-marker{background:transparent!important;border:0!important;width:48px!important;height:48px!important}
.stop-icon{display:grid!important;place-items:center;width:44px!important;height:44px!important;border-radius:50%!important;background:#009b70!important;border:2px solid rgba(255,255,255,.95)!important;color:#fff!important;box-shadow:0 2px 7px rgba(0,0,0,.5)!important}
.stop-icon svg{display:block;width:25px;height:25px}
.leaflet-tooltip.stop-label{background:transparent!important;border:0!important;border-radius:0!important;color:#2876d0!important;padding:1px 3px!important;font-size:12px!important;line-height:1.15!important;font-weight:800!important;text-align:center!important;white-space:nowrap!important;text-shadow:0 1px 2px rgba(0,0,0,.9)!important;box-shadow:none!important}
.leaflet-tooltip.stop-label:before{display:none!important}
.leaflet-tooltip.stop-label .stop-platform{display:block;font-size:11px;font-weight:800;letter-spacing:.2px}

.schedule-head{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin:8px 0 14px}.schedule-head h3{margin:0}.schedule-head small{color:var(--muted)}.schedule-direction{margin:14px 0}.schedule-direction h4{margin:8px 0;color:var(--text)}.schedule-course{border-bottom:1px solid var(--border);padding:0}.schedule-course summary{display:flex;align-items:center;gap:12px;list-style:none;cursor:pointer;padding:12px 4px}.schedule-course summary::-webkit-details-marker{display:none}.schedule-course summary>b{font-size:16px;color:var(--accent);min-width:48px}.schedule-course summary span{flex:1}.schedule-course summary small{color:var(--muted)}.schedule-stop-list{padding:0 8px 10px 16px}.schedule-stop-row{display:flex;justify-content:space-between;gap:12px;padding:7px 0;border-bottom:1px solid var(--border);font-size:13px}.schedule-stop-row small{color:var(--muted)}.schedule-stop-row b{white-space:nowrap}

/* Finalne style przystanków — nie nadpisywać starszymi regułami */
.leaflet-marker-icon.stop-marker,.leaflet-div-icon.stop-marker{background:transparent!important;border:0!important;width:48px!important;height:48px!important;overflow:visible!important;padding:0!important}.leaflet-marker-icon.stop-marker .stop-icon{display:flex!important;align-items:center!important;justify-content:center!important;position:absolute!important;left:2px!important;top:2px!important;width:44px!important;height:44px!important;min-width:44px!important;min-height:44px!important;box-sizing:border-box!important;border-radius:50%!important;background:#009b70!important;border:2px solid #fff!important;color:#fff!important;box-shadow:0 2px 7px rgba(0,0,0,.55)!important;opacity:1!important;visibility:visible!important}
.leaflet-marker-icon.stop-marker .stop-icon{display:grid!important;place-items:center!important;width:44px!important;height:44px!important;box-sizing:border-box!important;border-radius:50%!important;background:#009b70!important;border:2px solid #fff!important;color:#fff!important;box-shadow:0 2px 7px rgba(0,0,0,.55)!important}
.leaflet-marker-icon.stop-marker .stop-icon svg{display:block!important;width:25px!important;height:25px!important}
.leaflet-tooltip.stop-label{background:transparent!important;border:0!important;border-radius:0!important;color:#2876d0!important;padding:1px 3px!important;font-size:12px!important;line-height:1.15!important;font-weight:800!important;text-align:center!important;white-space:nowrap!important;text-shadow:0 1px 2px rgba(0,0,0,.95)!important;box-shadow:none!important}
.leaflet-tooltip.stop-label:before{display:none!important}
.leaflet-tooltip.stop-label .stop-platform{display:block!important;font-size:11px!important;font-weight:800!important}

/* Czytelne, klikalne ikony przystanków — zielony znacznik z białym autobusem. */
.leaflet-marker-icon.stop-marker{width:44px!important;height:44px!important;margin-left:-22px!important;margin-top:-22px!important;background:transparent!important;border:0!important;padding:0!important;overflow:visible!important;opacity:1!important;visibility:visible!important;pointer-events:auto!important;}
.leaflet-tooltip.stop-label{z-index:1000!important;white-space:nowrap!important;}
.leaflet-popup-content-wrapper,.leaflet-popup-tip{background:#171b22;color:#f5f7fa;}
.stop-popup{min-width:230px;color:#f5f7fa;}
.stop-popup .small-note{color:#b7c0cc;}
.stop-popup .departure-row{border-color:#343b46;color:#f5f7fa;}
.stop-popup .departure-row small{color:#b7c0cc;}
</style>
</head>
<body class="menu-closed">
<button id="menuToggle" onclick="toggleMenu()" aria-label="Otwórz lub zamknij menu">☰</button>\n
<div id="mapTools" aria-label="Ulubione pojazdy na mapie"><button type="button" onclick="showSection('ulubione',document.querySelector('nav button[onclick*=ulubione]'))" aria-label="Ulubione pojazdy" title="Ulubione">★</button></div>
<div id="mapZoom" aria-label="Przybliżenie mapy"><button type="button" onclick="zoomMap(1)" aria-label="Przybliż">+</button><button type="button" onclick="zoomMap(-1)" aria-label="Oddal">−</button></div>
<button id="myLocation" onclick="locateUser()" aria-label="Pokaż moją lokalizację"><span class="loc-icon" aria-hidden="true"><svg viewBox="0 0 32 32" width="27" height="27" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="16" cy="16" r="9" stroke="currentColor" stroke-width="2.2"/><circle cx="16" cy="16" r="3.2" fill="currentColor"/><path d="M16 2.5v6M16 23.5v6M2.5 16h6M23.5 16h6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg></span></button>
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
 <button onclick="showSection('baza',this)">🚍 Baza pojazdów ZTM</button>
 <button onclick="showSection('konto',this)">👤 Konto</button>
 <button id="adminNavButton" style="display:none" onclick="showSection('administracja',this)">🛡️ Administracja</button>
 <a class="nav-instagram" href="https://www.instagram.com/boruwkowlosa/" target="_blank" rel="noopener noreferrer"><svg class="instagram-glyph" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5" fill="none" stroke="url(#igGradient)" stroke-width="2"/><circle cx="12" cy="12" r="4.2" fill="none" stroke="url(#igGradient)" stroke-width="2"/><circle cx="17.6" cy="6.6" r="1.25" fill="url(#igGradient)"/><defs><linearGradient id="igGradient" x1="3" y1="21" x2="21" y2="3" gradientUnits="userSpaceOnUse"><stop stop-color="#feda75"/><stop offset=".35" stop-color="#fa7e1e"/><stop offset=".68" stop-color="#d62976"/><stop offset="1" stop-color="#4f5bd5"/></linearGradient></defs></svg><span>@boruwkowlosa</span></a>
</nav>
<div id="bottomNav" class="bottom-nav" aria-label="Nawigacja główna">
 <button type="button" onclick="showBottomSection('ulubione',this)"><span>★</span><small>Ulubione</small></button>
 <button type="button" onclick="showBottomSection('komunikaty',this)"><span>●</span><small>Komunikaty</small></button>
 <button type="button" class="active" onclick="showBottomSection('mapa',this)"><span>📍</span><small>Mapa</small></button>
 <button type="button" onclick="showBottomSection('odjazdy',this)"><span>▤</span><small>Rozkłady</small></button>
 <button type="button" onclick="toggleMenu()"><span>☰</span><small>Menu</small></button>
</div>
<main>
<section id="mapa" class="active">
 <div class="section-head"><div><h2>Mapa pojazdów</h2><div class="hint">Pozycje GPS aktualizowane automatycznie</div></div></div>
 <div id="mapVehicleSearchPanel">
  <div class="map-search-input-wrap"><span aria-hidden="true">⌕</span><input id="mapVehicleSearch" type="search" placeholder="Szukaj pojazdu: linia, brygada, numer taborowy…" autocomplete="off" oninput="searchMapVehicles()" aria-label="Wyszukiwarka pojazdów na mapie"><button type="button" id="clearMapVehicleSearch" onclick="clearMapVehicleSearch()" aria-label="Wyczyść wyszukiwanie">×</button></div>
  <div id="mapVehicleSearchResults" style="display:none;max-height: min(48vh,360px);overflow-y:auto;margin-top:7px"></div>
 </div>
 <div id="vehicleDetailOverlay" class="vehicle-detail-overlay" aria-hidden="true"><div class="vehicle-detail-backdrop" onclick="closeVehicleDetails()"></div><article class="vehicle-detail-card" role="dialog" aria-modal="true" aria-label="Szczegóły pojazdu"><div class="vehicle-detail-grabber"></div><button class="vehicle-detail-close" type="button" onclick="closeVehicleDetails()" aria-label="Zamknij">×</button><div id="vehicleDetailContent"></div></article></div>
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
<section id="komunikaty">
 <div class="section-head"><div><h2>Komunikaty</h2><div class="hint">Informacje dotyczące funkcjonowania komunikacji miejskiej</div></div></div>
 <div class="surface"><div class="empty">Źródło komunikatów ZTM nie jest jeszcze podłączone.</div></div>
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
 <div class="section-head"><div><h2>Rozkłady jazdy</h2><div class="hint">Wybierz linię, a następnie kierunek i kurs z rozkładu ZTM</div></div></div>
 <div class="surface departures-card">
  <label class="small-note" for="routeSearch">Wyszukaj linię</label>
  <input id="routeSearch" type="search" placeholder="Numer linii, np. 167" oninput="filterScheduleLines()">
  <div id="routeSearchResults" class="stop-search-results"><div class="empty">Ładowanie listy linii…</div></div>
  <div id="selectedLineSchedule" class="departures-list"></div>
 </div>
</section>
<section id="ustawienia">
 <div class="section-head"><div><h2>Ustawienia mapy</h2><div class="hint">Dostosuj etykiety pojazdów do swoich preferencji</div></div></div>
 <div class="surface"><div class="settings-grid">
  <label class="check"><input type="checkbox" id="showLine" checked onchange="saveLabelSettings()"> Numer linii</label>
  <label class="check"><input type="checkbox" id="showBrigade" onchange="saveLabelSettings()"> Numer brygady</label>
  <label class="check"><input type="checkbox" id="showFleet" checked onchange="saveLabelSettings()"> Numer taborowy</label>
 </div><p class="small-note">Widoczne będą wyłącznie dane potwierdzone w źródłach ZTM.</p><div class="theme-setting"><h3>Wygląd aplikacji</h3><p class="small-note">Wybierz motyw Transportie.</p><div class="theme-options"><button type="button" id="themeLight" onclick="setTheme('light')" aria-pressed="false">☀️ Jasny</button><button type="button" id="themeDark" onclick="setTheme('dark')" aria-pressed="false">🌙 Ciemny</button><button type="button" id="themeSystem" onclick="setTheme('system')" aria-pressed="false">⚙️ Systemowy</button></div></div><div class="small-note" id="mapLabelSummary">Etykiety: —</div><div class="small-note" id="dataStatus">Połączenie z danymi: oczekiwanie…</div><div class="small-note" id="lastUpdateSettings">Ostatnia aktualizacja: —</div><div class="small-note" id="vehicleCountSettings">Widoczne pojazdy: —</div></div>
</section>
<section id="baza">
 <div class="section-head"><div><h2>Baza pojazdów ZTM</h2><div class="hint">Katalog pojazdów na podstawie danych źródłowych ZTM Gdańsk</div></div></div>
 <div class="surface"><div class="toolbar"><input id="fleetDatabaseSearch" type="search" placeholder="Szukaj: numer taborowy, model, przewoźnik…" oninput="renderFleetDatabase()"><button class="primary" onclick="loadFleetDatabase(true)">Odśwież</button></div><div class="small-note" id="fleetDatabaseStatus">Pobieranie bazy pojazdów…</div><div id="fleetDatabaseTable"></div></div>
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
let map=null;let allStops=[];let stopRenderer=null;let vehiclesUpdateInFlight=false;let mapDarkTiles=null;let mapLightTiles=null;let darkMapMode=true;let stopsVisible=true;let stopsLoading=false;
function initMap(){
 try{
  if(!window.L||map)return;
  map=L.map('map',{zoomControl:false,attributionControl:false,preferCanvas:true}).setView([54.3520,18.6466],12);if(!map.getPane('stopsPane')){map.createPane('stopsPane');map.getPane('stopsPane').style.zIndex='625';}L.control.attribution({prefix:'🇵🇱'}).addTo(map);map.whenReady(()=>{if(typeof loadStops==='function')loadStops();});map.on('zoomend',refreshTooltips);map.on('moveend',refreshTooltips);map.on('click',function(event){if(!map)return;const tap=map.latLngToContainerPoint(event.latlng);let nearest=null,nearestDistance=30;Object.entries(stopMarkers).forEach(([id,marker])=>{const point=map.latLngToContainerPoint(marker.getLatLng()),distance=point.distanceTo(tap);if(distance<nearestDistance){nearestDistance=distance;nearest=marker;}});if(nearest)nearest.openPopup();});stopRenderer=L.svg({padding:0.5});
  mapDarkTiles=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors',subdomains:'abc',maxZoom:19,className:'transportie-dark-tiles'}).addTo(map);
  mapLightTiles=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors',subdomains:'abc',maxZoom:19});
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
function getThemePreference(){try{return localStorage.getItem('transportie-theme')||'system';}catch(e){return 'system';}}
function applyTheme(){const pref=getThemePreference(),dark=pref==='dark'||(pref==='system'&&window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.dataset.theme=dark?'dark':'light';['light','dark','system'].forEach(name=>{const el=document.getElementById('theme'+name.charAt(0).toUpperCase()+name.slice(1));if(el){el.setAttribute('aria-pressed',String(pref===name));el.classList.toggle('selected',pref===name);}});}
function setTheme(theme){if(!['light','dark','system'].includes(theme))return;try{localStorage.setItem('transportie-theme',theme);}catch(e){}applyTheme();}
if(window.matchMedia){const themeMedia=window.matchMedia('(prefers-color-scheme: dark)');if(themeMedia.addEventListener)themeMedia.addEventListener('change',()=>{if(getThemePreference()==='system')applyTheme();});}
applyTheme();
let fleetDatabaseRows=[];
async function loadFleetDatabase(force){const status=document.getElementById('fleetDatabaseStatus'),box=document.getElementById('fleetDatabaseTable');if(!status||!box)return;status.textContent='Pobieranie oficjalnej bazy pojazdów ZTM…';if(force)box.innerHTML='';try{const response=await fetch('/api/fleet',{cache:force?'no-store':'default'});const data=await response.json();if(!response.ok||data.error)throw new Error(data.error||'Błąd pobierania bazy');fleetDatabaseRows=Array.isArray(data.vehicles)?data.vehicles:[];status.textContent='Pojazdy w bazie: '+fleetDatabaseRows.length+' · Źródło: '+(data.source||'ZTM Gdańsk')+' · Aktualizacja: '+(data.lastUpdate||'brak informacji');renderFleetDatabase();}catch(error){status.textContent='Nie udało się pobrać bazy pojazdów: '+error.message;box.innerHTML='<div class="empty">Dane źródłowe są chwilowo niedostępne. Spróbuj ponownie później.</div>';}}
function renderFleetDatabase(){const box=document.getElementById('fleetDatabaseTable');if(!box)return;const q=(document.getElementById('fleetDatabaseSearch')?.value||'').trim().toLowerCase();const rows=fleetDatabaseRows.filter(v=>Object.values(v).some(x=>x!=null&&String(x).toLowerCase().includes(q)));if(!rows.length){box.innerHTML='<div class="empty">Brak pojazdów pasujących do wyszukiwania.</div>';return;}const val=(v,keys)=>{for(const k of keys){if(v[k]!=null&&String(v[k]).trim()!=='')return String(v[k]);}return '—';};box.innerHTML='<div class="table-wrap"><table><thead><tr><th>Nr taborowy</th><th>Marka / model</th><th>Przewoźnik</th><th>Typ</th><th>Rok</th></tr></thead><tbody>'+rows.map(v=>'<tr><td><b>#'+safe(val(v,['vehicleCode','fleetNumber','fleet','number']))+'</b></td><td>'+safe([val(v,['brand','make','manufacturer']) ,val(v,['model','vehicleModel'])].filter(x=>x!=='—').join(' ')||'—')+'</td><td>'+safe(val(v,['carrier','carrirer','operator']))+'</td><td>'+safe(val(v,['vehicleType','type','category']))+'</td><td>'+safe(val(v,['productionYear','year','manufactureYear']))+'</td></tr>').join('')+'</tbody></table></div>';}function showSection(id,button){document.querySelectorAll('main section').forEach(s=>s.classList.remove('active'));document.querySelectorAll('nav button').forEach(b=>b.classList.remove('active'));document.getElementById(id).classList.add('active');if(button)button.classList.add('active');if(window.innerWidth<=850){document.body.classList.add('menu-closed');document.body.classList.remove('mobile-menu-open');document.querySelectorAll('#bottomNav button').forEach(b=>b.classList.toggle('active',b.getAttribute('onclick')&&b.getAttribute('onclick').includes("'"+id+"'")));}if(id==='mapa'&&map)setTimeout(()=>map.invalidateSize(),180);if(id==='ulubione')renderFavorites();if(id==='wyjechalo')renderActiveTable();if(id==='baza')loadFleetDatabase(false);if(id==='konto')refreshAccount();if(id==='odjazdy'){loadScheduleRoutes();}}
 window.showSection=showSection;
function toggleMenu(){if(window.innerWidth<=850){document.body.classList.toggle('mobile-menu-open');}else{document.body.classList.toggle('menu-closed');}if(map)setTimeout(()=>map.invalidateSize(),260);}
function showBottomSection(id,button){showSection(id,button);document.querySelectorAll('#bottomNav button').forEach(b=>b.classList.toggle('active',b===button));}
function toggleStopVisibility(){stopsVisible=!stopsVisible;Object.values(stopMarkers).forEach(marker=>{if(stopsVisible){if(!map.hasLayer(marker))marker.addTo(map);}else if(map.hasLayer(marker)){map.removeLayer(marker);}});const b=document.querySelector('#mapTools button:first-child');if(b)b.classList.toggle('tool-off',!stopsVisible);}
function toggleMapLayer(){if(!map||!mapDarkTiles||!mapLightTiles)return;if(darkMapMode){map.removeLayer(mapDarkTiles);mapLightTiles.addTo(map);}else{map.removeLayer(mapLightTiles);mapDarkTiles.addTo(map);}darkMapMode=!darkMapMode;const b=document.querySelector('#mapTools button:nth-child(2)');if(b)b.classList.toggle('tool-off',!darkMapMode);}
function zoomMap(delta){if(map)map.setZoom(map.getZoom()+delta);}
window.zoomMap=zoomMap;
function locateUser(){const button=document.getElementById('myLocation');button.disabled=true;if(!navigator.geolocation){button.disabled=false;return;}navigator.geolocation.getCurrentPosition(pos=>{const lat=pos.coords.latitude,lon=pos.coords.longitude;if(map){if(userLocationMarker)map.removeLayer(userLocationMarker);userLocationMarker=L.circleMarker([lat,lon],{radius:10,color:'#fff',weight:4,fillColor:'#1765d1',fillOpacity:1}).addTo(map).bindPopup('Twoja lokalizacja');map.setView([lat,lon],16);userLocationMarker.openPopup();}button.disabled=false;},()=>{button.disabled=false;},{enableHighAccuracy:true,timeout:15000,maximumAge:30000});}
function saveLabelSettings(){labelSettings={line:document.getElementById('showLine').checked,brigade:document.getElementById('showBrigade').checked,fleet:document.getElementById('showFleet').checked};localStorage.setItem('transportie-labels',JSON.stringify(labelSettings));const summary=document.getElementById('mapLabelSummary');if(summary)summary.textContent='Etykiety: '+([labelSettings.line?'Linia':null,labelSettings.brigade?'Brygada':null,labelSettings.fleet?'Tabor':null].filter(Boolean).join(' · ')||'wyłączone');refreshTooltips();}
async function loadStops(){
 if(stopsLoading||!map||!window.L)return;
 stopsLoading=true;
 try{
  const response=await fetch('/api/stops',{cache:'no-store'});
  const data=await response.json().catch(()=>({}));
  if(!response.ok)throw new Error(data.error||'Nie udało się pobrać przystanków: HTTP '+response.status);
  allStops=Array.isArray(data.stops)?data.stops:[];
  console.info('[Przystanki] pobrano:',allStops.length,'źródło:',data.source||'ZTM');
  if(!allStops.length)throw new Error(data.error||'API zwróciło pustą listę przystanków');
  let created=0;
  allStops.forEach(stop=>{
   const id=String(stop.stopId??stop.stop_id??stop.id??'').trim();
   const lat=Number(stop.lat??stop.stopLat??stop.stop_lat??stop.latitude);
   const lon=Number(stop.lon??stop.stopLon??stop.stop_lon??stop.longitude);
   const name=stop.stopName||stop.stopDesc||stop.stop_name||stop.name||'Przystanek';
   const platform=String(stop.subName||stop.sub_name||stop.stopCode||stop.stop_code||stop.platform||'').trim();
   if(!id||!Number.isFinite(lat)||!Number.isFinite(lon)||lat<53.8||lat>54.8||lon<18||lon>19.2||stopMarkers[id])return;
   const iconHtml='<div aria-label="Przystanek autobusowy" role="img" style="width:44px;height:44px;display:flex;align-items:center;justify-content:center;border-radius:50%;background:#07996d;border:3px solid #fff;color:#fff;box-shadow:0 2px 9px rgba(0,0,0,.75);"><svg viewBox="0 0 24 24" width="25" height="25" aria-hidden="true" style="display:block;flex:none;"><path d="M5 4.5A2.5 2.5 0 0 1 7.5 2h9A2.5 2.5 0 0 1 19 4.5v13a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 5 17.5zM7 5h10v8H7zM8 16h2m4 0h2M8 21v-2m8 2v-2" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></div>';
   const marker=L.marker([lat,lon],{
    pane:'markerPane',zIndexOffset:1200,keyboard:true,interactive:true,
    icon:L.divIcon({className:'stop-marker',html:iconHtml,iconSize:[44,44],iconAnchor:[22,22]})
   }).addTo(map);
   const label=platform?'<span>'+safe(name)+'</span><span class="stop-platform">'+safe(platform)+'</span>':safe(name);
   marker.bindTooltip(label,{permanent:true,direction:'bottom',offset:[0,22],className:'stop-label',opacity:1});
   marker.bindPopup('<div class="stop-popup"><b>'+safe(name)+'</b><div class="small-note">Pobieranie najbliższych odjazdów…</div></div>',{maxWidth:320});
   marker.on('click',()=>{if(!marker.isPopupOpen())marker.openPopup();});
   marker.on('popupopen',()=>loadStopDepartures(id,marker,name));
   stopMarkers[id]=marker;
   created++;
  });
  if(!created&&!Object.keys(stopMarkers).length)throw new Error('Dane przystanków pobrano, ale nie utworzono żadnego znacznika. Sprawdź współrzędne w API.');
  refreshTooltips();
  console.info('[Przystanki] utworzono klikalne ikony:',created,'łącznie:',Object.keys(stopMarkers).length);
 }catch(e){
  console.error('[Przystanki] błąd:',e);
  const results=document.getElementById('stopSearchResults');
  if(results)results.innerHTML='<div class="empty">Nie udało się pobrać przystanków ZTM: '+safe(e.message)+'</div>';
 }finally{stopsLoading=false;}
}
function parseStopTime(value){if(!value)return null;const raw=String(value).trim();let date=new Date(raw);if(!isNaN(date.getTime()))return date;const match=raw.match(/(?:T|^)(\d{1,2}):(\d{2})(?::(\d{2}))?/);if(match){date=new Date();date.setHours(Number(match[1]),Number(match[2]),Number(match[3]||0),0);if(date.getTime()<Date.now()-60000)date.setDate(date.getDate()+1);return date;}return null;}
function stopDepartureMarkup(d){const rawTime=d.estimatedTime||d.estimated_time||d.expectedTime||d.departureTime||d.arrivalTime||d.time||d.theoreticalTime||d.scheduledTime;const dt=parseStopTime(rawTime);const t=dt?dt.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'}):'—';const wait=dt?Math.max(0,Math.round((dt.getTime()-Date.now())/60000)):null;const delay=d.delayInSeconds??d.delay_in_seconds;const mins=wait!==null?(wait===0?'teraz':'za '+wait+' min'):(delay==null?'':(delay>0?'+':'')+Math.round(delay/60)+' min');const line=d.routeShortName||d.route||d.routeId||d.route_id||'—';const direction=d.headsign||d.direction||d.destination||'kierunek nieznany';const fleet=d.vehicleCode??d.vehicleId??d.vehicleNumber??d.fleetNumber;return '<div class="departure-row"><span><b>'+safe(line)+'</b> · '+safe(direction)+(fleet!=null&&fleet!==''?'<button type="button" class="departure-fleet" data-departure-vehicle="'+safe(fleet)+'">#'+safe(fleet)+'</button>':'<small class="small-note">pojazd niepodany w danych</small>')+'</span><span><b>'+safe(mins||'—')+'</b><br><small>'+safe(t)+'</small></span></div>';}
async function loadStopDepartures(id,marker,name){try{const response=await fetch('/api/departures/'+encodeURIComponent(id),{cache:'no-store'});const data=await response.json();if(!response.ok)throw new Error(data.error||'API odjazdów');const rows=Array.isArray(data.departures)?data.departures:[];const html=rows.length?rows.slice(0,15).map(stopDepartureMarkup).join(''):'<div class="empty">Brak najbliższych odjazdów w aktualnym źródle ZTM.</div>';marker.setPopupContent('<div class="stop-popup"><b>'+safe(name||'Przystanek')+'</b><div class="small-note">Linia · kierunek · tabor · czas przyjazdu</div>'+html+'</div>');}catch(e){marker.setPopupContent('<div class="stop-popup"><b>'+safe(name||'Przystanek')+'</b><div class="small-note">Nie udało się pobrać odjazdów: '+safe(e.message)+'</div></div>');}}
async function showStopDepartures(id,name){const box=document.getElementById('selectedStopDepartures');if(box)box.innerHTML='<div class="empty">Pobieranie odjazdów…</div>';try{const response=await fetch('/api/departures/'+encodeURIComponent(id),{cache:'no-store'});const data=await response.json();if(!response.ok)throw new Error(data.error||'API odjazdów');const rows=Array.isArray(data.departures)?data.departures:[];const html=rows.length?rows.slice(0,20).map(stopDepartureMarkup).join(''):'<div class="empty">Brak najbliższych odjazdów w aktualnym źródle ZTM.</div>';if(box)box.innerHTML='<h3>'+safe(name)+'</h3><div class="small-note">Linia · kierunek · tabor · czas przyjazdu</div>'+html;}catch(e){if(box)box.innerHTML='<div class="empty">Nie udało się pobrać odjazdów: '+safe(e.message)+'</div>';}}
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
window.toggleMenu=toggleMenu;window.locateUser=locateUser;window.loginUser=loginUser;window.registerUser=registerUser;window.logoutUser=logoutUser;window.loadAdminUsers=loadAdminUsers;
function brigadeFor(v){const service=String(v.vehicleService||'');const match=service.match(/-(\d{2})$/);return match?match[1]:'—';}
function labelFor(v){const parts=[];if(labelSettings.line)parts.push('Linia '+(v.routeShortName||'?'));if(labelSettings.brigade)parts.push('Brygada '+brigadeFor(v));if(labelSettings.fleet)parts.push('Tabor '+(v.vehicleCode||'?'));return parts.join(' · ')||'Pojazd';}
function isTram(v){const route=String(v.routeShortName||'').trim();const service=String(v.vehicleType||v.type||v.vehicleService||'').toLowerCase();return service.includes('tram')||/^(2|3|4|5|6|7|8|9|10|11|12)$/.test(route);}
function vehicleIcon(v){const label=labelFor(v);const tram=isTram(v);const color=tram?'#2878df':'#dc3545';const zoom=map?map.getZoom():14;if(zoom<=10)return L.divIcon({className:'vehicle-marker',html:'<div class="vehicle-dot" style="background:'+color+'"></div>',iconSize:[12,12],iconAnchor:[6,6]});const compact=zoom<=14;const shown=compact?(v.routeShortName||'•'):label;const width=Math.max(28,Math.min(150,shown.length*5.7+14));return L.divIcon({className:'vehicle-marker',html:'<div class="vehicle-chip" style="background:'+color+';color:#fff;border:1px solid '+color+';border-radius:5px;padding:'+(compact?'2px 4px':'3px 5px')+';font-size:'+(compact?'9px':'10px')+';box-shadow:0 1px 4px #17243a33;font-weight:800;white-space:nowrap">'+safe(shown)+'</div>',iconSize:[width,compact?16:20],iconAnchor:[width/2,compact?8:10]});}
function formatDelaySeconds(value){if(value===null||value===undefined||value===''||!Number.isFinite(Number(value)))return 'brak danych';const minutes=Math.round(Number(value)/60);if(minutes>0)return '-'+minutes+' min';if(minutes<0)return '+'+Math.abs(minutes)+' min';return 'punktualnie';}
function vehicleField(label,value,extra){if(value===undefined||value===null||value==='')return '';return '<div class="vehicle-detail-field"><span>'+safe(label)+'</span><b '+(extra||'')+'>'+safe(value)+'</b></div>';}
function vehicleValue(v,keys){for(const key of keys){if(v[key]!==undefined&&v[key]!==null&&v[key]!=='')return v[key];}return null;}
function openVehicleDetails(v){
 if(!v)return;
 const overlay=document.getElementById('vehicleDetailOverlay'),content=document.getElementById('vehicleDetailContent');
 if(!overlay||!content)return;
 const info=v.fleetInfo&&typeof v.fleetInfo==='object'?v.fleetInfo:{};
 const get=(obj,keys)=>vehicleValue(obj,keys);
 const line=get(v,['routeShortName','route','line']);
 const fleet=get(v,['vehicleCode','fleetNumber']);
 const carrier=get(v,['carrier'])||get(info,['carrier','carrirer','operator']);
 const delay=formatDelaySeconds(get(v,['delayInSeconds','delay']));
 const speed=get(v,['speed','speedKmh','velocity']);
 const direction=get(v,['headsign','destination','direction','finalStop','tripHeadsign']);
 const brigade=brigadeFor(v);
 const routeId=get(v,['routeId','route_id']);
 const tripId=get(v,['tripId','trip_id']);
 const fields=
  vehicleField('Linia',line)+
  vehicleField('Brygada',brigade)+
  vehicleField('Numer taborowy',fleet==null?null:'#'+fleet)+
  vehicleField('Przewoźnik',carrier)+
  vehicleField('Opóźnienie',delay,'class="vehicle-delay"')+
  vehicleField('Prędkość',speed==null?null:String(speed)+' km/h');
 const routeStops='<div class="vehicle-detail-section"><h3>Trasa i przystanki</h3>'+
  (line?'<div class="vehicle-route-line">Linia <b>'+safe(line)+'</b></div>':'')+
  (direction?'<div class="vehicle-route-direction">Kierunek: <b>'+safe(direction)+'</b></div>':'')+
  '<div id="vehicleRouteStops" class="vehicle-detail-stops"><div class="vehicle-detail-empty">Pobieranie przystanków z rozkładu ZTM…</div></div></div>';

 const specs=[
  ['Marka',['brand','make','manufacturer']],
  ['Model',['model','vehicleModel']],
  ['Liczba siedzeń',['seats','seatCount','seatingCapacity','numberOfSeats','placesSeated']],
  ['Długość autobusu',['length','vehicleLength','lengthMeters','length_m']],
  ['Rok produkcji',['productionYear','year','manufactureYear']],
  ['Miejsca stojące',['standingPlaces','standing','standingCapacity','placesStanding']],
  ['USB',['usb','USB','hasUsb','usbPorts']],
  ['AED',['aed','AED','hasAed']],
  ['Rampa',['ramp','hasRamp','wheelchairRamp']],
  ['Typ autobusu',['busType','vehicleType','type','vehicle_kind']],
  ['Ilość drzwi',['doors','doorCount','numberOfDoors']]
 ];
 const technicalRows=specs.map(([label,keys])=>{
  const value=get(info,keys)||get(v,keys);
  if(value===null)return '';
  const display=typeof value==='boolean'?(value?'Tak':'Nie'):String(value)+(label==='Długość autobusu'&&!/m\s*$/.test(String(value))?' m':'');
  return vehicleField(label,display);
 }).join('');
 const technical=technicalRows?'<div class="vehicle-detail-section"><h3>Dane techniczne</h3><div class="vehicle-detail-grid">'+technicalRows+'</div></div>':'';
  const vehicleTab='<div class="vehicle-detail-section"><h3>Informacje o pojeździe</h3><div class="vehicle-detail-grid">'+(fields||'<div class="vehicle-detail-empty">Brak danych pojazdu.</div>')+'</div></div>'+technical;
 const brigadeTab='<div class="vehicle-detail-section"><h3>Rzeczywisty rozkład brygady ZTM</h3><div class="vehicle-brigade-note">Brygada <b>'+safe(brigade)+'</b> · zadanie '+safe(get(v,['vehicleService'])||'—')+' · rozkład na dziś z danych ZTM.</div><div id="vehicleBrigadeCourses" class="vehicle-duty-courses"><div class="vehicle-detail-empty">Pobieranie wszystkich kursów brygady z ZTM…</div></div></div>';
 content.innerHTML=
  '<div class="vehicle-detail-head"><div class="vehicle-detail-line">'+safe(line||'—')+'</div><div><div class="vehicle-detail-type">'+(isTram(v)?'🚊 Tramwaj':'🚌 Autobus')+' · POJAZD LIVE</div><div class="vehicle-detail-title">'+safe(direction||'Kurs w trakcie')+'</div><span class="vehicle-live-status">● Pozycja GPS na żywo</span></div></div>'+
  '<div class="vehicle-detail-meta"><strong>#'+safe(fleet||'—')+'</strong><span>·</span><span>Brygada '+safe(brigade)+'</span><span>·</span><span>'+safe(speed==null?'—':String(speed)+' km/h')+'</span><span>·</span><span>'+safe(delay)+'</span><span>·</span><span>GPS ZTM: '+safe(formatZtmTimestamp(get(v,['generated','dataGenerated','DataGenerated']))||'—')+'</span></div>'+
  '<div class="vehicle-detail-tabs"><button type="button" class="active" data-vehicle-tab="route">TRASA</button><button type="button" data-vehicle-tab="vehicle">POJAZD</button><button type="button" data-vehicle-tab="brigade">ROZKŁAD BRYGADOWY</button></div>'+
  '<div class="vehicle-tab-panel active" data-vehicle-panel="route">'+routeStops+'</div>'+
  '<div class="vehicle-tab-panel" data-vehicle-panel="vehicle">'+vehicleTab+'</div>'+
  '<div class="vehicle-tab-panel" data-vehicle-panel="brigade">'+brigadeTab+'</div>';
 content.querySelectorAll('[data-vehicle-tab]').forEach(button=>button.addEventListener('click',()=>selectVehicleTab(button.dataset.vehicleTab,button)));
overlay.classList.add('open');
 overlay.setAttribute('aria-hidden','false');
 document.body.classList.add('vehicle-detail-open');
 selectedVehicleCode=String(v.vehicleCode||'');
 if(vehicleRouteStopsTimer){clearInterval(vehicleRouteStopsTimer);vehicleRouteStopsTimer=null;}
 loadVehicleRouteStops(routeId,tripId,selectedVehicleCode,v);
 loadVehicleDuty(routeId,get(v,['vehicleService','vehicle_service','BusServiceName','busServiceName']));
 vehicleRouteStopsTimer=setInterval(()=>{
  if(String(selectedVehicleCode)!==String(v.vehicleCode||''))return;
  const latest=Array.isArray(vehicles)?vehicles.find(item=>String(item.vehicleCode||'')===String(v.vehicleCode||'')):null;
  if(latest)loadVehicleRouteStops(routeId,tripId,selectedVehicleCode,latest);
 },15000);
}
async function loadVehicleRouteStops(routeId,tripId,vehicleCode,vehicle){
 const box=document.getElementById('vehicleRouteStops');
 if(!box)return;
 if(routeId==null||tripId==null){
  box.innerHTML='<div class="vehicle-detail-empty">GPS nie przekazał identyfikatora wariantu kursu, więc nie można dopasować dokładnej listy przystanków.</div>';
  return;
 }
 try{
  const lat=vehicle&&vehicle.lat!=null?vehicle.lat:'';
  const lon=vehicle&&vehicle.lon!=null?vehicle.lon:'';
  const delay=vehicle&&vehicle.delay!=null?vehicle.delay:'';
  const service=vehicle&&vehicle.vehicleService!=null?vehicle.vehicleService:'';
  const startTime=vehicle&&vehicle.scheduledTripStartTime?vehicle.scheduledTripStartTime:'';
  const query='?lat='+encodeURIComponent(lat)+'&lon='+encodeURIComponent(lon)+'&delay='+encodeURIComponent(delay)+'&vehicle_service='+encodeURIComponent(service)+'&scheduled_trip_start_time='+encodeURIComponent(startTime);
  const response=await fetch('/api/vehicle-route/'+encodeURIComponent(routeId)+'/'+encodeURIComponent(tripId)+query);
  const data=await response.json();
  if(String(selectedVehicleCode)!==String(vehicleCode))return;
  if(!response.ok)throw new Error(data.error||'Błąd pobierania rozkładu');
  const stops=Array.isArray(data.stops)?data.stops:[];
  if(!stops.length){
   box.innerHTML='<div class="vehicle-detail-empty">ZTM nie zwrócił przystanków dla tego wariantu kursu.</div>';
   return;
  }
  const currentIndex=Number(data.currentIndex||0);
  const routePoints=stops.filter(stop=>Number.isFinite(Number(stop.lat))&&Number.isFinite(Number(stop.lon))).map(stop=>[Number(stop.lat),Number(stop.lon)]);
  if(vehicleRoutePolyline&&map){map.removeLayer(vehicleRoutePolyline);vehicleRoutePolyline=null;}
  if(map&&routePoints.length>1){vehicleRoutePolyline=L.polyline(routePoints,{color:'#00a56a',weight:5,opacity:.92,lineCap:'round',lineJoin:'round'}).addTo(map);}
  box.innerHTML=stops.map((stop,index)=>{
   const time=stop.estimatedTime&&stop.scheduledTime&&stop.estimatedTime!==stop.scheduledTime
    ?'<span class="course-stop-time"><s>'+safe(stop.scheduledTime)+'</s><strong>'+safe(stop.estimatedTime)+'</strong></span>'
    :'<span class="course-stop-time">'+safe(stop.estimatedTime||stop.scheduledTime||'—')+'</span>';
   const passed=index<currentIndex?' passed':'';
   const stopLabel=(stop.name||'Przystanek')+(stop.code&&!String(stop.name||'').endsWith(String(stop.code))?' '+stop.code:'');
   return '<div class="course-stop'+passed+'" data-stop-index="'+index+'"><span class="course-stop-marker" aria-hidden="true"></span><span class="course-stop-name"><b>'+safe(stopLabel)+'</b></span>'+time+'</div>';
  }).join('');

  if(currentIndex>0){
   window.setTimeout(()=>{
    if(String(selectedVehicleCode)!==String(vehicleCode))return;
    box.querySelectorAll('.course-stop.passed').forEach(row=>row.remove());
   },700);
  }
 }catch(error){
  if(String(selectedVehicleCode)!==String(vehicleCode))return;
  box.innerHTML='<div class="vehicle-detail-empty">'+safe(error.message||'Nie udało się pobrać listy przystanków.')+'</div>';
 }
}
let vehicleRouteStopsTimer=null;
function closeVehicleDetails(){if(vehicleRoutePolyline&&map){map.removeLayer(vehicleRoutePolyline);vehicleRoutePolyline=null;}const overlay=document.getElementById('vehicleDetailOverlay');if(overlay){overlay.classList.remove('open');overlay.setAttribute('aria-hidden','true');}document.body.classList.remove('vehicle-detail-open');selectedVehicleCode=null;if(vehicleRouteStopsTimer){clearInterval(vehicleRouteStopsTimer);vehicleRouteStopsTimer=null;}}
function formatZtmTimestamp(value){if(!value)return '';const d=new Date(value);return Number.isNaN(d.getTime())?String(value):d.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit',second:'2-digit'});}
async function loadVehicleDuty(routeId,service){
 const box=document.getElementById('vehicleBrigadeCourses');if(!box)return;
 if(routeId==null||!service){box.innerHTML='<div class="vehicle-detail-empty">Brak identyfikatora brygady w danych GPS. Rozkład brygadowy nie może zostać dopasowany automatycznie.</div>';return;}
 try{
  const response=await fetch('/api/vehicle-duty/'+encodeURIComponent(routeId)+'/'+encodeURIComponent(service),{cache:'no-store'});
  const data=await response.json();if(!response.ok)throw new Error(data.error||'Nie udało się pobrać rozkładu brygady.');
  const courses=Array.isArray(data.courses)?data.courses:[];
  if(!courses.length){box.innerHTML='<div class="vehicle-detail-empty">Brak kursów tej brygady w dzisiejszym rozkładzie ZTM.</div>';return;}
  box.innerHTML='<div class="vehicle-duty-source">Rozkład ZTM · '+safe(data.date||'dzisiaj')+' · '+safe(data.count||courses.length)+' kursów</div>'+courses.map(course=>'<article class="vehicle-duty-course"><div class="vehicle-duty-course-head"><span>Kurs '+safe(course.order||'—')+'</span><small>'+safe(course.startTime||'—')+' – '+safe(course.endTime||'—')+'</small></div>'+(course.stops||[]).map(stop=>'<div class="vehicle-duty-stop"><span>'+safe(stop.name||'Przystanek')+(stop.code?' <small>'+safe(stop.code)+'</small>':'')+'</span><time>'+safe(stop.time||'—')+'</time></div>').join('')+'</article>').join('');
 }catch(error){box.innerHTML='<div class="vehicle-detail-empty">'+safe(error.message||'Błąd pobierania danych ZTM.')+'</div>';}
}
function selectVehicleTab(tab,button){const root=document.getElementById('vehicleDetailContent');if(!root)return;root.querySelectorAll('[data-vehicle-tab]').forEach(x=>x.classList.toggle('active',x===button));root.querySelectorAll('[data-vehicle-panel]').forEach(x=>x.classList.toggle('active',x.getAttribute('data-vehicle-panel')===tab));}
window.selectVehicleTab=selectVehicleTab;
window.openVehicleDetails=openVehicleDetails;window.closeVehicleDetails=closeVehicleDetails;
let selectedVehicleCode=null;
let vehicleRoutePolyline=null;
function refreshTooltips(){vehicles.forEach(v=>{const id=String(v.vehicleCode||'');if(markers[id]){const icon=vehicleIcon(v),html=icon.options&&icon.options.html||'';if(markers[id]._transportieIconHtml!==html){markers[id].setIcon(icon);markers[id]._transportieIconHtml=html;}}});const zoom=map?map.getZoom():12,bounds=map?map.getBounds():null;Object.values(stopMarkers).forEach(marker=>{if(zoom>=14&&bounds&&bounds.contains(marker.getLatLng())){marker.openTooltip&&marker.openTooltip();}else{marker.closeTooltip&&marker.closeTooltip();}});}
// Zgodność ze starszymi elementami HTML, które mogą jeszcze wywoływać searchStops().
function searchStops(){
 const input=document.getElementById('stopSearch');
 const box=document.getElementById('stopSearchResults');
 if(!input||!box)return;
 const q=(input.value||'').trim().toLowerCase();
 const matches=(Array.isArray(allStops)?allStops:[]).filter(stop=>(String(stop.stopName||stop.stopDesc||'')+' '+String(stop.stopId||'')).toLowerCase().includes(q)).slice(0,60);
 box.innerHTML=matches.length?matches.map(stop=>'<button type="button" data-stop-select="'+safe(stop.stopId)+'" data-stop-name="'+safe(stop.stopName||stop.stopDesc||'Przystanek')+'">'+safe(stop.stopName||stop.stopDesc||'Przystanek')+'</button>').join(''):'<div class="empty">Nie znaleziono przystanków.</div>';
}
window.searchStops=searchStops;
let scheduleRoutes=[];
async function loadScheduleRoutes(force=false){
 const box=document.getElementById('routeSearchResults');if(!box)return;
 if(scheduleRoutes.length&&!force){filterScheduleLines();return;}
 box.innerHTML='<div class="empty">Pobieranie listy linii ZTM…</div>';
 try{const response=await fetch('/api/routes');const data=await response.json();if(!response.ok)throw new Error(data.error||'Błąd listy linii');scheduleRoutes=Array.isArray(data.routes)?data.routes:[];filterScheduleLines();}
 catch(error){box.innerHTML='<div class="empty">Nie udało się pobrać listy linii ZTM.</div>';console.warn('Linie:',error);}
}
function filterScheduleLines(){
 const box=document.getElementById('routeSearchResults');if(!box)return;
 const q=(document.getElementById('routeSearch')?.value||'').trim().toLowerCase();
 const matches=scheduleRoutes.filter(r=>(String(r.routeShortName||'')+' '+String(r.routeLongName||'')).toLowerCase().includes(q)).slice(0,80);
 box.innerHTML=matches.length?matches.map(r=>'<button type="button" data-schedule-route="'+safe(r.routeId)+'"><b>Linia '+safe(r.routeShortName)+'</b><br><small>'+safe(r.routeLongName||'Rozkład ZTM')+'</small></button>').join(''):'<div class="empty">Nie znaleziono linii.</div>';
}
async function selectScheduleLine(routeId){
 const route=scheduleRoutes.find(r=>String(r.routeId)===String(routeId));if(!route)return;
 const box=document.getElementById('selectedLineSchedule');if(!box)return;
 box.innerHTML='<div class="empty">Pobieranie rozkładu linii '+safe(route.routeShortName)+'…</div>';
 try{
  const response=await fetch('/api/line-schedule/'+encodeURIComponent(routeId));const data=await response.json();if(!response.ok)throw new Error(data.error||'Błąd rozkładu');
  const courses=Array.isArray(data.courses)?data.courses:[];
  if(!courses.length){box.innerHTML='<h3>Linia '+safe(route.routeShortName)+'</h3><div class="empty">Brak kursów w rozkładzie na '+safe(data.date||'dzisiaj')+'.</div>';return;}
  const directions={};courses.forEach(c=>{const key=c.direction||'Kierunek nieznany';(directions[key]||(directions[key]=[])).push(c);});
  box.innerHTML='<div class="schedule-head"><h3>Linia '+safe(route.routeShortName)+'</h3><small>Rozkład na '+safe(data.date||'dzisiaj')+' · '+courses.length+' kursów</small></div>'+Object.entries(directions).map(([direction,list])=>'<section class="schedule-direction"><h4>Kierunek: '+safe(direction)+'</h4>'+list.map(c=>'<details class="schedule-course"><summary><b>'+safe(c.start||'—')+'</b><span>'+safe(c.service?'Brygada '+c.service:'Kurs')+'</span><small>'+c.stops.length+' przystanków</small></summary><div class="schedule-stop-list">'+c.stops.map(st=>'<div class="schedule-stop-row"><span>'+safe(st.name)+(st.note?' <small>'+safe(st.note)+'</small>':'')+'</span><b>'+safe(st.time||'—')+'</b></div>').join('')+'</div></details>').join('')+'</section>').join('');
 }catch(error){box.innerHTML='<div class="empty">Nie udało się pobrać rozkładu tej linii.</div>';console.warn('Rozkład linii:',error);}
}

const mapSearchInput=document.getElementById("mapVehicleSearch");if(mapSearchInput){mapSearchInput.addEventListener("focus",()=>document.body.classList.add("map-search-active"));mapSearchInput.addEventListener("blur",()=>{if(!mapSearchInput.value.trim())document.body.classList.remove("map-search-active");});}
function clearMapVehicleSearch(){const input=document.getElementById('mapVehicleSearch');if(input){input.value='';input.blur();}document.body.classList.remove('map-search-active');searchMapVehicles();}window.clearMapVehicleSearch=clearMapVehicleSearch;
function searchMapVehicles(){const input=document.getElementById('mapVehicleSearch'),box=document.getElementById('mapVehicleSearchResults');if(!input||!box)return;const q=input.value.trim().toLowerCase();if(!q){box.style.display='none';box.innerHTML='';return;}const matches=vehicles.filter(v=>(String(v.vehicleCode||'')+' '+String(v.routeShortName||'')+' '+String(brigadeFor(v))+' '+String(v.destination||v.finalStop||'')).toLowerCase().includes(q)).slice(0,15);box.style.display='block';box.innerHTML=matches.length?matches.map(v=>'<button type="button" data-map-vehicle="'+safe(v.vehicleCode)+'" style="display:block;width:100%;text-align:left;padding:10px;border:0;border-top:1px solid #e6eaf0;background:transparent;color:inherit"><b>🚌 #'+safe(v.vehicleCode)+'</b> · linia '+safe(v.routeShortName)+' · brygada '+safe(brigadeFor(v))+'<br><small>'+safe(v.destination||v.finalStop||'Kierunek niedostępny')+' · opóźnienie: '+safe(formatDelaySeconds(v.delayInSeconds!=null?v.delayInSeconds:v.delay))+'</small></button>').join(''):'<div class="empty">Nie znaleziono aktywnych pojazdów.</div>';}
function safe(value){return String(value==null?'—':value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function table(rows,emptyText){if(!rows.length)return '<div class="empty">'+safe(emptyText)+'</div>';return '<div class="table-wrap"><table><thead><tr><th>Tabor</th><th>Linia</th><th>Brygada</th><th>Przewoźnik</th><th>Akcja</th></tr></thead><tbody>'+rows.map(v=>'<tr><td><button type="button" class="departure-fleet" data-course-vehicle="'+safe(v.vehicleCode)+'">#'+safe(v.vehicleCode)+'</button></td><td><span class="tag">'+safe(v.routeShortName)+'</span></td><td>'+safe(brigadeFor(v))+'</td><td>'+safe(v.carrier)+'</td><td><button class="secondary" data-favorite="'+safe(v.vehicleCode)+'">☆ Ulubione</button></td></tr>').join('')+'</tbody></table></div>';}
function renderActiveTable(){const q=(document.getElementById('fleetFilter')?.value||'').trim().toLowerCase();const rows=vehicles.filter(v=>(String(v.vehicleCode||'')+' '+String(v.routeShortName||'')).toLowerCase().includes(q)).slice().sort((a,b)=>String(a.vehicleCode||'').localeCompare(String(b.vehicleCode||''),undefined,{numeric:true}));document.getElementById('activeTable').innerHTML=table(rows,'Brak pojazdów GPS');}
function getFavorites(){try{return JSON.parse(localStorage.getItem('transportie-favorites')||'[]');}catch(e){return [];}}
function saveFavorites(items){localStorage.setItem('transportie-favorites',JSON.stringify([...new Set(items)]));}
function addFavorite(){const input=document.getElementById('favoriteInput');const code=input.value.trim();if(!code)return;saveFavorites([...getFavorites(),code]);input.value='';renderFavorites();}
function toggleFavorite(code){if(!code)return;const list=getFavorites();saveFavorites(list.includes(String(code))?list.filter(x=>x!==String(code)):[...list,String(code)]);renderFavorites();}
function renderFavorites(){const list=getFavorites();const rows=list.map(code=>{const v=vehicles.find(x=>String(x.vehicleCode)===String(code));return '<tr><td><b>'+safe(code)+'</b></td><td>'+safe(v?.routeShortName||'Poza aktualnym GPS')+'</td><td><button class="secondary" data-favorite="'+safe(code)+'">Usuń</button></td></tr>';}).join('');document.getElementById('favoritesTable').innerHTML=list.length?'<div class="table-wrap"><table><thead><tr><th>Tabor</th><th>Linia</th><th></th></tr></thead><tbody>'+rows+'</tbody></table></div>':'<div class="empty">Nie masz jeszcze ulubionych pojazdów. Dodaj pierwszy numer powyżej.</div>';}
function filterLine(){const q=document.getElementById('lineSearch').value.trim().toLowerCase();const rows=vehicles.filter(v=>String(v.routeShortName||'').toLowerCase()===q).slice().sort((a,b)=>String(a.vehicleCode||'').localeCompare(String(b.vehicleCode||''),undefined,{numeric:true}));document.getElementById('lineResults').innerHTML=table(rows,q?'Nie znaleziono pojazdów na tej linii.':'Wpisz numer linii.');}
window.addFavorite=addFavorite;window.toggleFavorite=toggleFavorite;window.filterLine=filterLine;window.renderActiveTable=renderActiveTable;window.saveLabelSettings=saveLabelSettings;
document.addEventListener('click',function(event){const courseLink=event.target.closest('[data-course-vehicle]');if(courseLink){const code=courseLink.getAttribute('data-course-vehicle');const vehicle=vehicles.find(item=>String(item.vehicleCode||'')===String(code));if(vehicle&&map&&Number.isFinite(Number(vehicle.lat))&&Number.isFinite(Number(vehicle.lon))){showSection('mapa',document.querySelector('nav button'));map.setView([Number(vehicle.lat),Number(vehicle.lon)],17);if(markers[String(code)])openVehicleDetails(vehicle);}else{courseLink.title='Ten pojazd nie raportuje teraz pozycji GPS.';}return;}const fleetLink=event.target.closest('[data-departure-vehicle]');if(fleetLink){const code=fleetLink.getAttribute('data-departure-vehicle');const vehicle=vehicles.find(item=>String(item.vehicleCode||'')===String(code));if(vehicle&&map&&Number.isFinite(Number(vehicle.lat))&&Number.isFinite(Number(vehicle.lon))){showSection('mapa',document.querySelector('nav button'));map.setView([Number(vehicle.lat),Number(vehicle.lon)],17);const vehicleMarker=markers[String(code)];if(vehicleMarker)openVehicleDetails(vehicle);}else{fleetLink.title='Ten pojazd nie raportuje teraz pozycji GPS.';}return;}const button=event.target.closest('[data-favorite]');if(button)toggleFavorite(button.getAttribute('data-favorite'));const stopButton=event.target.closest('[data-stop-departures]');if(stopButton)showStopDepartures(stopButton.getAttribute('data-stop-departures'),stopButton.getAttribute('data-stop-name'));const stopChoice=event.target.closest('[data-stop-select]');if(stopChoice)showStopDepartures(stopChoice.getAttribute('data-stop-select'),stopChoice.getAttribute('data-stop-name'));const scheduleChoice=event.target.closest('[data-schedule-route]');if(scheduleChoice)selectScheduleLine(scheduleChoice.getAttribute('data-schedule-route'));const vehicleChoice=event.target.closest('[data-map-vehicle]');if(vehicleChoice){const id=vehicleChoice.getAttribute('data-map-vehicle'),v=vehicles.find(item=>String(item.vehicleCode||'')===id);if(v&&map&&Number.isFinite(Number(v.lat))&&Number.isFinite(Number(v.lon))){map.setView([Number(v.lat),Number(v.lon)],16);if(markers[id])openVehicleDetails(v);}const box=document.getElementById('mapVehicleSearchResults'),input=document.getElementById('mapVehicleSearch');if(box)box.style.display='none';if(input)input.value=v?(String(v.vehicleCode||'')+' · linia '+String(v.routeShortName||'')):id;}});
async function updateVehicles(){
 if(vehiclesUpdateInFlight||document.hidden)return;
 vehiclesUpdateInFlight=true;
 try{
  const response=await fetch('/api/live',{cache:'no-store'});
  const data=await response.json();
  if(!response.ok||data.error)throw new Error(data.error||('Błąd API GPS ('+response.status+')'));
  vehicles=Array.isArray(data.vehicles)?data.vehicles:[];
  document.getElementById('connection').textContent='GPS aktywny';
  document.getElementById('vehicleCountSettings').textContent='Widoczne pojazdy: '+vehicles.length;
  document.getElementById('lastUpdateSettings').textContent='Ostatnia aktualizacja: '+(data.lastUpdate||'brak danych');
  document.getElementById('dataStatus').textContent='Połączenie z danymi: aktywne';
  const active=new Set();
  for(const v of vehicles){
   const id=String(v.vehicleCode||''),lat=Number(v.lat),lon=Number(v.lon);
   if(!id||!Number.isFinite(lat)||!Number.isFinite(lon))continue;
   active.add(id);
   if(!map)continue;
   const icon=vehicleIcon(v);
   if(markers[id]){
    const marker=markers[id],pos=marker.getLatLng();marker._transportieVehicle=v;
    if(Math.abs(pos.lat-lat)>0.00001||Math.abs(pos.lng-lon)>0.00001)marker.setLatLng([lat,lon]);
    const nextIcon=icon.options&&icon.options.html||'';
    if(marker._transportieIconHtml!==nextIcon){marker.setIcon(icon);marker._transportieIconHtml=nextIcon;}
    if(selectedVehicleCode===id)openVehicleDetails(v);
   }else{
    const marker=L.marker([lat,lon],{icon:icon}).addTo(map);marker._transportieVehicle=v;marker.on('click',()=>openVehicleDetails(marker._transportieVehicle));
    marker._transportieIconHtml=icon.options&&icon.options.html||'';
    
    markers[id]=marker;
   }
  }
  if(map)Object.keys(markers).forEach(id=>{if(!active.has(id)){map.removeLayer(markers[id]);delete markers[id];}});
  if(document.getElementById('wyjechalo').classList.contains('active'))renderActiveTable();
  if(document.getElementById('mapVehicleSearch')?.value.trim())searchMapVehicles();
  if(document.getElementById('ulubione').classList.contains('active'))renderFavorites();
 }catch(error){
  document.getElementById('connection').textContent='Brak połączenia GPS';
  document.getElementById('vehicleCountSettings').textContent='Widoczne pojazdy: —';
  document.getElementById('lastUpdateSettings').textContent='Ostatnia aktualizacja: —';
  document.getElementById('dataStatus').textContent='GPS: '+String(error&&error.message||'błąd połączenia').slice(0,180);
 }finally{vehiclesUpdateInFlight=false;}
}
const summary=document.getElementById('mapLabelSummary');if(summary)summary.textContent='Etykiety: '+([labelSettings.line?'Linia':null,labelSettings.brigade?'Brygada':null,labelSettings.fleet?'Tabor':null].filter(Boolean).join(' · ')||'wyłączone');
updateVehicles();if(map)loadStops();refreshAccount();setInterval(updateVehicles,30000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)updateVehicles();});
</script>
</body>
</html>
"""


@app.get("/api/fleet")
async def fleet():
    global _vehicle_db, _vehicle_db_loaded_at
    try:
        if not _vehicle_db or time.time() - _vehicle_db_loaded_at > 3600:
            headers = {"Accept": "application/json", "User-Agent": "Transportie/1.0 (ZTM Gdansk fleet database)"}
            async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=10.0), follow_redirects=True, headers=headers) as client:
                response = await client.get(VEHICLE_DB_URL)
                response.raise_for_status()
                data = response.json()
            rows = data.get("results", []) if isinstance(data, dict) else data if isinstance(data, list) else []
            if not isinstance(rows, list):
                raise ValueError("Nieprawidłowy format bazy pojazdów.")
            _vehicle_db = {str(item.get("vehicleCode")): item for item in rows if isinstance(item, dict) and item.get("vehicleCode") is not None}
            _vehicle_db_loaded_at = time.time()
        return {"vehicles": list(_vehicle_db.values()), "count": len(_vehicle_db), "lastUpdate": datetime.fromtimestamp(_vehicle_db_loaded_at, ZoneInfo("Europe/Warsaw")).strftime("%Y-%m-%d %H:%M:%S"), "source": "Baza pojazdów ZTM Gdańsk"}
    except Exception as error:
        return JSONResponse(status_code=502, content={"vehicles": [], "count": 0, "error": "Nie udało się pobrać bazy pojazdów ZTM: " + str(error)[:220]})

@app.get("/api/live")
async def live():
    global _vehicle_db, _vehicle_db_loaded_at
    try:
        headers = {
            "Accept": "application/json",
            "User-Agent": "Transportie/1.0 (ZTM Gdansk live tracker)",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=10.0), follow_redirects=True, headers=headers) as client:
            response = await client.get(GPS_URL)
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict):
                raise ValueError("Źródło GPS zwróciło nieoczekiwany format danych.")

            # Static fleet data is optional; GPS must continue working without it.
            if time.time() - _vehicle_db_loaded_at > 3600:
                try:
                    fleet_response = await client.get(VEHICLE_DB_URL)
                    fleet_response.raise_for_status()
                    fleet_data = fleet_response.json()
                    rows = fleet_data.get("results", []) if isinstance(fleet_data, dict) else []
                    _vehicle_db = {
                        str(item.get("vehicleCode")): item
                        for item in rows
                        if isinstance(item, dict) and item.get("vehicleCode") is not None
                    }
                    _vehicle_db_loaded_at = time.time()
                except Exception:
                    pass

        raw_vehicles = data.get("vehicles") or data.get("Vehicles") or []
        if isinstance(raw_vehicles, dict):
            raw_vehicles = list(raw_vehicles.values())
        if not isinstance(raw_vehicles, list):
            raise ValueError("Źródło GPS nie zwróciło listy pojazdów.")

        vehicles = []
        for raw in raw_vehicles:
            if not isinstance(raw, dict):
                continue
            # Normalise documented ZTM v2 names and tolerate legacy capitalised fields.
            vehicle = dict(raw)
            aliases = {
                "vehicleCode": ("VehicleCode",),
                "routeShortName": ("Line", "line"),
                "routeId": ("RouteId", "routeID", "route_id", "routeid"),
                "tripId": ("TripId", "trip_id", "tripID", "Route", "route"),
                "vehicleService": ("VehicleService", "vehicle_service", "BusServiceName", "busServiceName", "bus_service_name"),
                "scheduledTripStartTime": ("ScheduledTripStartTime", "scheduled_trip_start_time", "TripStartTime"),
                "vehicleId": ("VehicleId",),
                "speed": ("Speed",),
                "delay": ("Delay",),
                "lat": ("Lat", "latitude", "Latitude"),
                "lon": ("Lon", "lng", "longitude", "Longitude"),
                "gpsQuality": ("GPSQuality", "gps_quality"),
                "generated": ("DataGenerated", "dataGenerated"),
                "headsign": ("Headsign",),
                "direction": ("Direction",),
            }
            for target, sources in aliases.items():
                if vehicle.get(target) is None:
                    for source in sources:
                        if vehicle.get(source) is not None:
                            vehicle[target] = vehicle[source]
                            break

            code = vehicle.get("vehicleCode")
            fleet = _vehicle_db.get(str(code), {}) if code is not None else {}
            vehicle["carrier"] = (
                fleet.get("carrier")
                or fleet.get("carrirer")
                or fleet.get("operator")
                or "—"
            )
            vehicle["fleetInfo"] = fleet
            vehicles.append(vehicle)

        return {
            "lastUpdate": data.get("lastUpdate"),
            "vehicles": vehicles,
            "count": len(vehicles),
            "source": "ZTM GPS v2",
        }
    except Exception as error:
        return JSONResponse(
            status_code=502,
            content={
                "lastUpdate": None,
                "vehicles": [],
                "count": 0,
                "source": "ZTM GPS v2",
                "error": "Nie udało się pobrać danych GPS ZTM: " + str(error)[:240],
            },
        )

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
async def get_stops(refresh: bool = False):
    global _stops_cache, _stops_loaded_at
    if not refresh and _stops_cache and time.time() - _stops_loaded_at < 86400:
        return {"stops": _stops_cache, "cached": True, "source": "official-stops.json"}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=20.0), follow_redirects=True) as client:
            response = await client.get(STOPS_URL, headers={"Accept": "application/json", "User-Agent": "Transportie-ZTM/1.0"})
            response.raise_for_status()
            raw = response.json()

        # ZTM publikuje dane jako listę albo jako obiekt z kluczem daty,
        # wewnątrz którego znajduje się tablica "stops".
        records = []
        queue = [raw]
        while queue:
            node = queue.pop(0)
            if isinstance(node, list):
                if node and all(isinstance(x, dict) for x in node):
                    # Tablica rekordów przystanków.
                    if any(("stopId" in x or "stop_id" in x) for x in node):
                        records.extend(node)
                    else:
                        queue.extend(node)
                else:
                    queue.extend(x for x in node if isinstance(x, (dict, list)))
            elif isinstance(node, dict):
                stops_list = node.get("stops")
                if isinstance(stops_list, list):
                    queue.append(stops_list)
                else:
                    for key in ("results", "data", "items", "records"):
                        value = node.get(key)
                        if isinstance(value, (dict, list)):
                            queue.append(value)
                    if not any(isinstance(node.get(k), (dict, list)) for k in ("stops", "results", "data", "items", "records")):
                        for value in node.values():
                            if isinstance(value, (dict, list)):
                                queue.append(value)

        normalized = []
        used = set()
        for item in records:
            sid = item.get("stopId", item.get("stop_id", item.get("id")))
            lat = item.get("stopLat", item.get("stop_lat", item.get("lat", item.get("latitude"))))
            lon = item.get("stopLon", item.get("stop_lon", item.get("lon", item.get("longitude"))))
            try:
                lat, lon = float(lat), float(lon)
            except (TypeError, ValueError):
                continue
            if sid is None or not (53.8 <= lat <= 54.8 and 18.0 <= lon <= 19.2):
                continue
            # Korzystamy z dedykowanego, oficjalnego zasobu stopsingdansk.json,
            # więc nie odrzucamy słupków na podstawie opcjonalnego zoneName.
            sid = str(sid)
            if sid in used:
                continue
            used.add(sid)
            normalized.append({
                "stopId": sid,
                "stopName": str(item.get("stopName") or item.get("stopDesc") or item.get("stop_name") or item.get("name") or "Przystanek"),
                "stopCode": str(item.get("stopCode") or item.get("stop_code") or ""),
                "subName": str(item.get("subName") or item.get("sub_name") or ""),
                "lat": lat,
                "lon": lon
            })

        if not normalized:
            return JSONResponse(status_code=502, content={
                "stops": [], "error": "Oficjalny zasób stops.json nie zwrócił rozpoznawalnych przystanków Gdańska.",
                "source_type": type(raw).__name__,
                "top_level_keys": list(raw.keys())[:30] if isinstance(raw, dict) else [],
                "records_found": len(records)
            })
        _stops_cache = normalized
        _stops_loaded_at = time.time()
        return {"stops": normalized, "cached": False, "source": "official-stops.json"}
    except Exception as error:
        return JSONResponse(status_code=502, content={"stops": [], "error": str(error), "source": "official-stops.json"})


@app.get("/api/vehicle-route/{route_id}/{trip_id}")
async def get_vehicle_route(route_id: str, trip_id: str, lat: float = None, lon: float = None, delay: float = None, vehicle_service: str = None, scheduled_trip_start_time: str = None):
    """Return the ordered passenger stops and timetable times for the exact live trip."""
    global _stops_in_trips_cache, _stops_in_trips_loaded_at, _stops_cache, _stops_loaded_at
    try:
        async with httpx.AsyncClient(timeout=35, follow_redirects=True) as client:
            if not _stops_in_trips_cache or time.time() - _stops_in_trips_loaded_at > 86400:
                response = await client.get(STOPS_IN_TRIPS_URL)
                response.raise_for_status()
                raw = response.json()
                records = raw if isinstance(raw, list) else []
                if isinstance(raw, dict):
                    records = raw.get("stopsInTrip") or raw.get("results") or raw.get("data") or []
                    if not records:
                        dated = [
                            (key, value.get("stopsInTrip"))
                            for key, value in raw.items()
                            if isinstance(value, dict) and isinstance(value.get("stopsInTrip"), list)
                        ]
                        if dated:
                            records = sorted(dated, key=lambda entry: entry[0])[-1][1]
                _stops_in_trips_cache = records if isinstance(records, list) else []
                _stops_in_trips_loaded_at = time.time()

            if not _stops_cache or time.time() - _stops_loaded_at > 86400:
                stops_response = await client.get(STOPS_URL)
                stops_response.raise_for_status()
                stop_raw = stops_response.json()
                stop_records = stop_raw if isinstance(stop_raw, list) else []
                if isinstance(stop_raw, dict):
                    stop_records = stop_raw.get("stops") or stop_raw.get("results") or stop_raw.get("data") or []
                    if not stop_records:
                        dated = [
                            (key, value.get("stops"))
                            for key, value in stop_raw.items()
                            if isinstance(value, dict) and isinstance(value.get("stops"), list)
                        ]
                        if dated:
                            stop_records = sorted(dated, key=lambda entry: entry[0])[-1][1]
                _stops_cache = stop_records if isinstance(stop_records, list) else []
                _stops_loaded_at = time.time()

        stop_lookup = {}
        for stop in _stops_cache:
            if not isinstance(stop, dict):
                continue
            sid = stop.get("stopId", stop.get("stop_id", stop.get("id")))
            if sid is None:
                continue
            try:
                stop_lat = float(stop.get("stopLat", stop.get("stop_lat", stop.get("lat", stop.get("latitude")))))
                stop_lon = float(stop.get("stopLon", stop.get("stop_lon", stop.get("lon", stop.get("longitude")))))
            except (TypeError, ValueError):
                stop_lat, stop_lon = None, None
            stop_lookup[str(sid)] = {
                "stopId": str(sid),
                "name": stop.get("stopName") or stop.get("stopDesc") or stop.get("stop_name") or stop.get("name") or "Przystanek",
                "code": stop.get("subName") or stop.get("stopCode") or "",
                "lat": stop_lat,
                "lon": stop_lon,
            }

        matches = [
            row for row in _stops_in_trips_cache
            if isinstance(row, dict)
            and str(row.get("routeId")) == str(route_id)
            and str(row.get("tripId")) == str(trip_id)
        ]
        matches.sort(key=lambda row: int(row.get("stopSequence") or 0))

        # Match timetable to the live vehicle, tolerating different tripId formats.
        scheduled_by_stop = {}
        scheduled_by_sequence = {}
        schedule_row_count = 0
        schedule_match = "none"
        schedule_diagnostics = {
            "date": datetime.now(ZoneInfo("Europe/Warsaw")).strftime("%Y-%m-%d"),
            "tripStops": len(matches),
            "routeRows": 0,
            "tripRows": 0,
            "serviceRows": 0,
            "tripIds": [],
            "sampleKeys": [],
            "sampleRows": [],
            "error": None,
        }
        try:
            today = datetime.now(ZoneInfo("Europe/Warsaw")).strftime("%Y-%m-%d")
            cache_key = today + ":" + str(route_id)
            cached = _stop_times_cache.get(cache_key)
            if not cached or time.time() - cached.get("loaded_at", 0) > 1800:
                schedule_records = []
                last_error = None
                for base_url in ("https://ckan2.multimediagdansk.pl/stopTimes", "http://ckan2.multimediagdansk.pl/stopTimes"):
                    try:
                        schedule_response = await client.get(base_url, params={"date": today, "routeId": route_id})
                        schedule_response.raise_for_status()
                        schedule_raw = schedule_response.json()
                        if isinstance(schedule_raw, list):
                            schedule_records = schedule_raw
                        elif isinstance(schedule_raw, dict):
                            candidate = schedule_raw.get("stopTimes") or schedule_raw.get("stop_times") or schedule_raw.get("results") or schedule_raw.get("data") or []
                            if isinstance(candidate, dict):
                                candidate = candidate.get("stopTimes") or candidate.get("stop_times") or candidate.get("results") or []
                            if not candidate:
                                for value in schedule_raw.values():
                                    if isinstance(value, dict):
                                        candidate = value.get("stopTimes") or value.get("stop_times") or value.get("results") or []
                                        if candidate:
                                            break
                            schedule_records = candidate if isinstance(candidate, list) else []
                        break
                    except Exception as fetch_error:
                        last_error = fetch_error
                if not schedule_records and last_error:
                    raise last_error
                cached = {"loaded_at": time.time(), "records": schedule_records}
                _stop_times_cache[cache_key] = cached

            schedule_rows = [item for item in cached.get("records", []) if isinstance(item, dict)]
            schedule_row_count = len(schedule_rows)
            if schedule_rows:
                schedule_diagnostics["sampleKeys"] = sorted(schedule_rows[0].keys())[:30]
                schedule_diagnostics["sampleRows"] = [
                    {key: item.get(key) for key in ("routeId", "tripId", "stopId", "stopSequence", "departureTime", "arrivalTime", "busServiceName", "vehicleService")}
                    for item in schedule_rows[:3]
                ]
            def norm_id(value):
                return str(value).strip().replace(".0", "") if value is not None else ""
            route_schedule = [item for item in schedule_rows if norm_id(item.get("routeId") or item.get("route_id")) == norm_id(route_id)]
            trip_schedule = [item for item in route_schedule if norm_id(item.get("tripId") or item.get("trip_id")) == norm_id(trip_id)]
            if not trip_schedule:
                trip_schedule = [item for item in schedule_rows if norm_id(item.get("tripId") or item.get("trip_id")) == norm_id(trip_id)]
            route_stop_ids = {norm_id(row.get("stopId") or row.get("stop_id")) for row in matches}
            schedule_diagnostics["routeRows"] = len(route_schedule)
            if route_schedule:
                schedule_diagnostics["sampleRows"] = [
                    {key: item.get(key) for key in ("routeId", "tripId", "stopId", "stopSequence", "departureTime", "arrivalTime", "busServiceName", "vehicleService")}
                    for item in route_schedule[:5]
                ]
            schedule_diagnostics["tripRows"] = len(trip_schedule)
            if vehicle_service:
                # Najpierw ograniczamy dane do wariantu GPS (tripId), dopiero potem
                # do zadania pojazdu (vehicleService). Filtrowanie po samym
                # vehicleService mieszało kursy jadące różnymi wariantami tej samej linii.
                service_rows = [
                    item for item in trip_schedule
                    if norm_id(item.get("busServiceName") or item.get("bus_service_name") or item.get("vehicleService") or item.get("vehicle_service")) == norm_id(vehicle_service)
                ]
                schedule_diagnostics["serviceRows"] = len(service_rows)
                if service_rows:
                    # vehicleService identifies the vehicle's duty; "order" separates
                    # individual runs within that duty. GPS scheduledTripStartTime
                    # selects the exact run instead of mixing every run on the variant.
                    service_groups = {}
                    for item in service_rows:
                        service_groups.setdefault(norm_id(item.get("order")), []).append(item)
                    if scheduled_trip_start_time and service_groups:
                        try:
                            gps_start = datetime.fromisoformat(str(scheduled_trip_start_time).replace("Z", "+00:00"))
                            if gps_start.tzinfo is not None:
                                gps_start = gps_start.astimezone(ZoneInfo("Europe/Warsaw"))
                            gps_seconds = gps_start.hour * 3600 + gps_start.minute * 60 + gps_start.second

                            def run_start_seconds(group):
                                first = min(group, key=lambda item: int(item.get("stopSequence") or item.get("stop_sequence") or 0))
                                raw_value = first.get("departureTime") or first.get("departure_time") or first.get("arrivalTime") or first.get("arrival_time")
                                parsed = datetime.fromisoformat(str(raw_value).replace("Z", "+00:00"))
                                return parsed.hour * 3600 + parsed.minute * 60 + parsed.second

                            def start_distance(group):
                                seconds = run_start_seconds(group)
                                diff = abs(seconds - gps_seconds)
                                return min(diff, abs(diff - 86400), abs(diff + 86400))

                            best_group = min(service_groups.values(), key=start_distance)
                            trip_schedule = best_group
                            schedule_match = "vehicleService+scheduledTripStartTime"
                        except (TypeError, ValueError, OverflowError):
                            if not trip_schedule and len(service_groups) == 1:
                                trip_schedule = next(iter(service_groups.values()))
                                schedule_match = "vehicleService(uniqueOrder)"
                    elif not trip_schedule and len(service_groups) == 1:
                        trip_schedule = next(iter(service_groups.values()))
                        schedule_match = "vehicleService(uniqueOrder)"
                    elif not trip_schedule:
                        ranked_service = sorted(
                            service_groups.values(),
                            key=lambda group: len(route_stop_ids.intersection({norm_id(item.get("stopId") or item.get("stop_id")) for item in group})),
                            reverse=True,
                        )
                        if ranked_service:
                            best_service = ranked_service[0]
                            overlap = route_stop_ids.intersection({norm_id(item.get("stopId") or item.get("stop_id")) for item in best_service})
                            if overlap:
                                trip_schedule = best_service
                                schedule_match = "vehicleService+stopOverlap"
            if trip_schedule and schedule_match == "none":
                schedule_match = "tripId"
            if not trip_schedule and route_schedule:
                grouped = {}
                for item in route_schedule:
                    key = norm_id(item.get("tripId") or item.get("trip_id"))
                    grouped.setdefault(key, []).append(item)
                ranked = sorted(
                    grouped.values(),
                    key=lambda group: len(route_stop_ids.intersection({norm_id(item.get("stopId") or item.get("stop_id")) for item in group})),
                    reverse=True,
                )
                if ranked:
                    best = ranked[0]
                    overlap = route_stop_ids.intersection({norm_id(item.get("stopId")) for item in best})
                    if overlap:
                        trip_schedule = best
                        schedule_match = "bestStopSequence"
            schedule_diagnostics["tripIds"] = sorted({norm_id(item.get("tripId") or item.get("trip_id")) for item in route_schedule if norm_id(item.get("tripId") or item.get("trip_id"))})[:8]
            for item in trip_schedule:
                sid = norm_id(item.get("stopId") or item.get("stop_id"))
                value = (item.get("departureTime") or item.get("arrivalTime") or
                         item.get("departure_time") or item.get("arrival_time") or
                         item.get("departure") or item.get("arrival") or item.get("time"))
                if sid and value:
                    scheduled_by_stop[sid] = value
                sequence = norm_id(item.get("stopSequence") or item.get("stop_sequence"))
                if sequence and value:
                    scheduled_by_sequence[sequence] = value
        except Exception as schedule_error:
            scheduled_by_stop = {}
            scheduled_by_sequence = {}
            schedule_match = "error: " + str(schedule_error)[:120]
            schedule_diagnostics["error"] = str(schedule_error)[:220]

        result = []
        for row in matches:
            if row.get("passenger") is False:
                continue
            sid = str(row.get("stopId", ""))
            stop = stop_lookup.get(sid, {"stopId": sid, "name": "Przystanek", "code": "", "lat": None, "lon": None})
            sequence_key = str(row.get("stopSequence", row.get("stop_sequence", ""))).strip().replace(".0", "")
            time_value = scheduled_by_stop.get(str(sid).strip().replace(".0", "")) or scheduled_by_sequence.get(sequence_key)
            scheduled_time = None
            estimated_time = None
            if time_value:
                try:
                    raw_time = str(time_value).replace("Z", "+00:00")
                    try:
                        parsed = datetime.fromisoformat(raw_time)
                    except ValueError:
                        parsed = datetime.strptime(raw_time[:8], "%H:%M:%S")
                    scheduled_time = parsed.strftime("%H:%M")
                    if delay is not None:
                        adjusted = datetime(2000, 1, 1, parsed.hour, parsed.minute, parsed.second) + timedelta(seconds=delay)
                        estimated_time = adjusted.strftime("%H:%M")
                except (TypeError, ValueError):
                    pass
            result.append({
                "stopId": sid,
                "name": stop["name"],
                "code": stop["code"],
                "sequence": row.get("stopSequence"),
                "lat": stop["lat"],
                "lon": stop["lon"],
                "scheduledTime": scheduled_time,
                "estimatedTime": estimated_time,
            })

        # Approximate the vehicle's progress using the closest stop on this trip.
        # If the GPS position is far from the route, keep the complete list.
        current_index = 0
        if lat is not None and lon is not None and result:
            distances = []
            for index, stop in enumerate(result):
                if stop["lat"] is None or stop["lon"] is None:
                    continue
                p1, p2 = math.radians(lat), math.radians(stop["lat"])
                dp = math.radians(stop["lat"] - lat)
                dl = math.radians(stop["lon"] - lon)
                a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
                distances.append((2 * 6371000 * math.asin(min(1, math.sqrt(a))), index))
            if distances:
                nearest_distance, nearest_index = min(distances)
                if nearest_distance <= 1500:
                    current_index = nearest_index
        return {
            "routeId": route_id,
            "tripId": trip_id,
            "stops": result,
            "count": len(result),
            "currentIndex": current_index,
            "scheduleRows": schedule_row_count,
            "scheduleMatch": schedule_match,
            "timesFound": len(scheduled_by_stop),
            "diagnostics": schedule_diagnostics,
            "source": "ZTM stopsInTrip + stops + stopTimes",
        }
    except Exception as error:
        return JSONResponse(
            status_code=502,
            content={"stops": [], "count": 0, "error": "Nie udało się pobrać przystanków kursu: " + str(error)[:220]},
        )

@app.get("/api/vehicle-duty/{route_id}/{vehicle_service}")
async def get_vehicle_duty(route_id: str, vehicle_service: str):
    """Return all trips and passenger stop times for one ZTM vehicle duty today."""
    global _stops_cache, _stops_loaded_at, _stop_times_cache
    try:
        today = datetime.now(ZoneInfo("Europe/Warsaw")).strftime("%Y-%m-%d")
        cache_key = today + ":" + str(route_id)
        cached = _stop_times_cache.get(cache_key)
        async with httpx.AsyncClient(timeout=40, follow_redirects=True) as client:
            if not _stops_cache or time.time() - _stops_loaded_at > 86400:
                stop_response = await client.get(STOPS_URL)
                stop_response.raise_for_status()
                raw_stops = stop_response.json()
                stop_records = raw_stops if isinstance(raw_stops, list) else []
                if isinstance(raw_stops, dict):
                    stop_records = raw_stops.get("stops") or raw_stops.get("results") or raw_stops.get("data") or []
                    if not stop_records:
                        dated = [(key, value.get("stops")) for key, value in raw_stops.items()
                                 if isinstance(value, dict) and isinstance(value.get("stops"), list)]
                        if dated:
                            stop_records = sorted(dated, key=lambda item: item[0])[-1][1]
                _stops_cache = stop_records if isinstance(stop_records, list) else []
                _stops_loaded_at = time.time()
            if not cached or time.time() - cached.get("loaded_at", 0) > 1800:
                schedule_response = await client.get("https://ckan2.multimediagdansk.pl/stopTimes",
                                                     params={"date": today, "routeId": route_id})
                schedule_response.raise_for_status()
                raw_schedule = schedule_response.json()
                schedule_records = raw_schedule if isinstance(raw_schedule, list) else []
                if isinstance(raw_schedule, dict):
                    schedule_records = (raw_schedule.get("stopTimes") or raw_schedule.get("stop_times") or
                                        raw_schedule.get("results") or raw_schedule.get("data") or [])
                    if isinstance(schedule_records, dict):
                        schedule_records = (schedule_records.get("stopTimes") or
                                            schedule_records.get("stop_times") or
                                            schedule_records.get("results") or [])
                    if not schedule_records:
                        for value in raw_schedule.values():
                            if isinstance(value, dict):
                                schedule_records = (value.get("stopTimes") or value.get("stop_times") or
                                                    value.get("results") or [])
                                if schedule_records:
                                    break
                cached = {"loaded_at": time.time(),
                          "records": schedule_records if isinstance(schedule_records, list) else []}
                _stop_times_cache[cache_key] = cached
        def norm(value):
            return str(value).strip().replace(".0", "") if value is not None else ""
        wanted_service = norm(vehicle_service)
        duty_rows = [row for row in cached.get("records", [])
                     if isinstance(row, dict) and norm(row.get("busServiceName") or
                        row.get("bus_service_name") or row.get("vehicleService") or
                        row.get("vehicle_service")) == wanted_service]
        if not duty_rows:
            return {"date": today, "vehicleService": vehicle_service, "courses": [],
                    "count": 0, "source": "ZTM stopTimes"}
        stop_lookup = {}
        for item in _stops_cache:
            if not isinstance(item, dict):
                continue
            sid = item.get("stopId", item.get("stop_id", item.get("id")))
            if sid is None:
                continue
            stop_lookup[norm(sid)] = {
                "name": item.get("stopName") or item.get("stopDesc") or
                        item.get("stop_name") or item.get("name") or "Przystanek",
                "code": item.get("subName") or item.get("stopCode") or "",
            }
        grouped = {}
        for row in duty_rows:
            order = norm(row.get("order")) or norm(row.get("tripId") or row.get("trip_id"))
            grouped.setdefault(order, []).append(row)
        courses = []
        for order, rows in grouped.items():
            rows.sort(key=lambda item: int(item.get("stopSequence") or item.get("stop_sequence") or 0))
            passenger_stops = []
            for item in rows:
                if item.get("passenger") is False or str(item.get("nonpassenger", "0")) == "1":
                    continue
                sid = norm(item.get("stopId") or item.get("stop_id"))
                info = stop_lookup.get(sid, {})
                raw_time = (item.get("departureTime") or item.get("departure_time") or
                            item.get("arrivalTime") or item.get("arrival_time"))
                try:
                    parsed = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
                    clock = parsed.strftime("%H:%M")
                except (TypeError, ValueError):
                    clock = str(raw_time)[11:16] if raw_time and len(str(raw_time)) >= 16 else "—"
                passenger_stops.append({
                    "stopId": sid,
                    "name": info.get("name") or "Przystanek",
                    "code": info.get("code") or "",
                    "sequence": item.get("stopSequence") or item.get("stop_sequence"),
                    "time": clock,
                })
            if passenger_stops:
                courses.append({
                    "order": order,
                    "tripId": rows[0].get("tripId") or rows[0].get("trip_id"),
                    "startTime": passenger_stops[0]["time"],
                    "endTime": passenger_stops[-1]["time"],
                    "headsign": passenger_stops[-1]["name"],
                    "stops": passenger_stops,
                })
        def sort_course(course):
            try:
                order_value = int(course.get("order") or 0)
            except (TypeError, ValueError):
                order_value = 0
            return (course.get("startTime") or "99:99", order_value)
        courses.sort(key=sort_course)
        return {"date": today, "vehicleService": vehicle_service, "courses": courses,
                "count": len(courses), "source": "ZTM stopTimes + stops"}
    except Exception as error:
        return JSONResponse(status_code=502, content={
            "courses": [],
            "error": "Nie udało się pobrać rozkładu brygady ZTM: " + str(error)[:220],
        })

@app.get("/api/routes")
async def get_routes():
    """Return the current passenger line list from ZTM static data."""
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            response = await client.get("https://ckan.multimediagdansk.pl/dataset/c24aa637-3619-4dc2-a171-a23eec8f2172/resource/22313c56-5acf-41c7-a5fd-dc5dc72b3851/download/routes.json")
            response.raise_for_status()
            raw = response.json()
        records = raw if isinstance(raw, list) else []
        if isinstance(raw, dict):
            dated = [(key, value.get("routes")) for key, value in raw.items()
                     if isinstance(value, dict) and isinstance(value.get("routes"), list)]
            if dated:
                records = sorted(dated, key=lambda item: item[0])[-1][1]
            else:
                records = raw.get("routes") or raw.get("results") or []
        routes = [item for item in records if isinstance(item, dict)
                  and item.get("routeId") is not None
                  and str(item.get("routeShortName") or "").strip()]
        routes.sort(key=lambda item: (not str(item.get("routeShortName") or "").isdigit(),
                                      str(item.get("routeShortName") or "")))
        return {"routes": routes}
    except Exception as error:
        return JSONResponse(status_code=502, content={"routes": [], "error": str(error)})


@app.get("/api/line-schedule/{route_id}")
async def get_line_schedule(route_id: str):
    """Return today's timetable grouped into individual courses for one line."""
    global _stops_cache, _stops_loaded_at, _stops_in_trips_cache, _stops_in_trips_loaded_at
    try:
        today = datetime.now(ZoneInfo("Europe/Warsaw")).strftime("%Y-%m-%d")
        async with httpx.AsyncClient(timeout=40, follow_redirects=True) as client:
            schedule_response = await client.get("https://ckan2.multimediagdansk.pl/stopTimes",
                                                 params={"date": today, "routeId": route_id})
            schedule_response.raise_for_status()
            raw_schedule = schedule_response.json()
            rows = raw_schedule if isinstance(raw_schedule, list) else []
            if isinstance(raw_schedule, dict):
                rows = raw_schedule.get("stopTimes") or raw_schedule.get("stop_times") or raw_schedule.get("results") or []
                if not rows:
                    for value in raw_schedule.values():
                        if isinstance(value, dict):
                            rows = value.get("stopTimes") or value.get("stop_times") or value.get("results") or []
                            if rows:
                                break
            if not _stops_cache or time.time() - _stops_loaded_at > 86400:
                stop_response = await client.get(STOPS_URL)
                stop_response.raise_for_status()
                raw_stops = stop_response.json()
                stop_rows = raw_stops if isinstance(raw_stops, list) else []
                if isinstance(raw_stops, dict):
                    stop_rows = raw_stops.get("stops") or raw_stops.get("results") or raw_stops.get("data") or []
                    if not stop_rows:
                        dated = [(key, value.get("stops")) for key, value in raw_stops.items()
                                 if isinstance(value, dict) and isinstance(value.get("stops"), list)]
                        if dated:
                            stop_rows = sorted(dated, key=lambda item: item[0])[-1][1]
                _stops_cache = stop_rows if isinstance(stop_rows, list) else []
                _stops_loaded_at = time.time()
            if not _stops_in_trips_cache or time.time() - _stops_in_trips_loaded_at > 86400:
                trips_response = await client.get(STOPS_IN_TRIPS_URL)
                trips_response.raise_for_status()
                raw_trips = trips_response.json()
                trip_rows = raw_trips if isinstance(raw_trips, list) else []
                if isinstance(raw_trips, dict):
                    trip_rows = raw_trips.get("stopsInTrip") or raw_trips.get("results") or raw_trips.get("data") or []
                    if not trip_rows:
                        dated = [(key, value.get("stopsInTrip")) for key, value in raw_trips.items()
                                 if isinstance(value, dict) and isinstance(value.get("stopsInTrip"), list)]
                        if dated:
                            trip_rows = sorted(dated, key=lambda item: item[0])[-1][1]
                _stops_in_trips_cache = trip_rows if isinstance(trip_rows, list) else []

        stop_lookup = {}
        for item in _stops_cache:
            if not isinstance(item, dict):
                continue
            sid = item.get("stopId", item.get("stop_id", item.get("id")))
            if sid is not None:
                stop_lookup[str(sid)] = item.get("stopName") or item.get("stopDesc") or item.get("stop_name") or "Przystanek"
        trip_stops = {}
        for item in _stops_in_trips_cache:
            if not isinstance(item, dict) or str(item.get("routeId")) != str(route_id):
                continue
            trip_stops.setdefault(str(item.get("tripId")), []).append(item)
        grouped = {}
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            key = (str(row.get("tripId", "")), str(row.get("busServiceName") or ""), str(row.get("order") or ""))
            grouped.setdefault(key, []).append(row)
        courses = []
        for (trip_id, service, order), course_rows in grouped.items():
            course_rows.sort(key=lambda item: int(item.get("stopSequence") or 0))
            stops = []
            for row in course_rows:
                sid = str(row.get("stopId", ""))
                departure = str(row.get("departureTime") or row.get("arrivalTime") or "")
                clock = departure[-8:-3] if "T" in departure else departure[:5]
                stops.append({"stopId": sid, "name": stop_lookup.get(sid, "Przystanek"),
                              "time": clock, "sequence": int(row.get("stopSequence") or 0),
                              "note": row.get("noteDescription") or row.get("noteSymbol") or ""})
            if not stops:
                continue
            last_name = ""
            ordered_trip_stops = sorted(trip_stops.get(trip_id, []), key=lambda item: int(item.get("stopSequence") or 0))
            if ordered_trip_stops:
                last_name = stop_lookup.get(str(ordered_trip_stops[-1].get("stopId")), "")
            courses.append({"tripId": trip_id, "service": service, "order": order,
                            "direction": last_name or stops[-1]["name"],
                            "start": next((stop["time"] for stop in stops if stop["time"]), ""),
                            "stops": stops})
        courses.sort(key=lambda item: (item["start"] or "99:99", item["service"], item["order"]))
        return {"date": today, "courses": courses, "count": len(courses)}
    except Exception as error:
        return JSONResponse(status_code=502, content={"courses": [], "error": str(error)})


@app.get("/api/departures/{stop_id}")
async def get_departures(stop_id: str):
    """Return normalized live departures for one physical ZTM stop pole."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=10.0), follow_redirects=True) as client:
            response = await client.get(
                DEPARTURES_URL,
                params={"stopId": stop_id},
                headers={"Accept": "application/json", "User-Agent": "Transportie-ZTM/1.0"},
            )
            response.raise_for_status()
            data = response.json()

        # The CKAN2 feed has appeared both as {departures:[...]} and as
        # date-keyed / nested JSON. Find the actual departure rows instead
        # of silently returning an empty board for an unfamiliar wrapper.
        rows = []
        queue = [data]
        last_update = None
        while queue:
            node = queue.pop(0)
            if isinstance(node, list):
                if node and all(isinstance(x, dict) for x in node) and any(
                    key in x for x in node for key in ("routeId", "routeShortName", "estimatedTime", "theoreticalTime", "vehicleCode")
                ):
                    rows.extend(node)
                else:
                    queue.extend(x for x in node if isinstance(x, (dict, list)))
            elif isinstance(node, dict):
                last_update = last_update or node.get("lastUpdate") or node.get("last_update")
                found = False
                for key in ("departures", "departure", "results", "data", "items"):
                    value = node.get(key)
                    if isinstance(value, list):
                        queue.append(value)
                        found = True
                    elif isinstance(value, dict):
                        queue.append(value)
                        found = True
                if not found:
                    queue.extend(value for value in node.values() if isinstance(value, (dict, list)))

        normalized = []
        seen = set()
        for row in rows:
            route = row.get("routeShortName") or row.get("route_short_name") or row.get("route") or row.get("routeId") or row.get("route_id") or ""
            direction = row.get("headsign") or row.get("direction") or row.get("destination") or row.get("tripHeadsign") or ""
            vehicle = (row.get("vehicleCode") or row.get("vehicle_code") or row.get("vehicleId") or
                       row.get("vehicle_id") or row.get("vehicleNumber") or row.get("vehicle_number") or
                       row.get("fleetNumber") or row.get("vehicleNumber"))
            estimated = (row.get("estimatedTime") or row.get("estimated_time") or row.get("expectedTime") or
                         row.get("arrivalTime") or row.get("departureTime") or row.get("time"))
            theoretical = row.get("theoreticalTime") or row.get("theoretical_time") or row.get("scheduledTime")
            identity = (str(route), str(direction), str(vehicle), str(estimated), str(theoretical))
            if identity in seen:
                continue
            seen.add(identity)
            normalized.append({
                **row,
                "routeShortName": str(route) if route != "" else "—",
                "headsign": str(direction) if direction else "Kierunek nieznany",
                "vehicleCode": str(vehicle) if vehicle not in (None, "") else None,
                "estimatedTime": estimated,
                "theoreticalTime": theoretical,
                "delayInSeconds": row.get("delayInSeconds", row.get("delay_in_seconds")),
            })
        normalized.sort(key=lambda item: str(item.get("estimatedTime") or item.get("theoreticalTime") or ""))
        return {"lastUpdate": last_update, "departures": normalized[:30], "count": len(normalized)}
    except Exception as error:
        return JSONResponse(status_code=502, content={"departures": [], "error": str(error)[:240]})
