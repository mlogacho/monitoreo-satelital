import os
import time
import json
from datetime import datetime
from playwright.sync_api import sync_playwright
from alarm_notifier import check_and_send_alarms

SESSION_FILE = "state.json"
DATA_FILE = "starlink_data.json"


def check_device_status(page):
    """
    En la página de detalle de una antena, busca la sección 'Dispositivos'
    y detecta el color del indicador junto a 'STARLINK'.
    Verde = Activo (en línea), Rojo = Inactivo (fuera de línea).
    """
    try:
        # Esperar a que cargue la sección Dispositivos
        page.wait_for_selector("text=Dispositivos", timeout=15000)
        time.sleep(3)

        status = page.evaluate("""() => {
            // Buscar el texto exacto 'STARLINK' (no el logo del header)
            const walker = document.createTreeWalker(
                document.body, NodeFilter.SHOW_TEXT
            );
            let starlinkEl = null;
            while (walker.nextNode()) {
                const txt = walker.currentNode.textContent.trim();
                if (txt === 'STARLINK' || txt === 'Starlink') {
                    starlinkEl = walker.currentNode.parentElement;
                    break;
                }
            }
            if (!starlinkEl) return null;

            // Subir por el DOM buscando el contenedor de la fila del dispositivo
            let container = starlinkEl;
            for (let i = 0; i < 8; i++) {
                container = container.parentElement;
                if (!container) break;

                // Buscar elementos pequeños y redondos (indicadores de estado)
                for (const el of container.querySelectorAll('*')) {
                    const rect = el.getBoundingClientRect();
                    const w = rect.width;
                    const h = rect.height;

                    // Los dots de estado suelen ser entre 6-20px, cuadrados/redondos
                    if (w >= 6 && w <= 24 && h >= 6 && h <= 24 && Math.abs(w - h) < 4) {
                        const style = getComputedStyle(el);
                        const bg = style.backgroundColor;
                        const m = bg.match(/rgba?\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)/);
                        if (m) {
                            const r = parseInt(m[1]);
                            const g = parseInt(m[2]);
                            const b = parseInt(m[3]);
                            // Verde: g predomina sobre r
                            if (g > 100 && g > r * 1.3) return 'Activo';
                            // Rojo: r predomina sobre g
                            if (r > 100 && r > g * 1.3) return 'Inactivo';
                        }

                        // También verificar SVG fills
                        if (el.tagName === 'circle' || el.tagName === 'CIRCLE') {
                            const fill = el.getAttribute('fill') || style.fill;
                            if (fill) {
                                const fl = fill.toLowerCase();
                                if (fl.includes('green') || fl.includes('#22c55e') ||
                                    fl.includes('#10b981') || fl.includes('#4ade80') ||
                                    fl.includes('#16a34a')) return 'Activo';
                                if (fl.includes('red') || fl.includes('#ef4444') ||
                                    fl.includes('#dc2626') || fl.includes('#f87171')) return 'Inactivo';
                            }
                        }
                    }
                }
            }
            return null;
        }""")
        return status
    except Exception as e:
        print(f"    ⚠️ No se pudo verificar estado del dispositivo: {e}")
        return None


