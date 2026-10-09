# Dónde desplegar el sistema gratis

El enunciado pide que el `Jenkinsfile` cubra "el levantamiento de los servicios… y el despliegue",
y en la sustentación hay que mostrar "a Jenkins construyendo y desplegando la nueva versión".
**No exige una nube pública**: desplegar puede ser que Jenkins ejecute
`docker compose up -d --build` en la máquina donde corre. Lo único que obliga a tener una dirección
pública es el **webhook de GitHub**: GitHub tiene que poder llamar a Jenkins.

## Qué opciones sirven

El sistema es pesado: MongoDB con 1,88 M de documentos, un clúster de Dask, un clúster de Spark,
la API y el frontend. Por eso la mayoría de planes gratuitos no alcanzan.

| Opción | ¿Sirve? | Por qué |
|---|---|---|
| **Oracle Cloud Always Free** (VM ARM Ampere) | ✅ **Recomendada** | Gratis de forma permanente. La documentación oficial indica 4 núcleos, 24 GB de RAM y 200 GB de disco; un reporte de 2026 dice que podría haberse reducido a 2 núcleos y 12 GB (confirmar en la consola). Incluso con 12 GB alcanza para todo el `docker compose` y Jenkins. |
| GitHub Student Developer Pack (créditos de DigitalOcean, Azure for Students) | ✅ Alternativa | Créditos gratis con correo universitario para una VM normal (x86). Se acaban, pero cubren el semestre. |
| MongoDB Atlas gratuito (M0) | ❌ | Límite estricto de 512 MB: los 1,88 M de documentos con sus índices probablemente no caben, y solo resolvería la base de datos. |
| Render, Railway, Fly.io, Vercel, Netlify | ❌ | No ejecutan un `docker compose` de 10 servicios: poca RAM, se apagan por inactividad o ya no son gratis. Vercel o Netlify servirían solo para el frontend; la API seguiría necesitando un servidor. |
| VM gratuita de AWS o Google Cloud | ❌ | 1 GB de RAM; solo Spark necesita varios. |

## Por qué Oracle encaja con la parte de CI/CD

1. **El webhook funciona directo.** La VM tiene IP pública, así que GitHub llama a
   `http://<IP>:<puerto de Jenkins>/github-webhook/` sin túneles. Con Jenkins en un portátil hace
   falta ngrok o smee.io, y la URL gratuita cambia cada vez que se reinicia.
2. **El despliegue es real y se puede mostrar.** Jenkins construye, prueba y ejecuta
   `docker compose up -d`; en la sustentación el profesor abre `http://<IP>:3000` desde su propio
   equipo. Eso responde directamente a "un sistema que solo funciona en el computador de un
   integrante no se considera terminado".
3. **La arquitectura ARM no es un problema**: las imágenes que usamos (mongo, uv/Python, node,
   nginx y el Java de Debian) tienen versión ARM64.

## Cuidados

- Oracle pide tarjeta de crédito para verificar la cuenta, aunque no cobra en el plan Always Free.
- En las regiones más usadas a veces sale **"Out of capacity"** al crear la VM ARM: reintentar o
  elegir otra región al registrarse.
- Con 12 GB de RAM, bajar la memoria de Spark en el `.env` (por ejemplo `SPARK_WORKER_MEMORY=2g`).
  Las etapas de Dask y Spark corren una después de la otra, así que no coinciden en memoria.
- Abrir en la **Security List** de la VM solo los puertos necesarios: 3000 (frontend), 5000 (API) y
  el de Jenkins.
- **Jenkins y la interfaz del Spark master usan el puerto 8080.** En la misma máquina hay que
  cambiar uno de los dos (por ejemplo, Jenkins en 8090).

## Plan

1. Crear la VM ARM en Oracle e instalar Docker y Jenkins.
2. Completar el `Jenkinsfile` con: checkout, construcción de las imágenes, `pytest` y tests del
   frontend, levantamiento de los servicios, pruebas básicas contra la API y despliegue. Si una
   prueba falla, no se despliega.
3. Guardar el token de Kaggle como credencial de Jenkins y configurar el webhook en GitHub.

## Fuentes

- [Oracle — Always Free Resources (documentación oficial)](https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm)
- [TerminalBytes — Oracle Cloud free tier changes 2026](https://terminalbytes.com/oracle-cloud-free-tier-changes-2026)
- [Guía Oracle Always Free 4 OCPU / 24 GB (Medium, 2026)](https://medium.com/@imvinojanv/setup-always-free-vps-with-4-ocpu-24gb-ram-and-200gb-storage-the-ultimate-oracle-cloud-guide-bed5cbf73d34)
- [MongoDB Atlas — límites del clúster gratuito](https://mongodb.com/docs/atlas/reference/free-shared-limitations/)
- [MongoDB Atlas — FAQ de almacenamiento](https://docs.atlas.mongodb.com/reference/faq/storage/)
- [Oneuptime — MongoDB Atlas Free Tier (2026)](https://oneuptime.com/blog/post/2026-03-31-mongodb-atlas-free-tier-setup/view)
