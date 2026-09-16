# Empieza aquí

[English](../../START-HERE.md)

## 1. ¿Qué estamos creando?

Un ayudante para el equipo de una empresa. Le escribes por WhatsApp. El programa revisa quién pregunta, usa una herramienta permitida y devuelve el resultado.

La Mac guarda la configuración. La IA en internet ayuda a entender la petición. Los datos necesarios pueden viajar al proveedor elegido. Tener una Mac en la oficina no convierte todo en un sistema sin internet.

[Mira el dibujo](ARQUITECTURA.md) · [Explora la guía visual](https://puestario.com/es/agent-guide)

## 2. ¿Qué necesitas?

- Una Mac dedicada y una cuenta de operador que el personal no comparta.
- Una cuenta de WhatsApp dedicada y los números verificados de dos administradores.
- Cuentas autorizadas para el modelo y las aplicaciones del trabajo.
- Las versiones del software que indica [la guía del instalador](../MANAGED-INSTALL.md).
- Un lugar seguro para la llave de recuperación, separado de la Mac y de las copias.

Los administradores pueden ser de tu empresa. Nadie de Puestario viene agregado. En el código este papel se llama `founders`.

El código MIT es gratis. La Mac, el teléfono, el consumo de IA, las aplicaciones, el almacenamiento y el soporte tienen costos aparte. Todavía no se ha medido el tiempo de una instalación completa en una Mac nueva.

## 3. Llena un solo formulario

Copia [company.example.json](../../managed/company.example.json) a una carpeta privada fuera del repo. Llama a esa copia `company.json`.

Cambia empresa, agente, zona horaria, modelo y los nombres/números de los dos administradores. Confirma los números con sus dueños. Los ejemplos son inventados y una instalación normal los rechaza. `--staging` solo sirve para pruebas ficticias y nunca puede quedar Ready.

No pongas contraseñas en ese formulario. Las conexiones se autorizan después por la terminal local o la página del proveedor. Nunca pegues claves en el chat.

## 4. Sigue una sola instalación

Usa [la guía completa del instalador](../MANAGED-INSTALL.md), en este orden:

1. Descarga una versión revisada y prepara el software.
2. Ejecuta el instalador con el formulario privado. Crea los programas y los siete archivos de instrucciones.
3. Conecta el modelo y el teléfono dentro del perfil privado de esa empresa.
4. Abre Setup desde el chat privado de un administrador. Conecta una aplicación autorizada.
5. Agrega personas, prueba el primer trabajo y prueba también lo que debe bloquearse.
6. Crea una copia cifrada y comprueba que puedes restaurarla. Lo restaurado queda pausado.
7. Guarda las pruebas de aceptación, cierra Setup y comprueba Ready.

Si falla una prueba, corrígela antes de entregar. Un comando exitoso no demuestra que funcionen el teléfono, los permisos o el contenedor.

## 5. ¿Qué queda privado?

La carpeta de la empresa contiene accesos, notas, chats, permisos y registros. No va a GitHub. Las copias son archivos `.age` cifrados. La llave privada se guarda aparte. Nunca subas una carpeta real o un registro privado a un issue.

[Reporta un problema de seguridad por privado](../../SECURITY.md) · [Estado y límites](../RELEASE-STATUS.md) · [Guía para el equipo](../CLIENT-GUIDE.md)
