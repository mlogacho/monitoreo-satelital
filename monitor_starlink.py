import os
import time
import json
from datetime import datetime
from playwright.sync_api import sync_playwright

SESSION_FILE = "state.json"
DATA_FILE = "starlink_data.json"

def fetch_starlink_data():
    print(f"[{datetime.now()}] Iniciando chequeo automático de Starlink (Modo Rápido Corregido)...")
    
    if not os.path.exists(SESSION_FILE):
        print("❌ Error: No se encontró el archivo de sesión 'state.json'.")
        return
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(storage_state=SESSION_FILE)
        page = context.new_page()

        page.goto("https://www.starlink.com/account/subscriptions")
        time.sleep(10)
        
        subscriptions = []
        
        options_count = 1
        try:
            avatar = page.locator("button", has_text="ML").first
            if avatar.is_visible():
                avatar.click()
                time.sleep(3)
                combobox = page.locator('li[role="combobox"]')
                if combobox.is_visible():
                    combobox.click()
                    time.sleep(3)
                    options_count = page.locator('li:has-text("ACC-")').count()
                    if options_count == 0:
                        options_count = 1
                    page.keyboard.press("Escape")
                    time.sleep(2)
        except Exception as e:
            print(f"No se pudo determinar cuentas múltiples, asumiendo 1. {e}")

        for i in range(1, max(2, options_count)):
            try:
                page.goto("https://www.starlink.com/account/subscriptions")
                time.sleep(8)
                
                if options_count > 1:
                    avatar = page.locator("button", has_text="ML").first
                    if avatar.is_visible():
                        avatar.click()
                        time.sleep(2)
                        combobox = page.locator('li[role="combobox"]')
                        if combobox.is_visible():
                            combobox.click()
                            time.sleep(2)
                            opt = page.locator('li:has-text("ACC-")').nth(i)
                            if opt.is_visible():
                                opt.click()
                                time.sleep(10)
                
                # Extraccion rápida agrupando por href
                links = page.locator("a[href*='/account/service-line/']").all()
                
                href_groups = {}
                for link in links:
                    href = link.get_attribute("href")
                    text = link.inner_text().strip()
                    if href and text:
                        if href not in href_groups:
                            href_groups[href] = []
                        href_groups[href].append(text)
                        
                for href, texts in href_groups.items():
                    nombre = texts[0] if len(texts) > 0 else href.split("/")[-1]
                    ubicacion = ""
                    estado_val = "Inactivo"
                    
                    for t in texts:
                        if "Ubicación:" in t or "Location:" in t:
                            ubicacion = t.replace("Ubicación:", "").replace("Location:", "").strip()
                        if "Activo" in t or "Active" in t:
                            estado_val = "Activo"
                            
                    subscriptions.append({
                        "nombre": nombre,
                        "ubicacion": ubicacion,
                        "estado": estado_val,
                        "uso_datos": "N/A"
                    })
            except Exception as e:
                print(f"Error procesando cuenta {i}: {e}")
        
        unique_subs = {sub['nombre']: sub for sub in subscriptions}.values()
        final_list = list(unique_subs)
        
        if final_list:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump({"timestamp": datetime.now().isoformat(), "data": final_list}, f, indent=4, ensure_ascii=False)
            
            generate_static_dashboard(final_list, datetime.now().isoformat())
        else:
            print("⚠️ No se extrajeron antenas.")

        browser.close()

