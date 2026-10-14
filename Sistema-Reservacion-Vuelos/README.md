# Sistema de Reservación de Vuelos

Respaldo académico para Josué, Texis, León y Vera. Flask + SQLite + HTML/CSS/JavaScript. Los cinco vuelos y tarifas proceden de T1_T2ProyectoVuelo.docx. Entrega indicada en Teams: **15 de octubre de 2026, 23:59 (hora de México)**.

## Ejecutar en Windows
Instala Python 3.10 o posterior. Descomprime el ZIP, abre una terminal dentro de la carpeta `Sistema-Reservacion-Vuelos` y ejecuta:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python run.py
```

## Ejecutar en Mac o Linux
```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py
```

Abre **http://127.0.0.1:5000**. Mantén esa terminal abierta. Para detener: Ctrl+C. La primera instalación necesita Internet; después la demo funciona localmente sin correo. No hace falta activar el entorno virtual, instalar MariaDB ni configurar contraseñas de base de datos.

Crea tu cuenta desde «Entrar / Registrarme». No hay cuentas ni contraseñas precargadas. El archivo SQLite y la clave de sesión se crean automáticamente dentro de `instance/`. No subas esa carpeta a GitHub. Para empezar una demo vacía, detén el servidor y mueve `instance/` a una carpeta de respaldo; el siguiente inicio crea otra base.

Si el puerto 5000 está ocupado, ejecuta con el Python de tu entorno: `-m flask --app run:app run --port 5050` y abre http://127.0.0.1:5050.

## Recorrido para la exposición
1. Consulta vuelos sin iniciar sesión. Compara categorías y primera clase.
2. Registra una cuenta e inicia sesión. Elige Guadalajara, ida y vuelta.
3. Indica 2 boletos en total y selecciona los asientos 11 y 12. En «Categoría de cada boleto», deja el 11 como adulto y cambia el 12 a niño. Puedes modificar cada categoría sin liberar el asiento. Total: $2,320 MXN según la interpretación de demo.
4. En una ventana privada inicia sesión con otra cuenta e intenta seleccionar el mismo asiento: aparecerá ocupado; el servidor rechaza una carrera aunque la pantalla estuviera desactualizada.
5. Continúa a compra. El temporizador cambia de 10 minutos de selección a 15 minutos de compra.
6. Elige efectivo o tarjeta y confirma. No introduzcas números de tarjeta; ambos métodos son simulaciones sin cobros.
7. Descarga el comprobante TXT. Los asientos quedan vendidos y no vuelven a liberarse.
8. Consulta «Mis reservas» después de cerrar y abrir sesión; los datos persisten.

## Pruebas
```sh
# Mac/Linux
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```
En Windows usa `.venv\Scripts\python` en lugar de `.venv/bin/python`. Las pruebas emplean bases temporales y reloj controlado, sin esperar 10 o 15 minutos ni modificar tus reservas. Resultado de la verificación: consulta `documentacion/VERIFICACION.md`.

## Correo opcional
Sin SMTP se descarga el comprobante; la interfaz informa que el envío no está configurado. Configura variables de entorno antes de arrancar: `SMTP_HOST`, `SMTP_PORT` (587 por defecto), `SMTP_FROM`, y si el servidor exige autenticación `SMTP_USER` y `SMTP_PASSWORD`. El cliente exige STARTTLS y valida el certificado. Usa una cuenta de pruebas; no pegues credenciales en el código. `SECRET_KEY` permite proporcionar una clave de sesión externa. El programa no lee archivos `.env` automáticamente.

Ejemplo PowerShell: `$env:SMTP_HOST="smtp.example.com"`. Ejemplo Mac/Linux: `export SMTP_HOST="smtp.example.com"`. Sustituye el dominio por tu proveedor y configura el resto en tu terminal. Un fallo de correo no revierte una compra confirmada. Esta demo no tiene cola persistente ni reenvío; entrega el TXT manualmente si el SMTP falla. El envío real requiere configuración y no está acreditado por las pruebas sin servidor.

## Decisiones que debe validar el docente
- Se conservan **Quatar** y **Korea** tal como aparecen. Qatar es la grafía habitual; Korea no identifica país/aeropuerto exacto. Italia y Francia tampoco especifican ciudad o aeropuerto de destino.
- Se interpreta 08/11/26 como **8 de noviembre de 2026**, zona de Ciudad de México (-06:00). Se usan horarios de la tabla; la frase aislada «a las 20:00 horas» se considera inconsistente y queda pendiente de aclarar.
- Ida y vuelta se calcula como **2 × sencillo × (1 − descuento)**. El 20% corresponde únicamente a Quatar y Guadalajara y, para esta demo, también se aplica a primera clase. Para los otros tres destinos se usa 2 × sencillo. La frase «20% sobre el precio sencillo» podría interpretarse como 0.8 × sencillo para todo el viaje; no se atribuye al docente una interpretación que no confirmó.
- No se inventa fecha, vuelo o asiento de regreso: el comprobante dice retorno pendiente. Esta opción representa una cotización/compra simulada de ida y vuelta, no una reserva operacional de dos segmentos.
- Asientos 1–10 primera; 11–30 turista. La primera clase usa tarifa única para todas las edades. Las categorías se eligen sin verificar edad porque no se definieron rangos.
- Un plazo fijo de 10 minutos empieza al abrir la reserva. Al continuar a compra antes del vencimiento, inicia otro plazo fijo de 15 minutos. Total máximo 25 minutos. No se renuevan al recargar o repetir la transición.
- Se requieren cuenta también para bloquear asientos, aunque el documento solo exige registro explícitamente al comprar. Esto permite identificar al propietario.

## Organización
- `backend/app.py`: rutas, validación y autenticación (Josué; integración compartida).
- `backend/db.py`, `database/`: esquema, semillas y consultas de vuelos (Texis).
- `backend/reservas.py`: estados, exclusión mutua y vencimientos (León); función `price` y `pay` compartidas con Vera.
- `backend/comprobantes.py`: recibo y SMTP (Vera).
- `frontend/`: interfaz accesible y adaptable (Josué, con integración de todos).
- `tests/`: pruebas automáticas, responsabilidad compartida.
- `documentacion/INFORME.html`: documento imprimible con portada, problema, solución, modelo, diagramas, análisis distribuido, capturas y anexo de código.
- `documentacion/ARQUITECTURA.md`: detalles técnicos y contratos.

## Trabajo en equipo
Cada integrante clona el mismo repositorio privado, crea su rama, hace cambios pequeños y abre una solicitud de revisión. Integrar cambios solo después de ejecutar pruebas. No compartir el archivo SQLite por Drive/OneDrive; cada desarrollador mantiene su base local. Para probar concurrencia entre navegadores, ambos deben usar el mismo servidor y la misma base.

La entrega es local. El servidor Flask incorporado sirve para la exposición; no está preparado para publicación en Internet. No incluye pasarela bancaria, reembolsos, recuperación de contraseñas, verificación de correo, administración de vuelos ni protección contra abuso a escala de producción.
