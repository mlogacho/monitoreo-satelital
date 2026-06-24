# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
### Fixed (Infraestructura & Servidor)
- **Alarmas SMTP (DNS):** Resuelto fallo de resolución (`Name or service not known`) que impedía el envío de notificaciones de antenas caídas. Se identificó que el DNS local (Samba AD) no resolvía `mail.datacom.ec`. Solucionado mapeando la IP externa directamente en `/etc/hosts`.
- **Conflicto Nginx (Pantalla Blanca):** Corregido un error crítico donde el acceso al dashboard por IP mostraba una pantalla blanca. Nginx priorizaba el bloque de configuración del CRM en lugar del sistema Starlink. Se inyectó una regla `location /starlink/` explícita en Nginx para solucionarlo.
- **Redirección a IP Inactiva:** Se eliminó una URL "hardcoded" obsoleta (`10.11.121.58:8081`) que permanecía en el frontend compilado del CRM y que causaba redirecciones forzosas al intentar acceder a Starlink por culpa de la caché del navegador.