def generate_static_dashboard(data, timestamp):
    html_template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monitoreo Satelital</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
    <style>
        :root {
            --bg-color: #0f172a; --card-bg: rgba(30, 41, 59, 0.7); --card-border: rgba(255, 255, 255, 0.1);
            --text-main: #f8fafc; --text-muted: #94a3b8; --active-color: #10b981; --active-bg: rgba(16, 185, 129, 0.15);
            --inactive-color: #ef4444; --inactive-bg: rgba(239, 68, 68, 0.15); --accent: #3b82f6;
        }
        body { margin: 0; font-family: 'Inter', sans-serif; background-color: var(--bg-color); color: var(--text-main); min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }
        header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 20px; border-bottom: 1px solid var(--card-border); }
        h1 { margin: 0; font-size: 28px; }
        .meta-info { text-align: right; font-size: 14px; color: var(--text-muted); }
        
        .tabs { display: flex; gap: 10px; margin-bottom: 30px; }
        .tab-btn { background: var(--card-bg); border: 1px solid var(--card-border); color: var(--text-main); padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: 15px; font-weight: 500; transition: all 0.2s; }
        .tab-btn:hover { background: rgba(255,255,255,0.1); }
        .tab-btn.active { background: var(--accent); color: white; border-color: var(--accent); }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 24px; }
        .card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 16px; padding: 24px; display: flex; flex-direction: column; gap: 16px; }
        .card-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
        .antena-name { font-size: 18px; margin: 0; }
        .status-badge { padding: 6px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; }
        .status-active { background-color: var(--active-bg); color: var(--active-color); border: 1px solid rgba(16, 185, 129, 0.2); }
        .status-inactive { background-color: var(--inactive-bg); color: var(--inactive-color); border: 1px solid rgba(239, 68, 68, 0.2); }
        .info-row { font-size: 14px; color: var(--text-muted); margin-bottom: 8px;}
        .location-value { color: var(--text-main); font-family: monospace; background: rgba(0,0,0,0.2); padding: 2px 6px; border-radius: 4px; }
        .stats-summary { display: flex; gap: 20px; margin-bottom: 30px; }
        .stat-box { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 16px 24px; }
        .stat-value { font-size: 24px; font-weight: 700; }
        .stat-active .stat-value { color: var(--active-color); }
        .stat-inactive .stat-value { color: var(--inactive-color); }
        
        #map-view { display: none; height: 600px; width: 100%; border-radius: 16px; overflow: hidden; border: 1px solid var(--card-border); }
        .leaflet-popup-content-wrapper { background: var(--bg-color); color: var(--text-main); }
        .leaflet-popup-tip { background: var(--bg-color); }
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1>Monitoreo Satelital (Modo Rápido)</h1>
        <div class="meta-info">
            <div>Última actualización: <span id="timestamp"></span></div>
            <div>Total: <span id="total"></span> antenas</div>
        </div>
    </header>
    
    <div class="stats-summary">
        <div class="stat-box stat-active"><div class="stat-value" id="active-count">0</div><div>Activas</div></div>
        <div class="stat-box stat-inactive"><div class="stat-value" id="inactive-count">0</div><div>Inactivas</div></div>
    </div>

    <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('list')">Lista de Antenas</button>
        <button class="tab-btn" onclick="switchTab('map')">Mapa de Ecuador</button>
    </div>

    <div id="list-view" class="grid"></div>
    <div id="map-view"></div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
    const data = REPLACE_ME_DATA;
    const timestamp = "REPLACE_ME_TIMESTAMP";
    
    document.getElementById('timestamp').textContent = new Date(timestamp).toLocaleString();
    document.getElementById('total').textContent = data.length;
    
    let active = 0; let inactive = 0;
    const grid = document.getElementById('list-view');
    
    const map = L.map('map-view').setView([-1.8312, -78.1834], 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        className: 'map-tiles'
    }).addTo(map);
    
    data.forEach(a => {
        const isActive = a.estado.toLowerCase() === 'activo';
        if (isActive) active++; else inactive++;
        
        grid.innerHTML += `
            <div class="card">
                <div class="card-header">
                    <h2 class="antena-name">${a.nombre}</h2>
                    <span class="status-badge ${isActive ? 'status-active' : 'status-inactive'}">${isActive ? 'Activo' : 'Inactivo'}</span>
                </div>
                <div>
                    <div class="info-row">Ubicación GPS: <span class="location-value">${a.ubicacion}</span></div>
                    <div class="info-row">Estado: ${a.estado}</div>
                </div>
            </div>
        `;
        
        const coords = a.ubicacion.split(',');
        if (coords.length === 2) {
            const lat = parseFloat(coords[0].trim());
            const lng = parseFloat(coords[1].trim());
            if (!isNaN(lat) && !isNaN(lng)) {
                L.circleMarker([lat, lng], {
                    radius: 8,
                    fillColor: isActive ? '#10b981' : '#ef4444',
                    color: '#fff',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.9
                }).bindPopup(`<strong>${a.nombre}</strong><br>Estado: ${a.estado}`).addTo(map);
            }
        }
    });
    
    document.getElementById('active-count').textContent = active;
    document.getElementById('inactive-count').textContent = inactive;
    
    function switchTab(tabId) {
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        event.target.classList.add('active');
        
        if (tabId === 'list') {
            document.getElementById('list-view').style.display = 'grid';
            document.getElementById('map-view').style.display = 'none';
        } else {
            document.getElementById('list-view').style.display = 'none';
            document.getElementById('map-view').style.display = 'block';
            setTimeout(() => map.invalidateSize(), 100);
        }
    }
</script>
</body>
</html>"""

    html_content = html_template.replace("REPLACE_ME_DATA", json.dumps(data)).replace("REPLACE_ME_TIMESTAMP", timestamp)
    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    
    if os.path.exists('/var/www/html/starlink'):
        try:
            import shutil
            shutil.copyfile('dashboard.html', '/var/www/html/starlink/index.html')
            print("🌐 Dashboard publicado en el servidor web (http://10.11.121.101/starlink/)")
        except Exception as e:
            print(f"⚠️ Error al publicar: {e}")

if __name__ == "__main__":
    fetch_starlink_data()
