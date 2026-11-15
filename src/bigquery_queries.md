#### **🏎️ 1. El Mito de la *Pole Position* vs. Circuitos de Remontada**

- **Tabla origen**: `f1_carreras_consolidado`
- **Pregunta**: ¿En qué circuitos clasificar 1º el sábado asegura casi el 100% de la victoria el domingo frente a circuitos donde se puede remontar?
- **Valor**:
  - 🔰 **Principiante**: Entiende por qué el sábado de Mónaco es tan crucial mientras que en Spa o Monza la carrera se decide el domingo.
  - 🏎️ **Aficionado**: Sabe qué circuitos premiarán la velocidad a 1 vuelta y cuáles la gestión de ritmo de carrera.
  - 📊 **Experto**: Obtiene la probabilidad condicional de victoria desde la *Pole* y el promedio de puestos remontados por el ganador.

```SQL
SELECT
  circuit_name,
  country,
  COUNT(DISTINCT raceId) AS total_carreras,
  COUNTIF(
    SAFE_CAST(grid AS INT64) = 1
    AND SAFE_CAST(positionOrder AS INT64) = 1) AS victorias_desde_pole,
  ROUND(
    COUNTIF(
      SAFE_CAST(grid AS INT64) = 1
      AND SAFE_CAST(positionOrder AS INT64) = 1)
      * 100.0 / NULLIF(COUNT(DISTINCT raceId), 0),
    2) AS pct_victoria_pole,
  ROUND(
    AVG(
      CASE
        WHEN
          SAFE_CAST(positionOrder AS INT64) = 1
          AND SAFE_CAST(grid AS INT64) > 1
          THEN SAFE_CAST(grid AS INT64) - 1
        END),
    2) AS promedio_remontada_ganador,
  MAX(
    CASE
      WHEN SAFE_CAST(positionOrder AS INT64) = 1
        THEN SAFE_CAST(grid AS INT64)
      END) AS peor_posicion_salida_ganador
FROM
  `fluted-set-423901-d4.f1_bigdata.f1_carreras_consolidado`
WHERE
  SAFE_CAST(grid AS INT64) > 0
  AND SAFE_CAST(positionOrder AS INT64) IS NOT NULL
GROUP BY
  circuit_name,
  country
HAVING
  total_carreras >= 10
ORDER BY
  pct_victoria_pole DESC;
```

#### **⏱️ 2. Eficiencia Operativa en Pit Stops por Escudería (2011–2020)**

- **Tabla origen**: `f1_tiempos_vuelta_consolidado`
- **Pregunta**: ¿Qué escuderías tienen el equipo de mecánicos en boxes más rápido y consistente en la F1 moderna?
- **Valor**:
  - 🔰 **Principiante**: Entiende qué es una parada en pits y qué se considera una parada lenta o fallida.
  - 🏎️ **Aficionado**: Compara la ejecución de Red Bull vs. los errores estratégicos de Ferrari o Mercedes.
  - 📊 **Experto**: Analiza la mediana del tiempo en pitlane y la tasa de paradas lentas (>30 segundos en pitlane).


```SQL
SELECT
  constructor_name,
  year,
  COUNT(stop) AS total_pit_stops,
  ROUND(AVG(pit_milliseconds / 1000.0), 2) AS tiempo_promedio_pitlane_seg,
  ROUND(MIN(pit_milliseconds / 1000.0), 2) AS tiempo_minimo_pitlane_seg,
  COUNTIF(pit_milliseconds / 1000.0 > 30.0) AS paradas_lentas_count,
  ROUND(
    COUNTIF(pit_milliseconds / 1000.0 > 30.0) * 100.0 / NULLIF(COUNT(stop), 0),
    2) AS pct_paradas_lentas
FROM
  `fluted-set-423901-d4.f1_bigdata.f1_tiempos_vuelta_consolidado`
WHERE
  year BETWEEN 2011 AND 2024
  AND stop IS NOT NULL
  AND pit_milliseconds IS NOT NULL
  AND (pit_milliseconds / 1000.0) BETWEEN 12.0 AND 60.0
GROUP BY
  constructor_name,
  year
ORDER BY
  year DESC,
  tiempo_promedio_pitlane_seg ASC;
```

