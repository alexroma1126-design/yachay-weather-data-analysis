"""Diagnosticos estocasticos iniciales para ERA5 1940-2025."""

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

DATA_PATH = (
    ROOT
    / "data"
    / "processed"
    / "era5_master_1940_2025.csv"
)

OUTPUT_DIR = ROOT / "data" / "analysis"

SUMMARY_PATH = (
    OUTPUT_DIR
    / "stochastic_diagnostics.json"
)

CLIMATOLOGY_PATH = (
    OUTPUT_DIR
    / "temperature_month_hour_climatology.csv"
)

AUTOCORRELATION_PATH = (
    OUTPUT_DIR
    / "temperature_autocorrelation.csv"
)

RAIN_TRANSITION_PATH = (
    OUTPUT_DIR
    / "rain_transition_probabilities.csv"
)

HUMIDITY_LEAD_PATH = (
    OUTPUT_DIR
    / "humidity_future_rain.csv"
)


EXPECTED_ROWS = 753_888

AUTOCORRELATION_LAGS = (
    1,
    3,
    6,
    12,
    24,
    48,
    72,
    168,
    336,
    720,
)

RAIN_THRESHOLDS = (
    ("gt_0", 0.0, "gt"),
    ("ge_0_1", 0.1, "ge"),
    ("ge_0_5", 0.5, "ge"),
    ("ge_1_0", 1.0, "ge"),
)

FUTURE_RAIN_LEADS = (
    0,
    1,
    3,
    6,
    12,
    24,
)


def autocorrelation_table(raw, residual):
    """Comparar memoria antes y despues de descomponer."""

    rows = []

    for lag in AUTOCORRELATION_LAGS:
        rows.append(
            {
                "lag_hours": lag,
                "temperature_raw": float(
                    raw.autocorr(lag=lag)
                ),
                "temperature_residual": float(
                    residual.autocorr(lag=lag)
                ),
            }
        )

    return pd.DataFrame(rows)


def rain_state(precipitation, threshold, operator):
    """Crear estado binario seco/lluvia."""

    if operator == "gt":
        return precipitation > threshold

    if operator == "ge":
        return precipitation >= threshold

    raise ValueError(
        f"Operador desconocido: {operator}"
    )


def transition_statistics(
    precipitation,
    label,
    threshold,
    operator,
):
    """Estimar matriz empirica de transicion a una hora."""

    state = rain_state(
        precipitation,
        threshold,
        operator,
    ).astype(np.int8)

    current = state.iloc[:-1].to_numpy()
    following = state.iloc[1:].to_numpy()

    n00 = int(
        np.sum(
            (current == 0)
            & (following == 0)
        )
    )

    n01 = int(
        np.sum(
            (current == 0)
            & (following == 1)
        )
    )

    n10 = int(
        np.sum(
            (current == 1)
            & (following == 0)
        )
    )

    n11 = int(
        np.sum(
            (current == 1)
            & (following == 1)
        )
    )

    dry_total = n00 + n01
    wet_total = n10 + n11

    return {
        "threshold_label": label,
        "threshold_mm": threshold,
        "operator": operator,
        "dry_to_dry_count": n00,
        "dry_to_rain_count": n01,
        "rain_to_dry_count": n10,
        "rain_to_rain_count": n11,
        "p_dry_to_dry": n00 / dry_total,
        "p_dry_to_rain": n01 / dry_total,
        "p_rain_to_dry": n10 / wet_total,
        "p_rain_to_rain": n11 / wet_total,
        "wet_fraction": float(
            state.mean()
        ),
    }


def humidity_future_rain(
    humidity,
    precipitation,
):
    """Relacion lineal entre humedad y lluvia futura."""

    rain = (
        precipitation >= 0.1
    ).astype(float)

    rows = []

    for lead in FUTURE_RAIN_LEADS:

        if lead == 0:
            correlation = humidity.corr(rain)

        else:
            correlation = (
                humidity.iloc[:-lead]
                .reset_index(drop=True)
                .corr(
                    rain.iloc[lead:]
                    .reset_index(drop=True)
                )
            )

        rows.append(
            {
                "lead_hours": lead,
                "correlation_humidity_future_rain": (
                    float(correlation)
                ),
            }
        )

    return pd.DataFrame(rows)


