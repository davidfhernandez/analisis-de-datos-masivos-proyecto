# Proyecto final: análisis de datos masivos de Fórmula 1

Pipeline reproducible para integrar el histórico de Fórmula 1, generar tablas consolidadas, almacenarlas en MongoDB y publicarlas en BigQuery para su visualización en Looker Studio.

El snapshot incluido en este repositorio contiene carreras desde **1950 hasta 2024**. La fuente de descarga utilizada es el dataset de Kaggle enlazado en la sección de recursos.

## Flujo del proyecto

```text
Dataset de Kaggle (CSV)
        │
        ▼
      data/
        │
        ▼
src/join_f1_data.py
        ├── output/f1_carreras_consolidado.csv
        ├── output/f1_tiempos_vuelta_consolidado.csv
        └── MongoDB (colecciones originales y consolidadas)
                │
                ▼
        src/export_bigquery.py
                │
                ▼
     BigQuery: fluted-set-423901-d4.f1_bigdata
                │
                ▼
             Looker Studio
```

El entorno se ejecuta con Docker Compose. El script de integración usa Python y pandas; PySpark está disponible en la imagen para extender el procesamiento, pero no es requerido por el flujo actual.

## Recursos

- [Dataset de Fórmula 1 en Kaggle](https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020)
- [Dashboard en Looker Studio](https://datastudio.google.com/reporting/86ab5641-1d5b-492f-8d5e-a0d7ec9a391f)

## Estructura del repositorio

```text
Analisis-de-datos-masivos/
├── data/                         # CSV originales del dataset
│   ├── circuits.csv
│   ├── constructor_results.csv
│   ├── constructor_standings.csv
│   ├── constructors.csv
│   ├── driver_standings.csv
│   ├── drivers.csv
│   ├── lap_times.csv
│   ├── pit_stops.csv
│   ├── qualifying.csv
│   ├── races.csv
│   ├── results.csv
│   ├── seasons.csv
│   ├── sprint_results.csv
│   └── status.csv
├── docker/
│   └── Dockerfile                 # Python 3.10, Java y dependencias
├── output/                        # CSV consolidados generados
├── src/
│   ├── join_f1_data.py            # Integración, transformación y carga a MongoDB
│   └── export_bigquery.py         # Exportación de los consolidados a BigQuery
├── docker-compose.yml             # MongoDB y contenedor de procesamiento
├── requirements.txt               # Dependencias Python
├── .gitignore                     # Excluye la clave local de GCP
└── README.md
```

## Requisitos

- Docker Desktop con Docker Compose.
- Git, si se va a clonar el repositorio.
- Una cuenta de Google Cloud con BigQuery habilitado, únicamente para ejecutar la exportación a BigQuery.
- Una clave JSON de una cuenta de servicio con permisos para crear el dataset, ejecutar jobs y crear/reemplazar tablas en BigQuery.

No es necesario instalar Python, Java, pandas ni MongoDB en el equipo anfitrión: el flujo recomendado utiliza el contenedor `spark-app`.

## Preparación

1. Clonar el repositorio y entrar en su carpeta:

   ```bash
   git clone <URL_DEL_REPOSITORIO>
   cd Analisis-de-datos-masivos
   ```

2. Si los datos no están presentes, descargar y descomprimir el dataset de Kaggle dentro de `data/`. Los archivos deben quedar directamente en esa carpeta, no dentro de otra subcarpeta.

3. Comprobar que estén disponibles los archivos principales:

   ```bash
   test -f data/races.csv
   test -f data/results.csv
   test -f data/drivers.csv
   test -f data/constructors.csv
   test -f data/circuits.csv
   test -f data/status.csv
   ```

   `qualifying.csv`, `lap_times.csv` y `pit_stops.csv` se integran cuando existen. El resto de los CSV presentes en `data/` se carga como colección original en MongoDB.

## Ejecución del pipeline local

### 1. Construir la imagen

Desde la raíz del repositorio:

```bash
docker compose build spark-app
```

### 2. Generar los consolidados y cargar MongoDB

La forma más sencilla de ejecutar todo el proceso es:

```bash
docker compose up --build spark-app
```

Este comando inicia MongoDB, espera a que esté disponible y ejecuta `src/join_f1_data.py`. Cuando termina correctamente, el contenedor de procesamiento puede aparecer como `Exited (0)`; es un resultado esperado porque el script es de una sola ejecución.

Para ejecutar el proceso usando una imagen ya construida:

```bash
docker compose up -d mongodb
docker compose run --rm spark-app python3 src/join_f1_data.py
```

El proceso:

- Lee los CSV desde `data/` y convierte el marcador `\N` en valores nulos.
- Une `results.csv` con carreras, pilotos, escuderías, circuitos y estados.
- Integra `qualifying.csv` si está disponible.
- Integra `lap_times.csv` con `pit_stops.csv` y añade el contexto de la carrera, piloto, escudería y circuito.
- Genera los dos CSV de `output/`.
- Reemplaza las colecciones correspondientes en la base `f1_db` de MongoDB.

La carga es idempotente: cada ejecución elimina y vuelve a insertar el contenido de las colecciones administradas por el script. Esto permite repetir el pipeline sin acumular documentos duplicados.

### 3. Revisar la ejecución

Ver el estado de los servicios:

```bash
docker compose ps
```

Ver los logs del servicio de MongoDB:

```bash
docker compose logs mongodb
```

Ver las colecciones cargadas:

```bash
docker exec -it f1_mongodb mongosh \
  -u f1user -p f1password --authenticationDatabase admin f1_db \
  --eval 'show collections'
```

Se esperan las colecciones originales (`races`, `results`, `drivers`, etc.) y estas dos colecciones consolidadas:

- `f1_carreras_consolidado`: resultados de carrera enriquecidos con información de carrera, piloto, escudería, circuito, estado y clasificación cuando está disponible.
- `f1_tiempos_vuelta_consolidado`: tiempos por vuelta enriquecidos con información de carrera y paradas en boxes cuando existe coincidencia.

También deben existir estos archivos:

```text
output/f1_carreras_consolidado.csv
output/f1_tiempos_vuelta_consolidado.csv
```

### 4. Generar únicamente los CSV

Si solo se necesitan las transformaciones y no se quiere conectar a MongoDB:

```bash
docker compose run --rm --no-deps spark-app \
  python3 src/join_f1_data.py --skip-mongo
```

### 5. Mantener el contenedor activo (opcional)

El modo `--keep-alive` solo es útil para inspección manual del contenedor o para conectarse a los puertos publicados:

```bash
docker compose run --rm --service-ports spark-app \
  python3 src/join_f1_data.py --keep-alive
```

## Exportación a Google BigQuery

La exportación debe ejecutarse después de generar los archivos de `output/`.

### Credenciales

El script espera una clave de cuenta de servicio en la raíz del proyecto con este nombre exacto:

```text
credentials_f1_gcp.json
```

La ruta está excluida mediante `.gitignore`. No se debe publicar esta clave ni incluirla en un commit. Si una clave real ya fue subida a un repositorio remoto, debe revocarse y generarse una nueva antes de continuar.

### Ejecutar la exportación

```bash
docker compose run --rm spark-app \
  python3 src/export_bigquery.py
```

La configuración actual del script es:

| Recurso | Valor |
|---|---|
| Proyecto de Google Cloud | `fluted-set-423901-d4` |
| Dataset de BigQuery | `f1_bigdata` |
| Región | `us-east1` |
| Tabla de carreras | `f1_carreras_consolidado` |
| Tabla de vueltas | `f1_tiempos_vuelta_consolidado` |

El dataset se crea si no existe. Las dos tablas se cargan con `replace`, por lo que una nueva exportación reemplaza su contenido con el de los CSV actuales.

Después de una exportación correcta, las tablas pueden consultarse en:

```text
fluted-set-423901-d4.f1_bigdata.f1_carreras_consolidado
fluted-set-423901-d4.f1_bigdata.f1_tiempos_vuelta_consolidado
```

El dashboard de Looker Studio utiliza los datos publicados en BigQuery: [abrir dashboard](https://datastudio.google.com/reporting/86ab5641-1d5b-492f-8d5e-a0d7ec9a391f).

## Parámetros del script de integración

`join_f1_data.py` acepta estos argumentos:

```text
--data-dir    Directorio de entrada de los CSV
--output-dir  Directorio de salida de los consolidados
--mongo-uri   URI de conexión a MongoDB
--mongo-db    Nombre de la base de datos
--skip-mongo  Genera los CSV sin cargar MongoDB
--keep-alive  Mantiene el proceso activo al finalizar
```

Ejemplo con directorios alternativos dentro del contenedor:

```bash
docker compose run --rm --no-deps spark-app \
  python3 src/join_f1_data.py \
  --data-dir data \
  --output-dir output \
  --skip-mongo
```

Los valores por defecto también pueden configurarse mediante las variables `DATA_DIR`, `OUTPUT_DIR`, `MONGO_URI` y `MONGO_DB`.

## Detener y limpiar el entorno

Detener los contenedores conservando los datos de MongoDB:

```bash
docker compose down
```

Detener los contenedores y eliminar el volumen local de MongoDB:

```bash
docker compose down -v
```

El segundo comando elimina la base local almacenada en el volumen `mongo_data`. No elimina los CSV de `data/` ni los archivos de `output/`, pero los documentos de MongoDB deberán cargarse nuevamente.

## Solución de problemas

- **No existe un CSV requerido:** comprobar que los archivos estén directamente dentro de `data/` y que sus nombres coincidan con los del dataset.
- **MongoDB no está disponible:** ejecutar `docker compose ps` y revisar `docker compose logs mongodb`. El script reintenta la conexión durante aproximadamente un minuto.
- **El puerto 27017 está ocupado:** detener otra instancia local de MongoDB o modificar el mapeo de puertos en `docker-compose.yml`. La comunicación interna entre los contenedores seguirá usando el nombre `mongodb`.
- **No se encuentra la clave de GCP:** verificar que `credentials_f1_gcp.json` esté en la raíz del proyecto, al mismo nivel que `docker-compose.yml`.
- **Error de permisos en BigQuery:** revisar que la cuenta de servicio tenga acceso al proyecto y permisos para crear o escribir el dataset y las tablas.
- **El dashboard no muestra cambios:** confirmar que la exportación terminó correctamente y actualizar la fuente o la vista en Looker Studio.

## Tecnologías

- Python 3.10
- pandas
- MongoDB 6.0
- Docker y Docker Compose
- Google BigQuery
- Looker Studio
- PySpark disponible en la imagen del proyecto para futuras extensiones
