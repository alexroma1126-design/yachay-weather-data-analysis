
"""Auditoria inicial del archivo meteorologico ERA5."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


# Configuracion de nuestra primera prueba
YEAR = 2025
LATITUDE = 0.59354
LONGITUDE = -77.83066

VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
]

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
REPORT_DIR = ROOT / "data" / "processed"

RAW_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    """Descarga y audita un año de datos horarios."""

    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start_date": f"{YEAR}-01-01",
        "end_date": f"{YEAR}-12-31",
        "hourly": ",".join(VARIABLES),
        "timezone": "America/Guayaquil",
        "models": "era5",
    }

    url = (
        "https://archive-api.open-meteo.com/v1/archive?"
        + urlencode(params)
    )

    print(f"Consultando ERA5 para {YEAR}...")

    with urlopen(url, timeout=120) as response:
        data = json.load(response)

    # Conservar la respuesta original de la API.
    raw_path = RAW_DIR / f"era5_{YEAR}.json"
    raw_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    hourly = data["hourly"]

    # Construir la secuencia horaria que deberia existir.
    start = datetime(YEAR, 1, 1)
    end = datetime(YEAR + 1, 1, 1)

    expected = []
    current = start

    while current < end:
        expected.append(current)
        current += timedelta(hours=1)

    received = [
        datetime.fromisoformat(value)
        for value in hourly["time"]
    ]

    missing = {
        variable: sum(
            value is None
            for value in hourly[variable]
        )
        for variable in VARIABLES
    }

    lengths = {
        variable: len(hourly[variable])
        for variable in VARIABLES
    }

    report = {
        "year": YEAR,
        "source": "Open-Meteo ERA5",
        "requested_latitude": LATITUDE,
        "requested_longitude": LONGITUDE,
        "grid_latitude": data["latitude"],
        "grid_longitude": data["longitude"],
        "expected_records": len(expected),
        "received_records": len(received),
        "duplicate_timestamps": (
            len(received) - len(set(received))
        ),
        "continuous_timeline": received == expected,
        "variable_lengths": lengths,
        "missing_values": missing,
    }

    report["passed"] = (
        report["continuous_timeline"]
        and report["duplicate_timestamps"] == 0
        and all(
            count == len(expected)
            for count in lengths.values()
        )
        and all(
            count == 0
            for count in missing.values()
        )
    )

    report_path = REPORT_DIR / f"era5_{YEAR}_audit.json"

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))
    print(f"Datos guardados en: {raw_path}")
    print(f"Informe guardado en: {report_path}")

    if not report["passed"]:
        raise SystemExit("La auditoria no fue superada.")


if __name__ == "__main__":
    main()