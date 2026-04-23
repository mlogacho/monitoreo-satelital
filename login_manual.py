import os
from playwright.sync_api import sync_playwright

SESSION_FILE = "state.json"

def login_manual():
    print("Iniciando navegador para inicio de sesión manual...")
    with sync_playwright() as p:
        # Lanzamos el navegador en modo visible ocultando la bandera de robot
        browser = p.chromium.launch(
            headless=False, 
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context()
        page = context.new_page()
        
        print("Navegando a Starlink...")
        page.goto("https://www.starlink.com/account/home")
        
        print("\n" + "="*50)
        print("🛑 ACCIÓN REQUERIDA 🛑")
        print("1. En la ventana del navegador que se acaba de abrir, inicia sesión normalmente.")
        print("2. Resuelve cualquier CAPTCHA si te lo pide.")
        print("3. Si te pide código al correo, ingrésalo.")
        print("4. UNA VEZ QUE ESTÉS DENTRO DE TU PANEL (y veas tus antenas), vuelve a esta terminal.")
        print("="*50 + "\n")
        
        # El script se pausa aquí hasta que el usuario presione Enter
        input("Presiona ENTER aquí cuando hayas terminado de iniciar sesión en el navegador...")
        
        print("\nGuardando tu sesión humana...")
        context.storage_state(path=SESSION_FILE)
        print("✅ ¡Sesión guardada exitosamente en state.json!")
        print("Ahora el robot podrá usar esta sesión para consultar los datos automáticamente.")
        
        browser.close()

if __name__ == "__main__":
    login_manual()
