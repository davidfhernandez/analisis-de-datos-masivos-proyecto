"""Integra los CSV de Formula 1 y los carga en MongoDB.

El proceso es deliberadamente de una sola ejecucion: genera los CSV
consolidados y reemplaza el contenido de las colecciones de MongoDB.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from pymongo import MongoClient
from pymongo.collection import Collection


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_DIR / "data"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "output"
DEFAULT_MONGO_URI = (
    "mongodb://f1user:f1password@localhost:27017/f1_db?authSource=admin"
)
MONGO_BATCH_SIZE = 5_000


def read_csv(data_dir: Path, filename: str) -> pd.DataFrame:
    """Lee un CSV del dataset y convierte el marcador ``\\N`` a nulo."""

    path = data_dir / filename
    if not path.is_file():
        raise FileNotFoundError(f"No existe el archivo requerido: {path}")

    return pd.read_csv(path, na_values=[r"\N"], keep_default_na=True)


def load_and_join_f1_data(
    data_dir: str | Path = DEFAULT_DATA_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Une los datos de carrera y los datos de vueltas, y guarda ambos CSV."""

    data_path = Path(data_dir)
    output_path = Path(output_dir)
    print(f"=== Cargando tablas desde: {data_path}", flush=True)

    races = read_csv(data_path, "races.csv")
    results = read_csv(data_path, "results.csv")
    drivers = read_csv(data_path, "drivers.csv")
    constructors = read_csv(data_path, "constructors.csv")
    circuits = read_csv(data_path, "circuits.csv")
    status = read_csv(data_path, "status.csv")

    races_clean = races[
        ["raceId", "year", "round", "circuitId", "name", "date"]
    ].rename(columns={"name": "race_name", "date": "race_date"})

    drivers = drivers.copy()
    drivers["driver_fullname"] = (
        drivers[["forename", "surname"]]
        .fillna("")
        .astype(str)
        .agg(" ".join, axis=1)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    drivers_clean = drivers[
        ["driverId", "driverRef", "driver_fullname", "nationality", "dob"]
    ].rename(columns={"nationality": "driver_nationality"})

    constructors_clean = constructors[
        ["constructorId", "constructorRef", "name", "nationality"]
    ].rename(
        columns={
            "name": "constructor_name",
            "nationality": "constructor_nationality",
        }
    )

    circuits_clean = circuits[
        ["circuitId", "circuitRef", "name", "location", "country", "lat", "lng"]
    ].rename(columns={"name": "circuit_name"})

    status_clean = status[["statusId", "status"]]

    print("--> Uniendo resultados de carrera...", flush=True)
    df_main = results.merge(races_clean, on="raceId", how="left")
    df_main = df_main.merge(drivers_clean, on="driverId", how="left")
    df_main = df_main.merge(constructors_clean, on="constructorId", how="left")
    df_main = df_main.merge(circuits_clean, on="circuitId", how="left")
    df_main = df_main.merge(status_clean, on="statusId", how="left")

    qualifying_path = data_path / "qualifying.csv"
    if qualifying_path.is_file():
        print("--> Uniendo qualifying...", flush=True)
        qualifying = read_csv(data_path, "qualifying.csv")
        qualifying_clean = qualifying[
            ["raceId", "driverId", "position", "q1", "q2", "q3"]
        ].rename(columns={"position": "qualifying_position"})
        df_main = df_main.merge(
            qualifying_clean, on=["raceId", "driverId"], how="left"
        )

    df_laps_full: pd.DataFrame | None = None
    lap_times_path = data_path / "lap_times.csv"
    if lap_times_path.is_file():
        print("--> Procesando lap_times...", flush=True)
        lap_times = read_csv(data_path, "lap_times.csv")

        pit_stops_path = data_path / "pit_stops.csv"
        if pit_stops_path.is_file():
            print("--> Integrando pit_stops...", flush=True)
            pit_stops = read_csv(data_path, "pit_stops.csv")
            pit_stops_clean = pit_stops[
                ["raceId", "driverId", "stop", "lap", "duration", "milliseconds"]
            ].rename(
                columns={
                    "duration": "pit_duration",
                    "milliseconds": "pit_milliseconds",
                }
            )
            lap_times = lap_times.merge(
                pit_stops_clean,
                on=["raceId", "driverId", "lap"],
                how="left",
            )

        context_cols = [
            "raceId",
            "driverId",
            "year",
            "race_name",
            "driver_fullname",
            "constructor_name",
            "circuit_name",
        ]
        # results.csv contiene algunos pares raceId-driverId repetidos. Si se
        # usa df_main directamente, cada vuelta se duplica en esos casos.
        lap_context = df_main[context_cols].drop_duplicates(
            subset=["raceId", "driverId"], keep="first"
        )
        df_laps_full = lap_times.merge(
            lap_context, on=["raceId", "driverId"], how="left"
        )

    output_path.mkdir(parents=True, exist_ok=True)
    main_out = output_path / "f1_carreras_consolidado.csv"
    df_main.to_csv(main_out, index=False)
    print(f"OK: {main_out} ({len(df_main):,} registros)", flush=True)

    if df_laps_full is not None:
        laps_out = output_path / "f1_tiempos_vuelta_consolidado.csv"
        df_laps_full.to_csv(laps_out, index=False)
        print(f"OK: {laps_out} ({len(df_laps_full):,} registros)", flush=True)

    return df_main, df_laps_full


def _mongo_value(value: Any) -> Any:
    """Convierte valores de pandas/numpy a tipos que BSON puede serializar."""

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()

    # Convierte numpy.int64, numpy.float64, numpy.bool_, etc. a tipos nativos.
    item = getattr(value, "item", None)
    if callable(item):
        return item()

    return value


def _records_from_dataframe(dataframe: pd.DataFrame) -> Iterable[dict[str, Any]]:
    columns = list(dataframe.columns)
    for row in dataframe.itertuples(index=False, name=None):
        yield {
            column: _mongo_value(value) for column, value in zip(columns, row)
        }


def replace_collection(
    collection: Collection,
    dataframe: pd.DataFrame,
    batch_size: int = MONGO_BATCH_SIZE,
) -> int:
    """Reemplaza una coleccion por el contenido del DataFrame, por lotes."""

    collection.delete_many({})
    inserted = 0
    batch: list[dict[str, Any]] = []

    for record in _records_from_dataframe(dataframe):
        batch.append(record)
        if len(batch) >= batch_size:
            collection.insert_many(batch, ordered=False)
            inserted += len(batch)
            batch.clear()

    if batch:
        collection.insert_many(batch, ordered=False)
        inserted += len(batch)

    return inserted


def wait_for_mongo(
    mongo_uri: str,
    retries: int = 30,
    delay_seconds: float = 2.0,
) -> MongoClient:
    """Espera hasta que MongoDB acepte conexiones y responda a ping."""

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2_000)
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            client.admin.command("ping")
            print(f"OK: MongoDB disponible (intento {attempt})", flush=True)
            return client
        except Exception as error:  # Mongo puede tardar en inicializarse.
            last_error = error
            print(f"Esperando MongoDB ({attempt}/{retries})...", flush=True)
            time.sleep(delay_seconds)

    client.close()
    raise RuntimeError("MongoDB no estuvo disponible a tiempo") from last_error


