"""Perfil estadistico exploratorio del dataset ERA5 1940-2025."""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

DATA_PATH = (
    ROOT
    / "data"
    / "processed"
    / "era5_master_1940_2025.csv"
)

OUTPUT_DIR = ROOT / "data" / "analysis"

SUMMARY_PATH = OUTPUT_DIR / "eda_summary.json"
ANNUAL_PATH = OUTPUT_DIR / "annual_summary.csv"
MONTHLY_PATH = OUTPUT_DIR / "monthly_summary.csv"
DECADE_PATH = OUTPUT_DIR / "decade_summary.csv"
CORRELATION_PATH = OUTPUT_DIR / "correlation_matrix.csv"

EXPECTED_ROWS = 753_888


def serializable_dict(series):
    """Convertir una Serie de pandas en un diccionario JSON."""

    result = {}

    for key, value in series.items():
        if pd.isna(value):
            result[str(key)] = None
        else:
            result[str(key)] = float(value)

    return result


def main():
    """Construir el perfil exploratorio principal."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=== CARGANDO DATASET MAESTRO ===")

    df = pd.read_csv(
        DATA_PATH,
        parse_dates=["timestamp"],
    )

    print(f"Filas: {len(df):,}")
    print(f"Columnas: {len(df.columns)}")

    if len(df) != EXPECTED_ROWS:
        raise ValueError(
            f"Se esperaban {EXPECTED_ROWS} filas "
            f"y se encontraron {len(df)}."
        )

    if df["timestamp"].duplicated().any():
        raise ValueError(
            "Se encontraron timestamps duplicados."
        )

    if df.isna().any().any():
        raise ValueError(
            "Se encontraron valores faltantes."
        )

    df["year"] = df["timestamp"].dt.year
    df["month"] = df["timestamp"].dt.month
    df["hour"] = df["timestamp"].dt.hour

    df["decade"] = (
        df["year"] // 10 * 10
    )

    df["rain_hour"] = (
        df["precipitation"] > 0
    )

    temperature = df["temperature_2m"]
    humidity = df["relative_humidity_2m"]
    precipitation = df["precipitation"]

    global_summary = {
        "rows": int(len(df)),
        "columns_original": 4,
        "first_timestamp": (
            df["timestamp"].iloc[0].isoformat()
        ),
        "last_timestamp": (
            df["timestamp"].iloc[-1].isoformat()
        ),
        "duplicate_timestamps": int(
            df["timestamp"].duplicated().sum()
        ),
        "missing_values": {
            column: int(value)
            for column, value
            in df.isna().sum().items()
        },
        "temperature_2m": {
            "mean": float(temperature.mean()),
            "std": float(temperature.std()),
            "min": float(temperature.min()),
            "p01": float(
                temperature.quantile(0.01)
            ),
            "p05": float(
                temperature.quantile(0.05)
            ),
            "median": float(
                temperature.median()
            ),
            "p95": float(
                temperature.quantile(0.95)
            ),
            "p99": float(
                temperature.quantile(0.99)
            ),
            "max": float(temperature.max()),
        },
        "relative_humidity_2m": {
            "mean": float(humidity.mean()),
            "std": float(humidity.std()),
            "min": float(humidity.min()),
            "median": float(humidity.median()),
            "max": float(humidity.max()),
        },
        "precipitation": {
            "mean_hourly": float(
                precipitation.mean()
            ),
            "median_hourly": float(
                precipitation.median()
            ),
            "max_hourly": float(
                precipitation.max()
            ),
            "total_mm": float(
                precipitation.sum()
            ),
            "rain_hours": int(
                df["rain_hour"].sum()
            ),
            "rain_hour_fraction": float(
                df["rain_hour"].mean()
            ),
        },
    }

    print("=== RESUMEN GLOBAL ===")

    print(
        "Temperatura media: "
        f"{global_summary['temperature_2m']['mean']:.3f} °C"
    )

    print(
        "Temperatura minima: "
        f"{global_summary['temperature_2m']['min']:.3f} °C"
    )

    print(
        "Temperatura maxima: "
        f"{global_summary['temperature_2m']['max']:.3f} °C"
    )

    print(
        "Humedad media: "
        f"{global_summary['relative_humidity_2m']['mean']:.3f} %"
    )

    print(
        "Precipitacion acumulada: "
        f"{global_summary['precipitation']['total_mm']:.3f} mm"
    )

    annual = (
        df.groupby("year")
        .agg(
            temperature_mean=(
                "temperature_2m",
                "mean",
            ),
            temperature_min=(
                "temperature_2m",
                "min",
            ),
            temperature_max=(
                "temperature_2m",
                "max",
            ),
            humidity_mean=(
                "relative_humidity_2m",
                "mean",
            ),
            precipitation_total=(
                "precipitation",
                "sum",
            ),
            rain_hours=(
                "rain_hour",
                "sum",
            ),
        )
        .reset_index()
    )

    monthly = (
        df.groupby("month")
        .agg(
            temperature_mean=(
                "temperature_2m",
                "mean",
            ),
            humidity_mean=(
                "relative_humidity_2m",
                "mean",
            ),
            precipitation_mean_hourly=(
                "precipitation",
                "mean",
            ),
            precipitation_total=(
                "precipitation",
                "sum",
            ),
            rain_fraction=(
                "rain_hour",
                "mean",
            ),
        )
        .reset_index()
    )

    annual["decade"] = (
        annual["year"] // 10 * 10
    )

    decade = (
        annual.groupby("decade")
        .agg(
            years=(
                "year",
                "count",
            ),
            temperature_mean=(
                "temperature_mean",
                "mean",
            ),
            humidity_mean=(
                "humidity_mean",
                "mean",
            ),
            precipitation_mean_annual=(
                "precipitation_total",
                "mean",
            ),
            precipitation_std_annual=(
                "precipitation_total",
                "std",
            ),
        )
        .reset_index()
    )

    correlations = df[
        [
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
        ]
    ].corr()

    autocorrelation = {
        "temperature_lag_1h": float(
            temperature.autocorr(lag=1)
        ),
        "temperature_lag_24h": float(
            temperature.autocorr(lag=24)
        ),
        "temperature_lag_168h": float(
            temperature.autocorr(lag=168)
        ),
    }

    global_summary["autocorrelation"] = (
        autocorrelation
    )

    global_summary["correlations"] = {
        row: serializable_dict(
            correlations.loc[row]
        )
        for row in correlations.index
    }

    global_summary["annual_temperature"] = {
        "coldest_mean_year": int(
            annual.loc[
                annual["temperature_mean"].idxmin(),
                "year",
            ]
        ),
        "coldest_mean_temperature": float(
            annual["temperature_mean"].min()
        ),
        "warmest_mean_year": int(
            annual.loc[
                annual["temperature_mean"].idxmax(),
                "year",
            ]
        ),
        "warmest_mean_temperature": float(
            annual["temperature_mean"].max()
        ),
    }

    global_summary["annual_precipitation"] = {
        "driest_year": int(
            annual.loc[
                annual["precipitation_total"].idxmin(),
                "year",
            ]
        ),
        "driest_total_mm": float(
            annual["precipitation_total"].min()
        ),
        "wettest_year": int(
            annual.loc[
                annual["precipitation_total"].idxmax(),
                "year",
            ]
        ),
        "wettest_total_mm": float(
            annual["precipitation_total"].max()
        ),
    }

    annual.to_csv(
        ANNUAL_PATH,
        index=False,
    )

    monthly.to_csv(
        MONTHLY_PATH,
        index=False,
    )

    decade.to_csv(
        DECADE_PATH,
        index=False,
    )

    correlations.to_csv(
        CORRELATION_PATH,
        index_label="variable",
    )

    SUMMARY_PATH.write_text(
        json.dumps(
            global_summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\n=== HALLAZGOS INICIALES ===")

    print(
        "Año con menor temperatura media: "
        f"{global_summary['annual_temperature']['coldest_mean_year']} "
        f"("
        f"{global_summary['annual_temperature']['coldest_mean_temperature']:.3f}"
        " °C)"
    )

    print(
        "Año con mayor temperatura media: "
        f"{global_summary['annual_temperature']['warmest_mean_year']} "
        f"("
        f"{global_summary['annual_temperature']['warmest_mean_temperature']:.3f}"
        " °C)"
    )

    print(
        "Año con menor precipitacion: "
        f"{global_summary['annual_precipitation']['driest_year']} "
        f"("
        f"{global_summary['annual_precipitation']['driest_total_mm']:.1f}"
        " mm)"
    )

    print(
        "Año con mayor precipitacion: "
        f"{global_summary['annual_precipitation']['wettest_year']} "
        f"("
        f"{global_summary['annual_precipitation']['wettest_total_mm']:.1f}"
        " mm)"
    )

    print("\n=== AUTOCORRELACION DE TEMPERATURA ===")

    for name, value in autocorrelation.items():
        print(f"{name}: {value:.6f}")

    print("\nArchivos generados:")

    for path in (
        SUMMARY_PATH,
        ANNUAL_PATH,
        MONTHLY_PATH,
        DECADE_PATH,
        CORRELATION_PATH,
    ):
        print(path)


if __name__ == "__main__":
    main()