def main():
    """Ejecutar los diagnosticos estocasticos."""

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "=== DIAGNOSTICOS ESTOCASTICOS ==="
    )

    df = pd.read_csv(
        DATA_PATH,
        parse_dates=["timestamp"],
    )

    if len(df) != EXPECTED_ROWS:
        raise ValueError(
            f"Se esperaban {EXPECTED_ROWS} filas "
            f"y se encontraron {len(df)}."
        )

    temperature = df["temperature_2m"]

    # -------------------------------------------------
    # 1. Tendencia lineal de largo plazo
    # -------------------------------------------------

    start_time = df["timestamp"].iloc[0]

    elapsed_years = (
        (
            df["timestamp"] - start_time
        ).dt.total_seconds()
        / (
            365.2425
            * 24
            * 60
            * 60
        )
    )

    slope_per_year, intercept = np.polyfit(
        elapsed_years.to_numpy(),
        temperature.to_numpy(),
        deg=1,
    )

    trend = (
        intercept
        + slope_per_year
        * elapsed_years
    )

    detrended = temperature - trend

    # -------------------------------------------------
    # 2. Climatologia mes-hora
    # -------------------------------------------------

    work = pd.DataFrame(
        {
            "month": df["timestamp"].dt.month,
            "hour": df["timestamp"].dt.hour,
            "detrended_temperature": detrended,
        }
    )

    climatology = (
        work.groupby(
            ["month", "hour"],
            as_index=False,
        )
        .agg(
            seasonal_component=(
                "detrended_temperature",
                "mean",
            )
        )
    )

    work = work.merge(
        climatology,
        on=["month", "hour"],
        how="left",
        validate="many_to_one",
    )

    residual = (
        work["detrended_temperature"]
        - work["seasonal_component"]
    )

    # -------------------------------------------------
    # 3. Autocorrelaciones
    # -------------------------------------------------

    autocorrelations = (
        autocorrelation_table(
            temperature,
            residual,
        )
    )

    # -------------------------------------------------
    # 4. Estados de lluvia y transiciones
    # -------------------------------------------------

    rain_rows = []

    for (
        label,
        threshold,
        operator,
    ) in RAIN_THRESHOLDS:

        rain_rows.append(
            transition_statistics(
                df["precipitation"],
                label,
                threshold,
                operator,
            )
        )

    rain_transitions = pd.DataFrame(
        rain_rows
    )

    # -------------------------------------------------
    # 5. Humedad actual frente a lluvia futura
    # -------------------------------------------------

    humidity_leads = humidity_future_rain(
        df["relative_humidity_2m"],
        df["precipitation"],
    )

    # -------------------------------------------------
    # 6. Guardar resultados
    # -------------------------------------------------

    climatology.to_csv(
        CLIMATOLOGY_PATH,
        index=False,
    )

    autocorrelations.to_csv(
        AUTOCORRELATION_PATH,
        index=False,
    )

    rain_transitions.to_csv(
        RAIN_TRANSITION_PATH,
        index=False,
    )

    humidity_leads.to_csv(
        HUMIDITY_LEAD_PATH,
        index=False,
    )

    summary = {
        "source": "Open-Meteo ERA5",
        "rows": int(len(df)),
        "temperature": {
            "linear_trend_c_per_year": (
                float(slope_per_year)
            ),
            "linear_trend_c_per_decade": (
                float(
                    slope_per_year * 10
                )
            ),
            "raw_std": float(
                temperature.std()
            ),
            "residual_mean": float(
                residual.mean()
            ),
            "residual_std": float(
                residual.std()
            ),
            "seasonal_component_min": float(
                climatology[
                    "seasonal_component"
                ].min()
            ),
            "seasonal_component_max": float(
                climatology[
                    "seasonal_component"
                ].max()
            ),
        },
        "autocorrelations": (
            autocorrelations.to_dict(
                orient="records"
            )
        ),
        "rain_transitions": (
            rain_transitions.to_dict(
                orient="records"
            )
        ),
        "humidity_future_rain": (
            humidity_leads.to_dict(
                orient="records"
            )
        ),
    }

    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # -------------------------------------------------
    # 7. Mostrar hallazgos
    # -------------------------------------------------

    print(
        "\n=== TENDENCIA DE TEMPERATURA ==="
    )

    print(
        "Pendiente lineal: "
        f"{slope_per_year:.6f} °C/año"
    )

    print(
        "Pendiente lineal: "
        f"{slope_per_year * 10:.4f} °C/década"
    )

    print(
        "Desviacion estandar temperatura original: "
        f"{temperature.std():.4f} °C"
    )

    print(
        "Desviacion estandar residual: "
        f"{residual.std():.4f} °C"
    )

    print(
        "\n=== MEMORIA DE TEMPERATURA ==="
    )

    print(
        autocorrelations.to_string(
            index=False
        )
    )

    print(
        "\n=== TRANSICIONES DE LLUVIA ==="
    )

    columns = [
        "threshold_label",
        "wet_fraction",
        "p_dry_to_rain",
        "p_rain_to_rain",
    ]

    print(
        rain_transitions[
            columns
        ].to_string(
            index=False
        )
    )

    print(
        "\n=== HUMEDAD Y LLUVIA FUTURA ==="
    )

    print(
        humidity_leads.to_string(
            index=False
        )
    )

    print(
        "\nResultados guardados en:"
    )

    for path in (
        SUMMARY_PATH,
        CLIMATOLOGY_PATH,
        AUTOCORRELATION_PATH,
        RAIN_TRANSITION_PATH,
        HUMIDITY_LEAD_PATH,
    ):
        print(path)


if __name__ == "__main__":
    main()
