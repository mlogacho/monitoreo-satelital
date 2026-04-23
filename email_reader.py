import imaplib
import email
import re
import time
from email.header import decode_header

def get_starlink_code(gmail_user, gmail_pass, wait_time=60, check_interval=5):
    """
    Conecta a Gmail vía IMAP y espera un correo reciente de Starlink para extraer el código.
    Espera un máximo de `wait_time` segundos, chequeando cada `check_interval`.
    """
    # Limpiamos la contraseña de aplicación (quitar espacios)
    gmail_pass = gmail_pass.replace(" ", "")

    start_time = time.time()
    
    while True:
        try:
            # Conectar al servidor IMAP de Gmail
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(gmail_user, gmail_pass)
            
            # Seleccionar la bandeja de entrada
            mail.select("inbox")
            
            # Buscar correos no leídos (UNSEEN)
            status, messages = mail.search(None, "UNSEEN")
            
            if status == "OK" and messages[0]:
                email_ids = messages[0].split()
                # Recorrer del más reciente al más antiguo
                for e_id in reversed(email_ids):
                    status, msg_data = mail.fetch(e_id, "(RFC822)")
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            
                            # Decodificar el asunto
                            subject, encoding = decode_header(msg["Subject"])[0]
                            if isinstance(subject, bytes):
                                subject = subject.decode(encoding if encoding else "utf-8")
                                
                            sender = msg.get("From")
                            
                            # Verificar si es de Starlink
                            if "starlink" in str(sender).lower() or "starlink" in str(subject).lower():
                                body = ""
                                if msg.is_multipart():
                                    for part in msg.walk():
                                        content_type = part.get_content_type()
                                        if content_type == "text/plain" or content_type == "text/html":
                                            body = part.get_payload(decode=True).decode()
                                            break
                                else:
                                    body = msg.get_payload(decode=True).decode()
                                
                                # Extraer un código de 6 dígitos con Regex
                                # Usualmente Starlink envía un código de 6 números: "Your code is 123456"
                                match = re.search(r'\b\d{6}\b', body)
                                if match:
                                    code = match.group(0)
                                    print(f"✅ Código Starlink encontrado: {code}")
                                    
                                    # Marcar como leído o eliminar opcionalmente
                                    mail.store(e_id, '+FLAGS', '\\Seen')
                                    mail.logout()
                                    return code
            mail.logout()
        except Exception as e:
            print(f"Error revisando correo: {e}")

        # Comprobar si excedimos el tiempo de espera
        if time.time() - start_time > wait_time:
            print("⏳ Tiempo de espera agotado buscando el código en el correo.")
            return None
        
        print(f"Esperando correo... Reintentando en {check_interval} segundos.")
        time.sleep(check_interval)

if __name__ == "__main__":
    # Prueba rápida (requiere llenar .env)
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    g_user = os.getenv("GMAIL_EMAIL")
    g_pass = os.getenv("GMAIL_APP_PASS")
    
    print("Iniciando modo de prueba de lectura de correo...")
    code = get_starlink_code(g_user, g_pass, wait_time=15)
    print("Resultado:", code)