def fetch_starlink_data():
    print(f"[{datetime.now()}] Iniciando chequeo de Starlink (con verificación de dispositivo)...")

    if not os.path.exists(SESSION_FILE):
        print("❌ Error: No se encontró el archivo de sesión 'state.json'.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(storage_state=SESSION_FILE, viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        page.goto("https://www.starlink.com/account/subscriptions")
        time.sleep(10)

        subscriptions = []
        acc_set = []

        try:
            print("Detectando cuentas disponibles...")
            avatar = page.locator("button", has_text="ML").first
            if avatar.is_visible():
                avatar.click()
                time.sleep(3)
                combobox = page.locator('li[role="combobox"]')
                if combobox.is_visible():
                    combobox.click()
                    time.sleep(3)

                    # Scroll dentro del listbox hasta que no aparezcan nuevas cuentas
                    stable_rounds = 0
                    prev_count = -1
                    for _ in range(150):  # max 150 iteraciones de seguridad
                        items = page.locator('li:has-text("ACC-")').all()
                        for item in items:
                            try:
                                txt = item.inner_text().strip()
                            except Exception:
                                continue
                            acc_id = ""
                            for ln in txt.split('\n'):
                                if "ACC-" in ln:
                                    acc_id = ln.strip()
                                    break
                            if acc_id and acc_id not in acc_set:
                                acc_set.append(acc_id)
                        # Detectar estabilidad: si el conteo no cambió 5 rondas seguidas, terminamos
                        if len(acc_set) == prev_count:
                            stable_rounds += 1
                            if stable_rounds >= 5:
                                break
                        else:
                            stable_rounds = 0
                        prev_count = len(acc_set)
                        # Scrollear el listbox (no la página) para mostrar más ítems
                        page.evaluate("""
                            () => {
                                const lb = document.querySelector('[role="listbox"]')
                                    || document.querySelector('[role="option"]')?.parentElement;
                                if (lb) lb.scrollBy(0, 300);
                                else window.scrollBy(0, 300);
                            }
                        """)
                        time.sleep(0.4)

                    page.keyboard.press("Escape")
                    time.sleep(2)
        except Exception as e:
            print(f"Error detectando cuentas múltiples. {e}")

        if not acc_set:
            acc_set = ["DEFAULT"]  # fallback

        print(f"Se encontraron {len(acc_set)} cuentas únicas.")

        for idx, acc_id in enumerate(acc_set):
            try:
                print(f"--- Procesando Cuenta {idx+1}/{len(acc_set)} ({acc_id}) ---")
                page.goto("https://www.starlink.com/account/subscriptions")
                time.sleep(8)

                if acc_id != "DEFAULT":
                    avatar = page.locator("button", has_text="ML").first
                    if avatar.is_visible():
                        avatar.click()
                        time.sleep(2)
                        combobox = page.locator('li[role="combobox"]')
                        if combobox.is_visible():
                            combobox.click()
                            time.sleep(2)

                            found = False
                            for _ in range(30):
                                opt = page.locator(f'li:has-text("{acc_id}")').last
                                if opt.is_visible():
                                    try:
                                        opt.click(force=True)
                                    except:
                                        opt.evaluate("el => el.click()")
                                    time.sleep(10)
                                    found = True
                                    break
                                page.keyboard.press('PageDown')
                                time.sleep(0.5)

                            if not found:
                                page.keyboard.press("Escape")

                # ── Fase 1: Recolectar URLs y datos básicos de la lista ──
                account_lines = []
                page_num = 1
                while True:
                    print(f"  -> Extrayendo página {page_num}...")
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

                        for t in texts:
                            if "Ubicación:" in t or "Location:" in t:
                                ubicacion = t.replace("Ubicación:", "").replace("Location:", "").strip()

                        # Evitar nombres que sean ACC- u otros genéricos
                        if nombre.startswith("ACC-") or nombre.startswith("SL-DF"):
                            for t in texts:
                                if t and "Ubicación" not in t and "Activo" not in t and "Inactivo" not in t and "ACC-" not in t:
                                    nombre = t
                                    break

                        service_line_id = href.rstrip("/").split("/")[-1]
                        account_lines.append({
                            "href": href,
                            "service_line_id": service_line_id,
                            "nombre": nombre,
                            "ubicacion": ubicacion,
                        })

                    next_btn = page.locator('button[aria-label="Go to next page"]').first
                    if next_btn.is_visible() and not next_btn.is_disabled():
                        print("  -> Pasando a siguiente página de antenas...")
                        next_btn.click()
                        time.sleep(6)
                        page_num += 1
                    else:
                        break

                print(f"  Recolectadas {len(account_lines)} antenas de la cuenta. Verificando estado de dispositivos...")

                # ── Fase 2: Visitar cada detalle para obtener estado real ──
                for i, line in enumerate(account_lines):
                    detail_url = f"https://www.starlink.com{line['href']}"
                    estado_real = "Desconocido"
                    try:
                        print(f"    [{i+1}/{len(account_lines)}] Verificando {line['nombre']}...")
                        page.goto(detail_url)
                        time.sleep(6)

                        device_status = check_device_status(page)
                        if device_status:
                            estado_real = device_status
                            print(f"      -> Dispositivo: {device_status}")
                        else:
                            # Fallback: intentar leer texto de la página
                            page_text = page.inner_text("body")
                            if "Fuera de línea" in page_text or "Offline" in page_text:
                                estado_real = "Inactivo"
                                print(f"      -> Texto detectado: Inactivo")
                            elif "En línea" in page_text or "Online" in page_text:
                                estado_real = "Activo"
                                print(f"      -> Texto detectado: Activo")
                            else:
                                print(f"      -> ⚠️ No se pudo determinar estado, marcando como Desconocido")
                    except Exception as e:
                        print(f"      -> Error verificando dispositivo: {e}")

                    subscriptions.append({
                        "service_line_id": line['service_line_id'],
                        "nombre": line['nombre'],
                        "ubicacion": line['ubicacion'],
                        "estado": estado_real,
                        "uso_datos": "N/A"
                    })

            except Exception as e:
                print(f"Error procesando cuenta {acc_id}: {e}")

        # Eliminar duplicados usando service_line_id (ID real de la línea de servicio)
        # Esto evita que estaciones con el mismo nombre en distintas cuentas se fusionen
        unique_subs = {}
        for sub in subscriptions:
            key = sub.get('service_line_id') or (sub['nombre'] + sub['ubicacion'])
            unique_subs[key] = sub

        final_list = list(unique_subs.values())

        # Protección: no sobreescribir datos buenos con datos parciales
        MIN_EXPECTED_ANTENNAS = 40  # Mínimo esperado (~50% del total conocido)

        if final_list and len(final_list) >= MIN_EXPECTED_ANTENNAS:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump({"timestamp": datetime.now().isoformat(), "data": final_list}, f, indent=4, ensure_ascii=False)

            print(f"✅ ¡Extraídas {len(final_list)} antenas exitosamente!")
            generate_static_dashboard(final_list, datetime.now().isoformat())
            # Verificar alarmas de 24h offline
            try:
                check_and_send_alarms(final_list)
            except Exception as e:
                print(f"⚠️ Error en verificación de alarmas: {e}")
        elif final_list:
            print(f"⚠️ Solo se extrajeron {len(final_list)} antenas (mínimo esperado: {MIN_EXPECTED_ANTENNAS}). NO se sobreescriben los datos existentes.")
        else:
            print("⚠️ No se extrajeron antenas.")

        browser.close()


def generate_static_dashboard(data, timestamp):
    html_template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="1800">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>Monitoreo Satelital</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
    <style>
        :root {
            --bg-color: #0f172a; --card-bg: rgba(30, 41, 59, 0.7); --card-border: rgba(255, 255, 255, 0.1);
            --text-main: #f8fafc; --text-muted: #94a3b8; --active-color: #10b981; --active-bg: rgba(16, 185, 129, 0.15);
            --inactive-color: #ef4444; --inactive-bg: rgba(239, 68, 68, 0.15); --accent: #3b82f6;
            --unknown-color: #f59e0b; --unknown-bg: rgba(245, 158, 11, 0.15);
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
        .status-unknown { background-color: var(--unknown-bg); color: var(--unknown-color); border: 1px solid rgba(245, 158, 11, 0.2); }
        .info-row { font-size: 14px; color: var(--text-muted); margin-bottom: 8px;}
        .location-value { color: var(--text-main); font-family: monospace; background: rgba(0,0,0,0.2); padding: 2px 6px; border-radius: 4px; }
        .stats-summary { display: flex; gap: 20px; margin-bottom: 30px; }
        .stat-box { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 16px 24px; }
        .stat-value { font-size: 24px; font-weight: 700; }
        .stat-active .stat-value { color: var(--active-color); }
        .stat-inactive .stat-value { color: var(--inactive-color); }
        
        #list-view { display: none; }
        #map-view { display: block; height: 600px; width: 100%; border-radius: 16px; overflow: hidden; border: 1px solid var(--card-border); }
        .leaflet-popup-content-wrapper { background: var(--bg-color); color: var(--text-main); }
        .leaflet-popup-tip { background: var(--bg-color); }
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1>Monitoreo Satelital</h1>
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
        <button class="tab-btn" onclick="switchTab('list')">Lista de Antenas</button>
        <button class="tab-btn active" onclick="switchTab('map')">Mapa de Ecuador</button>
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
    
    data.forEach(a => {
        const estado = a.estado.toLowerCase();
        const isActive = estado === 'activo';
        const isInactive = estado === 'inactivo';
        if (isActive) active++; else inactive++;
        
        let badgeClass = 'status-unknown';
        let badgeText = a.estado;
        if (isActive) { badgeClass = 'status-active'; badgeText = 'En línea'; }
        else if (isInactive) { badgeClass = 'status-inactive'; badgeText = 'Fuera de línea'; }
        
        grid.innerHTML += `
            <div class="card">
                <div class="card-header">
                    <h2 class="antena-name">${a.nombre}</h2>
                    <span class="status-badge ${badgeClass}">${badgeText}</span>
                </div>
                <div>
                    <div class="info-row">Ubicación GPS: <span class="location-value">${a.ubicacion}</span></div>
                    <div class="info-row">Estado Dispositivo: ${badgeText}</div>
                </div>
            </div>
        `;
    });
    
    document.getElementById('active-count').textContent = active;
    document.getElementById('inactive-count').textContent = inactive;
    
    try {
        const map = L.map('map-view').setView([-1.8312, -78.1834], 6);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            className: 'map-tiles'
        }).addTo(map);
        
        data.forEach(a => {
            const isActive = a.estado.toLowerCase() === 'activo';
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
        
        window.myMap = map; // Save globally for the tab switcher
    } catch (e) {
        console.error("Error cargando el mapa:", e);
    }
    
    function switchTab(tabId) {
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        event.target.classList.add('active');
        
        if (tabId === 'list') {
            document.getElementById('list-view').style.display = 'grid';
            document.getElementById('map-view').style.display = 'none';
        } else {
            document.getElementById('list-view').style.display = 'none';
            document.getElementById('map-view').style.display = 'block';
            if (window.myMap) setTimeout(() => window.myMap.invalidateSize(), 100);
        }
    }
</script>
</body>
</html>"""

    html_content = html_template.replace("REPLACE_ME_DATA", json.dumps(data)).replace("REPLACE_ME_TIMESTAMP", timestamp)
    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    # Publicar en AMBOS directorios (Apache: /var/www/starlink, Nginx: /var/www/html/starlink)
    import shutil
    publish_dirs = ['/var/www/starlink', '/var/www/html/starlink']
    for pub_dir in publish_dirs:
        if os.path.exists(pub_dir):
            try:
                shutil.copyfile('dashboard.html', os.path.join(pub_dir, 'index.html'))
                print(f"🌐 Dashboard publicado en {pub_dir}/")
            except Exception as e:
                print(f"⚠️ Error al publicar en {pub_dir}: {e}")


if __name__ == "__main__":
    fetch_starlink_data()
