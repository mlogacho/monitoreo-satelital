# Monitoreo Satelital Starlink

## Descripción
Sistema de monitoreo automatizado diseñado para extraer y visualizar el estado de múltiples antenas Starlink asociadas a una o varias cuentas. El sistema ingresa a la plataforma oficial, recolecta la información de cada antena (nombre, ubicación GPS y estado de conectividad) y genera un dashboard HTML estático interactivo.

## Funcionalidades Principales
- **Extracción Multi-Cuenta (Modo Rápido Corregido):** Capacidad de iterar sobre un selector desplegable de múltiples cuentas (ej. 12 sub-cuentas bajo el mismo administrador) para consolidar todas las antenas.
- **Agrupación de DOM Avanzada:** La lectura se adapta a los cambios recientes en la interfaz web de Starlink, donde la información de una antena (Nombre, Ubicación y Estado) está dividida en múltiples etiquetas `<a>` hermanas que comparten el mismo enlace (`href`).
- **Dashboard Interactivo Estático:** Generación automática de un `index.html` que contiene dos pestañas principales:
  1. **Lista de Antenas:** Cuadrícula con las antenas, mostrando su estado con tarjetas de color.
  2. **Mapa de Ecuador (Leaflet.js):** Mapa interactivo mostrando marcadores en la ubicación GPS exacta de cada antena (Verde = Activo, Rojo = Inactivo).
- **Despliegue Automático:** Copia autónoma del reporte directamente a la ruta pública del servidor Web (Nginx).

## Requisitos
- Python 3.x
- Playwright (`pip install playwright` y `playwright install`)
- Archivo de sesión `state.json` válido (cookies persistentes para saltar el login).

## Configuración y Despliegue en Servidor Producción (Nginx)

El script `monitor_starlink.py` está configurado para publicar su salida en un servidor local Nginx. 

### Rutas de despliegue:
La ruta destino en el script de Python está fijada como absoluta:
```python
/var/www/html/starlink/index.html
```
*Nota importante:* Asegúrese de que el servidor web (Nginx) esté configurado para servir esta ruta directamente, en lugar de carpetas fuera de `/var/www/html/`.

### Tarea Automática (Cron Job)
Para asegurar el funcionamiento sin interrupciones cada 30 minutos, el *Cron Job* en Linux debe usar **rutas absolutas** para el entorno virtual, evitando fallos por la falta de variables de entorno (como `~`):
```bash
*/30 * * * * cd /home/datacomerp/monitoreo-satelital && /home/datacomerp/monitoreo-satelital/venv/bin/python3 monitor_starlink.py >> /home/datacomerp/monitoreo-satelital/cron.log 2>&1
```

## Registro de Cambios y Optimizaciones
- **Corrección de DOM (Abril 2026):** Se actualizó el bucle de Playwright para agrupar las etiquetas `<a>` basadas en su atributo `href` en lugar de separar por líneas (`\n`), debido a una actualización de Starlink.
- **Corrección de Nginx:** Se ajustó el directorio de despliegue de `/var/www/starlink/` a `/var/www/html/starlink/` para que coincida con el *Document Root* real del servidor.
- **Corrección de Cron:** Se sustituyeron las rutas relativas en Linux por rutas absolutas en crontab para evitar fallos silenciosos.
- **Escalabilidad a +80 antenas:** Se garantizó que el sistema espere a que la lista virtualizada renderice todas las cuentas al hacer scroll iterativo.
