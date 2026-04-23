import os
import time
import json
from datetime import datetime
from playwright.sync_api import sync_playwright

SESSION_FILE = "state.json"
DATA_FILE = "starlink_data.json"

def fetch_starlink_data():
    print(f"[{datetime.now()}] Iniciando chequeo automático de Starlink...")
    
    if not os.path.exists(SESSION_FILE):
        print("❌ Error: No se encontró el archivo de sesión 'state.json'.")
        print("Por favor, ejecuta primero 'python3 login_manual.py' para iniciar sesión manualmente.")
        return
    
    with sync_playwright() as p:
        # Se ejecuta en modo headless (invisible) usando el Chrome real
        browser = p.chromium.launch(headless=True, channel="chrome")
        
        print("Cargando sesión guardada...")
        context = browser.new_context(storage_state=SESSION_FILE)
        page = context.new_page()

        print("Navegando a la sección de Suscripciones...")
        # Ir directo a suscripciones
        page.goto("https://www.starlink.com/account/subscriptions")
        
        # Esperar unos segundos para que carguen los datos dinámicos (SPA)
        time.sleep(10) 
        
        # Verificar si la sesión caducó (nos redirige a auth)
        if "auth" in page.url or page.locator("input[type='email']").is_visible():
            print("⚠️ Tu sesión guardada ha expirado o no es válida.")
            print("Por favor, vuelve a ejecutar 'python3 login_manual.py' para renovarla.")
            browser.close()
            return
        
        print("Extrayendo información de las antenas...")
        
        subscriptions = []
        
        # Intentamos localizar las filas de la tabla
        # Como no sabemos el HTML exacto, buscamos elementos que contengan texto característico
        # En tu captura, cada antena tiene un nombre y debajo la ubicación
        
        # Obtener todo el texto de la página y buscar patrones
        # O intentar extraer roles genéricos
        
        # Estrategia general: vamos a extraer todos los elementos que parecen ser contenedores de antenas.
        # Basado en la estructura de Starlink, los items suelen estar en listas
        
        # Obtendremos todos los textos que contengan "Ubicación:"
        elements = page.locator("xpath=//div[contains(., 'Ubicación') or contains(., 'Location')]").all()
        
        if not elements:
             # A veces están en spans o p
             elements = page.locator("xpath=//*[contains(text(), 'Ubicación') or contains(text(), 'Location')]").all()
        
        print(f"Buscando contenedores... se analizará el contenido visible.")
        
        # Como es complejo sin ver el HTML, extraigamos el texto entero de la región principal (main) o body
        main_content = page.locator("body").inner_text()
        
        # Vamos a dividirlo por líneas y buscar patrones
        lines = main_content.split('\n')
        
        # Un escaneo simple: si vemos una línea con "Ubicación:", la línea anterior suele ser el nombre de la antena
        # y la siguiente el estado.
        for i, line in enumerate(lines):
            line = line.strip()
            if "Ubicación:" in line or "Location:" in line:
                # La antena es probablemente la línea anterior o dos líneas atrás que no esté vacía
                nombre = ""
                for j in range(i-1, max(-1, i-4), -1):
                    if lines[j].strip():
                        nombre = lines[j].strip()
                        break
                
                estado = ""
                # El estado es probablemente la siguiente línea que no esté vacía y que diga Activo o Offline
                for j in range(i+1, min(len(lines), i+4)):
                    if lines[j].strip():
                        estado = lines[j].strip()
                        break
                
                if nombre:
                    subscriptions.append({
                        "nombre": nombre,
                        "ubicacion": line.replace("Ubicación:", "").replace("Location:", "").strip(),
                        "estado": estado
                    })
        
        # Eliminar duplicados (a veces el inner_text trae elementos repetidos)
        # Usamos un set para filtrar por nombre
        unique_subs = {sub['nombre']: sub for sub in subscriptions}.values()
        final_list = list(unique_subs)
        
        if final_list:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump({"timestamp": datetime.now().isoformat(), "data": final_list}, f, indent=4, ensure_ascii=False)
            print(f"✅ ¡Extraídas {len(final_list)} suscripciones exitosamente!")
            
            # Imprimir para verificación
            for s in final_list:
                print(f" - {s['nombre']} | {s['ubicacion']} | {s['estado']}")
                
            # Generar HTML estático
            generate_static_dashboard(final_list, datetime.now().isoformat())
                
        else:
            print("⚠️ No se pudieron extraer las suscripciones correctamente.")
            page.screenshot(path="debug_subscriptions.png")
            print("Pantallazo guardado como 'debug_subscriptions.png' para analizar.")

        browser.close()

def generate_static_dashboard(data, timestamp):
    import json
    
    html_template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monitoreo Starlink</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0f172a; --card-bg: rgba(30, 41, 59, 0.7); --card-border: rgba(255, 255, 255, 0.1);
            --text-main: #f8fafc; --text-muted: #94a3b8; --active-color: #10b981; --active-bg: rgba(16, 185, 129, 0.15);
            --inactive-color: #ef4444; --inactive-bg: rgba(239, 68, 68, 0.15); --accent: #3b82f6;
        }
        body { margin: 0; font-family: 'Inter', sans-serif; background-color: var(--bg-color); color: var(--text-main); min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }
        header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 40px; padding-bottom: 20px; border-bottom: 1px solid var(--card-border); }
        h1 { margin: 0; font-size: 28px; }
        .meta-info { text-align: right; font-size: 14px; color: var(--text-muted); }
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
    <div class="grid" id="grid"></div>
</div>
<script>
    const data = REPLACE_ME_DATA;
    const timestamp = "REPLACE_ME_TIMESTAMP";
    
    document.getElementById('timestamp').textContent = new Date(timestamp).toLocaleString();
    document.getElementById('total').textContent = data.length;
    
    let active = 0; let inactive = 0;
    const grid = document.getElementById('grid');
    
    data.forEach(a => {
        const isActive = a.estado.toLowerCase().includes('activo');
        if (isActive) active++; else inactive++;
        
        grid.innerHTML += `
            <div class="card">
                <div class="card-header">
                    <h2 class="antena-name">${a.nombre}</h2>
                    <span class="status-badge ${isActive ? 'status-active' : 'status-inactive'}">${isActive ? 'Activo' : a.estado}</span>
                </div>
                <div>
                    <div class="info-row">Ubicación GPS: <span class="location-value">${a.ubicacion}</span></div>
                    <div class="info-row">Estado: ${a.estado}</div>
                </div>
            </div>
        `;
    });
    
    document.getElementById('active-count').textContent = active;
    document.getElementById('inactive-count').textContent = inactive;
</script>
</body>
</html>"""

    html_content = html_template.replace("REPLACE_ME_DATA", json.dumps(data)).replace("REPLACE_ME_TIMESTAMP", timestamp)
    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("✅ Archivo dashboard.html generado exitosamente.")

if __name__ == "__main__":
    fetch_starlink_data()
