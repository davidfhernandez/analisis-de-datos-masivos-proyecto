import os
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account


def export_to_bigquery():
    print("🚀 Iniciando exportación de tablas a Google BigQuery...")
    project_id = "fluted-set-423901-d4"
    dataset_id = "f1_bigdata"
    location = "us-east1"
    current_dir = os.path.dirname(os.path.abspath(__file__))
    key_path = os.path.join(current_dir, "../credentials_f1_gcp.json")

    # 1. Validar existencia de credenciales
    if not os.path.exists(key_path):
        raise FileNotFoundError(
            f"❌ No se encontró el archivo en: {os.path.abspath(key_path)}\n"
            f"Por favor, descarga el JSON de tu Service Account de GCP y colócalo en la carpeta correcta."
        )

    # 2. Autenticación explícita con el archivo JSON
    credentials = service_account.Credentials.from_service_account_file(key_path)
    client = bigquery.Client(project=project_id, credentials=credentials)
    dataset_ref = f"{project_id}.{dataset_id}"

    # 3. Crear Dataset si no existe
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = location
    dataset = client.create_dataset(dataset, exists_ok=True)
    print(f"✅ Dataset {dataset_ref} verificado/listo en BigQuery ({location}).")

    # 4. Carga de Tabla 1: Carreras Consolidado
    races_path = os.path.join(
        current_dir, "..", "output", "f1_carreras_consolidado.csv"
    )
    if os.path.exists(races_path):
        print("📦 Cargando f1_carreras_consolidado ...")
        df_races = pd.read_csv(races_path, low_memory=False)
        df_races.to_gbq(
            destination_table=f"{dataset_id}.f1_carreras_consolidado",
            project_id=project_id,
            if_exists="replace",
            credentials=credentials,
        )
        print("✅ Tabla f1_carreras_consolidado subida exitosamente.")

    # 5. Carga de Tabla 2: Tiempos de Vuelta Consolidado
    lap_times_path = os.path.join(
        current_dir, "..", "output", "f1_tiempos_vuelta_consolidado.csv"
    )
    if os.path.exists(lap_times_path):
        print("📦 Cargando f1_tiempos_vuelta_consolidado ...")
        df_lap_times = pd.read_csv(lap_times_path, low_memory=False)
        df_lap_times.to_gbq(
            destination_table=f"{dataset_id}.f1_tiempos_vuelta_consolidado",
            project_id=project_id,
            if_exists="replace",
            credentials=credentials,
        )
        print("✅ Tabla f1_tiempos_vuelta_consolidado subida exitosamente.")

    print(
        "\n🎉 Datos cargados en BigQuery. ¡Listos para crear vistas o conectar a Looker Studio!"
    )


if __name__ == "__main__":
    export_to_bigquery()
