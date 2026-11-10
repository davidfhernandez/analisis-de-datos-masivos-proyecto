# Proyecto Final: Análisis de Datos Masivos - Fórmula 1 (1950 - 2024)

## 📌 Descripción General
Este proyecto implementa una solución integral de Big Data para procesar, transformar y analizar el conjunto histórico oficial de carreras de la Fórmula 1. 

A través de una arquitectura basada en **contenedores Docker**, los datos relacionales de carreras, tiempos de vuelta, paradas en boxes, pilotos y escuderías son almacenados en **MongoDB**, procesados mediante **Python / Apache Spark**, y visualizados en un **Dashboard Interactivo**.

---

## 🏗️ Estructura del Repositorio Recomendada

```text
Analisis-de-datos-masivos/
├── data/                  # Archivos CSV descargados desde Kaggle
├── docker/
│   └── Dockerfile         # Configuración del entorno Python + Java / PySpark
├── src/
│   └── join_f1_data.py    # Script principal de carga, uniones (joins) e ingesta
├── output/            # Datasets procesados finales (CSV) - backup
├── docker-compose.yml     # Orquestación de MongoDB y Spark App
├── requirements.txt       # Librerías de Python requeridas
└── README.md              # Documentación y guía de ejecución
```

---

## 🛠️ Herramientas Tecnológicas e Infraestructura

1. **Almacenamiento NoSQL (MongoDB v6.0)**: Almacenamiento flexible de colecciones nativas de F1.
2. **Procesamiento Masivo (Apache Spark / Python 3.10)**: Uniones relacionales distribuibles de más de 500.000 registros de vueltas y paradas en boxes.
3. **Orquestación (Docker & Docker Compose)**: Containerización reproducible de los servicios sin necesidad de instalaciones locales.
4. **Visualización Looker**: Dashboard interactivo para exploración de indicadores.

---

## 🚀 Guía de Despliegue y Reproducibilidad

### 1. Requisitos Previos
* Tener instalado **Docker Desktop** y **Git**.
* Descargar el dataset de Kaggle: Formula 1 World Championship (1950-2020).
* Descomprimir todos los archivos `.csv` dentro de la carpeta `data/`.

### 2. Levantar el Entorno con Docker Compose
Abre tu terminal en la raíz de tu repositorio local y ejecuta:

```bash
docker compose up -d --build
```

Verifica que los contenedores estén activos:
```bash
docker compose ps
```

### 3. Ejecutar la integración y carga
`spark-app` es un proceso de carga de una sola ejecución. Al terminar
correctamente queda en estado `Exited (0)`; esto es esperado y significa que
los datos ya fueron escritos en MongoDB. Para ver el proceso en primer plano:

```bash
docker compose up --build spark-app
```

El script carga los 14 CSV originales en la base `f1_db` y además crea las
colecciones `f1_carreras_consolidado` y `f1_tiempos_vuelta_consolidado`. También
guarda los dos CSV consolidados en `output/`.

Para ejecutar nuevamente solo la carga sin reconstruir la imagen:

```bash
docker compose run --rm spark-app
```

La carga es idempotente: en cada ejecución reemplaza el contenido de las
colecciones, evitando documentos duplicados.

Para comprobar las colecciones desde MongoDB:

```bash
docker exec -it f1_mongodb mongosh \
  -u f1user -p f1password --authenticationDatabase admin f1_db \
  --eval 'show collections'
```

Si se necesita dejar el proceso de Python abierto después de cargar:

```bash
docker compose run --rm spark-app python3 src/join_f1_data.py --keep-alive
```

### 4. Detener los Servicios
```bash
docker compose down
```
