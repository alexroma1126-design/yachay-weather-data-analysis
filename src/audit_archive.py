"""Auditoria reproducible del archivo historico ERA5."""

import argparse
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
REPORT_DIR = ROOT / "data" / "processed"

API_URL = "https://archive-api.open-meteo.com/v1/archive"

LATITUDE = 0.59354
LONGITUDE = -77.83066

VARIABLES = (
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
)


def save_json(path, content):
    """Guardar un JSON sin sobrescribirlo parcialmente."""

    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(path.suffix + ".tmp")

    temporary.write_text(
        json.dumps(content, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    temporary.replace(path)


def download_year(year):
    """Solicitar un año completo de ERA5."""

    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "hourly": ",".join(VARIABLES),
        "timezone": "America/Guayaquil",
        "models": "era5",
    }

    url = API_URL + "?" + urlencode(params)

    with urlopen(url, timeout=120) as response:
        return json.load(response)


def audit_year(data, year):
    """Comprobar integridad temporal y calidad basica."""

    hourly = data["hourly"]
    timestamps = hourly["time"]

    start = datetime(year, 1, 1)
    end = datetime(year + 1, 1, 1)

    expected = []
    current = start

    while current < end:
        expected.append(
            current.isoformat(timespec="minutes")
        )
        current += timedelta(hours=1)

    lengths = {}
    missing = {}
    invalid = {}

    for variable in VARIABLES:
        values = hourly[variable]

        lengths[variable] = len(values)

        missing[variable] = sum(
            value is None for value in values
        )

        invalid[variable] = sum(
            value is not None
            and (
                not isinstance(value, (int, float))
                or not math.isfinite(value)
                or (
                    variable == "relative_humidity_2m"
                    and not 0 <= value <= 100
                )
                or (
                    variable == "precipitation"
                    and value < 0
                )
            )
            for value in values
        )

    report = {
        "year": year,
        "source": "Open-Meteo ERA5",
        "requested_latitude": LATITUDE,
        "requested_longitude": LONGITUDE,
        "grid_latitude": data["latitude"],
        "grid_longitude": data["longitude"],
        "expected_records": len(expected),
        "received_records": len(timestamps),
        "duplicate_timestamps": (
            len(timestamps) - len(set(timestamps))
        ),
        "continuous_timeline": timestamps == expected,
        "variable_lengths": lengths,
        "missing_values": missing,
        "invalid_values": invalid,
    }

    report["passed"] = (
        report["continuous_timeline"]
        and report["duplicate_timestamps"] == 0
        and all(
            count == len(expected)
            for count in lengths.values()
        )
        and all(count == 0 for count in missing.values())
        and all(count == 0 for count in invalid.values())
    )

    return report


def process_year(year):
    """Auditar la cache o descargar nuevamente el año."""

    raw_path = RAW_DIR / f"era5_{year}.json"
    report_path = REPORT_DIR / f"era5_{year}_audit.json"

    data = None
    report = None

    if raw_path.exists():
        try:
            data = json.loads(raw_path.read_text(encoding="utf-8"))
            report = audit_year(data, year)

            if report["passed"]:
                print(f"{year}: datos locales verificados.")
            else:
                print(f"{year}: cache incompleta; descargando.")
                data = None

        except (ValueError, KeyError, TypeError):
            print(f"{year}: cache invalida; descargando.")
            data = None

    if data is None:
        print(f"{year}: consultando Open-Meteo...")

        data = download_year(year)
        report = audit_year(data, year)

        if report["passed"]:
            save_json(raw_path, data)

    save_json(report_path, report)

    status = "OK" if report["passed"] else "FALLO"

    print(
        f"{year}: {status} | "
        f"{report['received_records']} registros"
    )

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Auditoria historica de ERA5."
    )

    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)

    args = parser.parse_args()

    if not 1940 <= args.start_year <= args.end_year <= 2025:
        parser.error(
            "Selecciona un periodo entre 1940 y 2025."
        )

    summary = {
        "source": "Open-Meteo ERA5",
        "start_year": args.start_year,
        "end_year": args.end_year,
        "years": [],
    }

    failures = 0

    for year in range(args.start_year, args.end_year + 1):
        try:
            report = process_year(year)

            summary["years"].append({
                "year": year,
                "passed": report["passed"],
                "records": report["received_records"],
            })

            if not report["passed"]:
                failures += 1

        except Exception as error:
            failures += 1

            summary["years"].append({
                "year": year,
                "passed": False,
                "error": str(error),
            })

            print(f"{year}: ERROR - {error}")

    summary["passed"] = failures == 0
    summary["failed_years"] = failures

    summary_path = (
        REPORT_DIR
        / f"era5_audit_summary_{args.start_year}_{args.end_year}.json"
    )

    save_json(summary_path, summary)

    print("\n=== RESUMEN ===")
    print(json.dumps(summary, indent=2))
    print(f"\nInforme: {summary_path}")

    if failures:
        raise SystemExit(
            f"Auditoria incompleta: {failures} años fallidos."
        )


if __name__ == "__main__":
    main()