def load_csvs_to_mongo(
    data_dir: str | Path,
    main_dataframe: pd.DataFrame,
    laps_dataframe: pd.DataFrame | None,
    mongo_uri: str,
    mongo_db: str = "f1_db",
) -> None:
    """Carga todos los CSV originales y los dos consolidados en MongoDB."""

    data_path = Path(data_dir)
    client = wait_for_mongo(mongo_uri)
    database = client[mongo_db]

    try:
        csv_paths = sorted(data_path.glob("*.csv"))
        if not csv_paths:
            raise FileNotFoundError(f"No hay archivos CSV en {data_path}")

        print(
            f"=== Cargando {len(csv_paths)} tablas originales en {mongo_db}",
            flush=True,
        )
        for csv_path in csv_paths:
            dataframe = read_csv(data_path, csv_path.name)
            inserted = replace_collection(database[csv_path.stem], dataframe)
            print(
                f"OK: {mongo_db}.{csv_path.stem} ({inserted:,} documentos)",
                flush=True,
            )

        inserted = replace_collection(
            database["f1_carreras_consolidado"], main_dataframe
        )
        print(
            f"OK: {mongo_db}.f1_carreras_consolidado ({inserted:,} documentos)",
            flush=True,
        )

        if laps_dataframe is not None:
            inserted = replace_collection(
                database["f1_tiempos_vuelta_consolidado"], laps_dataframe
            )
            print(
                "OK: "
                f"{mongo_db}.f1_tiempos_vuelta_consolidado "
                f"({inserted:,} documentos)",
                flush=True,
            )
    finally:
        client.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Integra los CSV de F1 y los carga en MongoDB."
    )
    parser.add_argument(
        "--data-dir",
        default=os.getenv("DATA_DIR", str(DEFAULT_DATA_DIR)),
        help="Directorio que contiene los CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)),
        help="Directorio para los CSV consolidados.",
    )
    parser.add_argument(
        "--mongo-uri",
        default=os.getenv("MONGO_URI", DEFAULT_MONGO_URI),
        help="URI de conexion a MongoDB.",
    )
    parser.add_argument(
        "--mongo-db",
        default=os.getenv("MONGO_DB", "f1_db"),
        help="Nombre de la base de datos MongoDB.",
    )
    parser.add_argument(
        "--skip-mongo",
        action="store_true",
        help="Solo genera los CSV consolidados; no conecta a MongoDB.",
    )
    parser.add_argument(
        "--keep-alive",
        action="store_true",
        help="Mantiene el proceso activo despues de cargar los datos.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    main_dataframe, laps_dataframe = load_and_join_f1_data(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
    )

    if not args.skip_mongo:
        load_csvs_to_mongo(
            data_dir=args.data_dir,
            main_dataframe=main_dataframe,
            laps_dataframe=laps_dataframe,
            mongo_uri=args.mongo_uri,
            mongo_db=args.mongo_db,
        )

    print("=== Proceso terminado correctamente ===", flush=True)

    if args.keep_alive:
        print("Modo keep-alive activo. Presiona Ctrl+C para salir.", flush=True)
        try:
            while True:
                time.sleep(3_600)
        except KeyboardInterrupt:
            print("Proceso detenido por el usuario.", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
