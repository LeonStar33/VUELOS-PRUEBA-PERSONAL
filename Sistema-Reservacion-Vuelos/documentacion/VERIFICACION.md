# Verificación realizada

- 18 casos de pytest aprobados en ejecución local con Python 3.14 y Flask 3.1.2.
- Catálogo de 5 vuelos, 30 asientos por vuelo, 10 primera y 20 turista.
- Registro, login, contraseñas con hash, validación y rechazo sin CSRF.
- Descuento por destino, primera clase, múltiples boletos y categorías.
- Límites exactos de 600 y 900 segundos con reloj controlado; selección y repetición de checkout no renuevan el plazo.
- Dos conexiones concurrentes intentan el mismo asiento: una gana y otra recibe conflicto; queda un único boleto activo.
- Acceso ajeno rechazado, cancelación libera asientos, entradas inválidas y compra fuera de estado rechazadas.
- Compra repetida no genera una segunda confirmación; fallo SMTP no revierte compra.
- Navegador Chrome controlado por Playwright: catálogo, registro, login, ida y vuelta, adulto y niño, selección de asientos 11 y 12, pago simulado con tarjeta y descarga TXT completados. Sin errores JavaScript detectados.
- Persistencia al volver a abrir la aplicación, rechazo de reventa de asientos pagados y composición del correo con transporte SMTP simulado.
- Vista móvil de 390 × 844: sin desbordamiento horizontal. Capturas guardadas en `capturas/`.

No se ha verificado envío a un proveedor SMTP real ni ejecución en Windows/MariaDB. La compatibilidad de los comandos de Windows está documentada, pero la ejecución comprobada fue en macOS. No se realizó prueba de carga masiva, auditoría de seguridad ni despliegue distribuido. Los tiempos se probaron con reloj controlado, no esperando 25 minutos en navegador.

Las capturas usan una cuenta ficticia. El ZIP excluye la base y la clave de sesión generadas durante la verificación. `comprobante-ejemplo.txt` es evidencia de simulación, no un boleto válido.

Verificación adicional de interfaz: dos asientos de Guadalajara sencillo, uno adulto y otro niño, total $1,450; cambiar solo el adulto a tercera edad mantiene el niño y recalcula el total a $1,000. Ejecutado en navegador con una base de prueba separada.
