"""Construccion reproducible del dataset maestro ERA5 1940-2025."""

import calendar
import csv
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

START_YEAR = 1940
END_YEAR = 2025

VARIABLES = (
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
)

OUTPUT_PATH = (
    PROCESSED_DIR
    / f"era5_master_{START_YEAR}_{END_YEAR}.csv"
)

SUMMARY_PATH = (
    PROCESSED_DIR
    / f"era5_master_{START_YEAR}_{END_YEAR}_summary.json"
)


def expected_records(year):
    """Numero esperado de observaciones horarias."""

    days = 366 if calendar.isleap(year) else 365
    return days * 24


def file_sha256(path):
    """Calcular SHA-256 de un archivo."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def main():
    """Construir y validar el dataset maestro."""

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    expected_total = sum(
        expected_records(year)
        for year in range(START_YEAR, END_YEAR + 1)
    )

    temporary_path = OUTPUT_PATH.with_suffix(".csv.tmp")

    total_records = 0
    previous_time = None
    first_time = None
    last_time = None

    yearly_records = {}

    print("=== CONSTRUCCION DATASET MAESTRO ===")
    print(f"Periodo: {START_YEAR}-{END_YEAR}")
    print(f"Registros esperados: {expected_total}")

    with temporary_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as csv_file:

        writer = csv.writer(csv_file)

        writer.writerow(
            [
                "timestamp",
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation",
            ]
        )

        for year in range(START_YEAR, END_YEAR + 1):

            raw_path = RAW_DIR / f"era5_{year}.json"

            if not raw_path.exists():
                raise FileNotFoundError(
                    f"Falta el archivo {raw_path}"
                )

            data = json.loads(
                raw_path.read_text(encoding="utf-8")
            )

            hourly = data["hourly"]

            times = hourly["time"]

            lengths = {
                "time": len(times),
                **{
                    variable: len(hourly[variable])
                    for variable in VARIABLES
                },
            }

            if len(set(lengths.values())) != 1:
                raise ValueError(
                    f"{year}: longitudes inconsistentes: "
                    f"{lengths}"
                )

            expected_year = expected_records(year)

            if len(times) != expected_year:
                raise ValueError(
                    f"{year}: esperados {expected_year}, "
                    f"recibidos {len(times)}"
                )

            year_count = 0

            for index, timestamp_text in enumerate(times):

                current_time = datetime.fromisoformat(
                    timestamp_text
                )

                if first_time is None:
                    first_time = current_time

                if previous_time is not None:
                    expected_next = (
                        previous_time + timedelta(hours=1)
                    )

                    if current_time != expected_next:
                        raise ValueError(
                            "Ruptura temporal entre "
                            f"{previous_time.isoformat()} y "
                            f"{current_time.isoformat()}"
                        )

                values = [
                    hourly[variable][index]
                    for variable in VARIABLES
                ]

                if any(value is None for value in values):
                    raise ValueError(
                        f"{year}: valor faltante en "
                        f"{timestamp_text}"
                    )

                writer.writerow(
                    [timestamp_text, *values]
                )

                previous_time = current_time
                last_time = current_time
                total_records += 1
                year_count += 1

            yearly_records[str(year)] = year_count

            print(
                f"{year}: OK | "
                f"{year_count} registros"
            )

    if total_records != expected_total:
        raise ValueError(
            f"Total incorrecto: {total_records}; "
            f"esperados: {expected_total}"
        )

    temporary_path.replace(OUTPUT_PATH)

    sha256 = file_sha256(OUTPUT_PATH)

    summary = {
        "source": "Open-Meteo ERA5",
        "start_year": START_YEAR,
        "end_year": END_YEAR,
        "raw_files": END_YEAR - START_YEAR + 1,
        "variables": list(VARIABLES),
        "columns": [
            "timestamp",
            *VARIABLES,
        ],
        "expected_records": expected_total,
        "written_records": total_records,
        "first_timestamp": first_time.isoformat(
            timespec="minutes"
        ),
        "last_timestamp": last_time.isoformat(
            timespec="minutes"
        ),
        "continuous_timeline": True,
        "yearly_records": yearly_records,
        "csv_file": OUTPUT_PATH.name,
        "csv_size_bytes": OUTPUT_PATH.stat().st_size,
        "csv_sha256": sha256,
        "passed": total_records == expected_total,
    }

    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\n=== RESULTADO ===")
    print(f"Registros escritos: {total_records}")
    print(
        "Primer timestamp: "
        f"{summary['first_timestamp']}"
    )
    print(
        "Ultimo timestamp: "
        f"{summary['last_timestamp']}"
    )
    print(
        "Tamaño CSV: "
        f"{OUTPUT_PATH.stat().st_size / 1024 / 1024:.2f} MB"
    )
    print(f"SHA-256: {sha256}")
    print(f"Dataset: {OUTPUT_PATH}")
    print(f"Resumen: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
