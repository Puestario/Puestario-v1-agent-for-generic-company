# First job / Primer trabajo

Fill this out with the client **before** the office visit. Save the completed copy in the client's private records, not this repo.

Llenen esta ficha con el cliente **antes** de la visita. Guarden la copia en sus registros privados, no en este repo.

## 1. Pick one useful job / Elijan un trabajo útil

Ask: What do you do by hand? How often? How long does it take? Watch one full run. Who needs the answer? What happens if it is wrong or late? What is the smallest useful version?

Pregunten: ¿Qué hacen a mano? ¿Cada cuánto? ¿Cuánto tarda? Miren una ejecución completa. ¿Quién necesita la respuesta? ¿Qué pasa si llega tarde o está mal? ¿Cuál es la versión útil más pequeña?

> Example / Ejemplo: Every morning at 8 AM Miami time, send Ana the approved sales range in her private WhatsApp chat. / Cada mañana a las 8 AM, hora de Miami, enviar a Ana el rango de ventas aprobado en su chat privado de WhatsApp.

| Decision / Decisión | Fill in / Completar |
|---|---|
| One job / Un trabajo | |
| Who receives it / Quién lo recibe | |
| Source and exact range / Fuente y rango exacto | |
| Read only or approved edit / Solo lectura o edición aprobada | |
| Time and time zone / Hora y zona horaria | |
| Private chat or approved group / Chat privado o grupo aprobado | |
| What counts as correct / Cómo saber que está bien | |
| Who handles a failure / Quién atiende un fallo | |
| What can change next month / Qué puede cambiar el próximo mes | |

## 2. Fit the current software / Usen lo que existe hoy

Current choices: Google Sheets, Google Calendar reads, Stripe charge reads, GHL contact reads, private notes, reminders and small single-source reports. The exact limits are in [the team guide](docs/TEAM-GUIDE.md). A scheduled report currently sends a label and source data; a polished multi-app daily brief needs more development.

Opciones actuales: Google Sheets, lectura de Google Calendar, cobros de Stripe, contactos de GHL, notas privadas, recordatorios e informes pequeños de una sola fuente. Un informe programado envía una etiqueta y los datos; un resumen elaborado de varias aplicaciones necesita más desarrollo.

**A new app name in a document does not create a working connection.** Put unsupported work in [the roadmap](docs/ROADMAP.md); quote and test it separately.

**Escribir el nombre de una aplicación no la conecta.** Lo que falta va en [el plan de mejoras](docs/ROADMAP.md); se cotiza y se prueba por separado.

## 3. Agree on access and cost / Acuerden permisos y costo

- Name the approved people, numbers, groups and data. Verify numbers separately. Group information must be suitable for every real group member.
- The two verified people chosen during setup start as administrators. The client owner is not automatically an administrator. Write down the agreed role.
- List device, line, model/API, app, device-management and support costs. Set vendor alerts or limits where available. This release has no combined spending cap.
- Record phone/SIM ownership, recovery access, billing responsibility and offboarding terms in the client agreement. Keep sign-ins out of chat.

En español: anoten las personas, números, grupos y datos aprobados. Verifiquen los números. Definan el papel del dueño del negocio. Anoten costos de equipo, línea, IA, aplicaciones, administración del equipo y soporte. Aclaren quién controla la línea y cómo se entrega o cancela el servicio. Las claves nunca van por chat.

## 4. Watch it work / Vean que funcione

1. Test one allowed request and one blocked request. / Prueben una petición permitida y una bloqueada.
2. Read the actual output. Check its source and the actual model used. A fallback is recorded separately. / Revisen la respuesta, la fuente y el modelo usado.
3. Watch the first reminder arrive in the right chat. A send receipt does not prove the person read it. / Vean llegar el primer aviso al chat correcto; envío no significa lectura.
4. Test backup and paused restore with approved test data. / Prueben la copia y la recuperación en pausa.
5. Complete [acceptance](docs/ACCEPTANCE.md), then close Setup. / Completen las pruebas y cierren Setup.

If a result is uncertain, say so. Check before retrying an action that might already have happened. For the first 30 days, review failures, late sends, model fallbacks and costs each week.

Si no sabemos si una acción terminó, hay que decirlo y revisar antes de repetirla. Durante los primeros 30 días, revisen fallos, retrasos, cambios de modelo y gastos cada semana.
