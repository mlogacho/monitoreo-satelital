"""
alarm_notifier.py
-----------------
Gestiona el estado de alarmas por antena y envía correos a soporte@datacom.ec
cuando una estación ha estado INACTIVA más de 24 horas.

Archivo de estado: alarm_state.json
  {
    "service_line_id": {
        "nombre": "...",
        "first_offline_at": "2026-05-19T12:00:00",
        "alarm_sent_at":    "2026-05-20T12:05:00"   # null si no se envió
    },
    ...
  }
"""
import json
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

ALARM_STATE_FILE = "alarm_state.json"
OFFLINE_THRESHOLD_HOURS = 24

# ── Configuración SMTP (cPanel / Datacom) ──────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "mail.datacom.ec")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "_mainaccount@datacom.ec")
SMTP_PASS = os.getenv("SMTP_PASS", "")          # definir en .env
ALARM_FROM = os.getenv("ALARM_FROM", "_mainaccount@datacom.ec")
ALARM_TO   = os.getenv("ALARM_TO",   "soporte@datacom.ec")


def _load_state() -> dict:
    if os.path.exists(ALARM_STATE_FILE):
        try:
            with open(ALARM_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_state(state: dict):
    with open(ALARM_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _hours_since(iso_str: str) -> float:
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return delta.total_seconds() / 3600
    except Exception:
        return 0.0


def _send_email(nombre: str, first_offline_at: str, hours_offline: float):
    """Envía un correo de alarma vía SMTP SSL."""
    subject = f"[ALARMA] Antena offline >24h: {nombre}"
    offline_dt = first_offline_at[:19].replace("T", " ")
    body_html = f"""
    <html><body style="font-family:Arial,sans-serif;color:#333">
    <h2 style="color:#dc2626">&#9888; Alarma de Estación Inactiva</h2>
    <p>La siguiente antena Starlink lleva más de <strong>{int(hours_offline)}</strong>
    horas sin conexión:</p>
    <table style="border-collapse:collapse;width:100%;max-width:520px">
      <tr style="background:#f3f4f6">
        <td style="padding:8px 12px;border:1px solid #e5e7eb"><b>Estación</b></td>
        <td style="padding:8px 12px;border:1px solid #e5e7eb">{nombre}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border:1px solid #e5e7eb"><b>Fuera de línea desde</b></td>
        <td style="padding:8px 12px;border:1px solid #e5e7eb">{offline_dt}</td>
      </tr>
      <tr style="background:#f3f4f6">
        <td style="padding:8px 12px;border:1px solid #e5e7eb"><b>Horas offline</b></td>
        <td style="padding:8px 12px;border:1px solid #e5e7eb">{hours_offline:.1f} horas</td>
      </tr>
    </table>
    <p style="margin-top:20px;color:#6b7280;font-size:13px">
      Monitoreo Satelital Datacom &mdash; {datetime.now().strftime('%Y-%m-%d %H:%M')}
    </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = ALARM_FROM
    msg["To"]      = ALARM_TO
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=30) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(ALARM_FROM, [ALARM_TO], msg.as_string())
        print(f"  📧 Alarma enviada a {ALARM_TO} para: {nombre}")
        return True
    except Exception as e:
        print(f"  ⚠️  Error enviando alarma para {nombre}: {e}")
        return False


def check_and_send_alarms(stations: list):
    """
    Recibe la lista actual de estaciones (con campos 'service_line_id',
    'nombre', 'estado') y:
      - Actualiza el estado de alarma para cada una.
      - Envía correo si la estación lleva >24h inactiva y no se había enviado ya.
      - Limpia el estado de estaciones que volvieron a estar activas.
    """
    from dotenv import load_dotenv
    load_dotenv()

    # Recargar vars de entorno por si se actualizó .env
    global SMTP_PASS, SMTP_USER, SMTP_HOST, SMTP_PORT, ALARM_FROM, ALARM_TO
    SMTP_HOST  = os.getenv("SMTP_HOST", SMTP_HOST)
    SMTP_PORT  = int(os.getenv("SMTP_PORT", str(SMTP_PORT)))
    SMTP_USER  = os.getenv("SMTP_USER", SMTP_USER)
    SMTP_PASS  = os.getenv("SMTP_PASS", SMTP_PASS)
    ALARM_FROM = os.getenv("ALARM_FROM", ALARM_FROM)
    ALARM_TO   = os.getenv("ALARM_TO", ALARM_TO)

    state = _load_state()
    now   = _now_iso()

    for station in stations:
        sid    = station.get("service_line_id") or station.get("nombre", "")
        nombre = station.get("nombre", sid)
        estado = station.get("estado", "").lower()

        if "inactivo" in estado or "offline" in estado or "fuera" in estado:
            # Estación offline
            if sid not in state:
                # Primera vez que la vemos offline
                state[sid] = {
                    "nombre":          nombre,
                    "first_offline_at": now,
                    "alarm_sent_at":   None,
                }
                print(f"  🔴 Offline detectado: {nombre} — iniciando contador de 24h")
            else:
                entry = state[sid]
                hours = _hours_since(entry["first_offline_at"])
                already_sent = entry.get("alarm_sent_at") is not None

                if hours >= OFFLINE_THRESHOLD_HOURS and not already_sent:
                    print(f"  🚨 {nombre} lleva {hours:.1f}h offline — enviando alarma...")
                    sent = _send_email(nombre, entry["first_offline_at"], hours)
                    if sent:
                        state[sid]["alarm_sent_at"] = now
        else:
            # Estación activa: limpiar estado de alarma
            if sid in state:
                print(f"  ✅ {nombre} volvió a estar activa — limpiando alarma")
                del state[sid]

    _save_state(state)
    print(f"[Alarmas] Estado guardado: {len(state)} estación(es) en seguimiento offline.")