#### **🛠️ 3. Evolución de Confiabilidad Mecánica por Eras Tecnológicas**

- **Tabla origen**: `f1_carreras_consolidado`
- **Pregunta**: ¿Cómo evolucionó la F1 desde una época frágil (donde fallaba el 40% de los motores) hasta la era Híbrida de ultra-confiabilidad?
- **Valor**:
  - 🔰 **Principiante**: Entiende la historia del deporte y por qué los autos de hoy casi siempre terminan la carrera.
  - 🏎️ **Aficionado**: Clasifica los abandonos entre errores humanos (accidentes/trompos) vs. fallas de ingeniería (motor, caja, frenos).
  - 📊 **Experto**: Mide el porcentaje de efectividad de llegada por normativa de motor (V10, V8, Turbo-Híbrido).


```SQL
SELECT
  CASE
    WHEN year BETWEEN 1950 AND 1965 THEN 'Era Antigua (1950-1965)'
    WHEN year BETWEEN 1966 AND 1988 THEN 'Era Turbo / Cosworth (1966-1988)'
    WHEN year BETWEEN 1989 AND 2013 THEN 'Era V10 / V8 (1989-2013)'
    ELSE 'Era Turbo-Híbrida (2014-2020)'
    END AS era_tecnologica,
  COUNT(*) AS total_participaciones,
  COUNTIF(
    LOWER(status) = 'finished'
    OR LOWER(status) LIKE '%lap%') AS finalizados,
  COUNTIF(
    LOWER(status) LIKE '%accident%'
    OR LOWER(status) LIKE '%collision%'
    OR LOWER(status) LIKE '%spun%') AS accidentes,
  COUNTIF(
    LOWER(status) != 'finished'
    AND LOWER(status) NOT LIKE '%lap%'
    AND LOWER(status) NOT LIKE '%accident%'
    AND LOWER(status) NOT LIKE '%collision%'
    AND LOWER(status) NOT LIKE '%spun%') AS fallas_mecanicas_tecnicas,
  ROUND(
    COUNTIF(
      LOWER(status) != 'finished'
      AND LOWER(status) NOT LIKE '%lap%'
      AND LOWER(status) NOT LIKE '%accident%'
      AND LOWER(status) NOT LIKE '%collision%'
      AND LOWER(status) NOT LIKE '%spun%')
      * 100.0 / COUNT(*),
    2) AS pct_fallas_mecanicas,
  ROUND(
    COUNTIF(
      LOWER(status) = 'finished'
      OR LOWER(status) LIKE '%lap%')
      * 100.0
      / COUNT(*),
    2) AS pct_efectividad_llegada
FROM
  `fluted-set-423901-d4.f1_bigdata.f1_carreras_consolidado`
GROUP BY
  era_tecnologica
ORDER BY
  MIN(year) ASC;
```

#### **🏆 4. Concentración de Dominio entre Escuderías Top vs. Midfield**

- **Tabla origen**: `f1_carreras_consolidado`
- **Pregunta**: ¿Qué años registraron un dominio absoluto de una sola escudería y cuántos puntos/podios acumularon frente al resto?
- **Valor**:
  - 🔰 **Principiante**: Aprende a seguir la "carrera secundaria" dentro de la zona media (*Midfield*).
  - 🏎️ **Aficionado**: Compara con datos reales las eras dominantes de Ferrari (Schumacher), Red Bull (Vettel) y Mercedes (Hamilton).
  - 📊 **Experto**: Evalúa la concentración de puntos acumulados por temporada para medir la paridad del campeonato.


```SQL
SELECT
  year,
  constructor_name,
  COUNT(DISTINCT raceId) AS carreras_disputadas,
  COUNTIF(SAFE_CAST(positionOrder AS INT64) = 1) AS victorias,
  COUNTIF(SAFE_CAST(positionOrder AS INT64) <= 3) AS podios,
  ROUND(SUM(SAFE_CAST(points AS FLOAT64)), 1) AS puntos_totales
FROM
  `fluted-set-423901-d4.f1_bigdata.f1_carreras_consolidado`
WHERE
  constructor_name IS NOT NULL
GROUP BY
  year,
  constructor_name
ORDER BY
  year DESC,
  puntos_totales DESC;
```
