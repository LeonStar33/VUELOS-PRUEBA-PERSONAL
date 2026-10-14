# Trazabilidad de requisitos

| Requisito de la consigna | Implementación | Evidencia |
|---|---|---|
| Cinco vuelos, origen CDMX, 08/11/26, horarios y tarifas | flights.json y catálogo público | test_public_catalog_and_capacity y test_pricing |
| Terminal 2, Puerta 2 | interfaz y comprobante | captura 01 y TXT de ejemplo |
| 30 asientos, 20 turista/10 primera | semillas y mapa de asientos | test_public_catalog_and_capacity |
| Sencillo/ida y vuelta, categorías y número de boletos | selector de viaje, cantidad y categoría por asiento | test_multi_seat_checkout_payment_receipt, captura 02 |
| Descuento del 20% donde se indica | función price con configuración por vuelo | cinco variantes de test_pricing |
| Navegación pública y cuenta para compra | sesión y rutas protegidas | test_auth_validation_csrf_and_hash |
| Reserva durante 10 minutos y compra durante 15 | máquina de estados y reloj del servidor | test_expiry_boundary_releases_seats |
| Bloquear durante selección y no vender dos veces | BEGIN IMMEDIATE e índice único | test_race_only_one_winner, test_sold_seat_never_reallocated_and_persists |
| Efectivo/tarjeta y total visible | compra simulada sin datos bancarios | test_multi_seat_checkout_payment_receipt y test_smtp_failure_does_not_undo_payment |
| Formato digital y correo | TXT descargable y SMTP STARTTLS opcional | captura 03, comprobante-ejemplo.txt, test_smtp_composition_with_fake_transport |
| Modelo relacional y UML | ARQUITECTURA.md e INFORME.html | relaciones, restricciones y máquina de estados |
| Portada, problema, desarrollo, conclusiones, código e imágenes | INFORME.html autocontenido | abrir en navegador; contiene imágenes integradas |
| Análisis distribuido, arquitectura, redes e IPC/RPC | ARQUITECTURA.md e INFORME.html | propuesta explícitamente diferenciada de la implementación actual |

El correo real, la ciudad/aeropuerto de los destinos extranjeros, el itinerario de retorno y la interpretación final del descuento requieren confirmación/configuración. No se inventan como requisitos ya resueltos.
