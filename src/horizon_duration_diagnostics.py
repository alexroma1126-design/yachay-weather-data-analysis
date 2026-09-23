"""Horizontes de temperatura y diagnostico de duracion de lluvia."""

import json
import math
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
    / "horizon_duration_summary.json"
)

FORECAST_PATH = (
    OUTPUT_DIR
    / "temperature_horizon_metrics.csv"
)

SPELL_PATH = (
    OUTPUT_DIR
    / "rain_spell_summary.csv"
)

CONTINUATION_PATH = (
    OUTPUT_DIR
    / "rain_duration_continuation.csv"
)


SPLIT_DATE = pd.Timestamp("2016-01-01 00:00:00")

RAIN_THRESHOLD = 0.1

FORECAST_HORIZONS = (
    1,
    3,
    6,
    12,
    24,
)

HISTORY_LAGS = np.array(
    [
        0,
        1,
        2,
        5,
        11,
        23,
        47,
        167,
    ],
    dtype=int,
)

DURATION_CHECKS = (
    1,
    2,
    3,
    6,
    12,
    24,
    48,
)


def regression_metrics(y_true, y_pred):
    """Calcular metricas de regresion."""

    error = y_true - y_pred

    mae = np.mean(
        np.abs(error)
    )

    rmse = np.sqrt(
        np.mean(error ** 2)
    )

    denominator = np.sum(
        (
            y_true
            - np.mean(y_true)
        ) ** 2
    )

    r2 = 1.0 - (
        np.sum(error ** 2)
        / denominator
    )

    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "r2": float(r2),
    }


def build_deterministic_temperature(
    df,
    split_index,
):
    """Ajustar tendencia y climatologia solo con entrenamiento."""

    timestamp = df["timestamp"]

    temperature = df[
        "temperature_2m"
    ].to_numpy(
        dtype=float
    )

    start_time = timestamp.iloc[0]

    elapsed_years = (
        (
            timestamp
            - start_time
        )
        .dt.total_seconds()
        .to_numpy()
        / (
            365.2425
            * 24
            * 60
            * 60
        )
    )

    slope, intercept = np.polyfit(
        elapsed_years[
            :split_index
        ],
        temperature[
            :split_index
        ],
        deg=1,
    )

    trend = (
        intercept
        + slope * elapsed_years
    )

    detrended = (
        temperature - trend
    )

    climatology_frame = pd.DataFrame(
        {
            "month": timestamp.dt.month,
            "hour": timestamp.dt.hour,
            "detrended": detrended,
        }
    )

    climatology = (
        climatology_frame
        .iloc[:split_index]
        .groupby(
            ["month", "hour"]
        )["detrended"]
        .mean()
    )

    seasonal = np.array(
        [
            climatology.loc[
                (month, hour)
            ]
            for month, hour in zip(
                timestamp.dt.month,
                timestamp.dt.hour,
            )
        ],
        dtype=float,
    )

    deterministic = (
        trend + seasonal
    )

    residual = (
        temperature
        - deterministic
    )

    return (
        temperature,
        deterministic,
        residual,
        slope,
    )


def evaluate_temperature_horizon(
    temperature,
    deterministic,
    residual,
    split_index,
    horizon,
):
    """Ajustar un AR directo para un horizonte especifico."""

    max_history = int(
        HISTORY_LAGS.max()
    )

    train_origins = np.arange(
        max_history,
        split_index - horizon,
    )

    train_targets = (
        train_origins + horizon
    )

    x_train = np.column_stack(
        [
            residual[
                train_origins - lag
            ]
            for lag in HISTORY_LAGS
        ]
    )

    x_train = np.column_stack(
        [
            np.ones(
                len(x_train)
            ),
            x_train,
        ]
    )

    y_train = residual[
        train_targets
    ]

    coefficients, *_ = (
        np.linalg.lstsq(
            x_train,
            y_train,
            rcond=None,
        )
    )

    test_origins = np.arange(
        split_index,
        len(temperature) - horizon,
    )

    test_targets = (
        test_origins + horizon
    )

    x_test = np.column_stack(
        [
            residual[
                test_origins - lag
            ]
            for lag in HISTORY_LAGS
        ]
    )

    x_test = np.column_stack(
        [
            np.ones(
                len(x_test)
            ),
            x_test,
        ]
    )

    predicted_residual = (
        x_test @ coefficients
    )

    y_true = temperature[
        test_targets
    ]

    persistence = temperature[
        test_origins
    ]

    daily_naive = temperature[
        test_targets - 24
    ]

    deterministic_prediction = (
        deterministic[
            test_targets
        ]
    )

    autoregressive = (
        deterministic_prediction
        + predicted_residual
    )

    return {
        "persistence": (
            regression_metrics(
                y_true,
                persistence,
            )
        ),
        "daily_naive": (
            regression_metrics(
                y_true,
                daily_naive,
            )
        ),
        "deterministic": (
            regression_metrics(
                y_true,
                deterministic_prediction,
            )
        ),
        "direct_ar": (
            regression_metrics(
                y_true,
                autoregressive,
            )
        ),
    }


def extract_run_lengths(state):
    """Extraer duraciones consecutivas de estados 0 y 1."""

    state = np.asarray(
        state,
        dtype=np.int8,
    )

    runs = {
        0: [],
        1: [],
    }

    current_state = int(
        state[0]
    )

    current_length = 1

    for value in state[1:]:

        value = int(value)

        if value == current_state:
            current_length += 1

        else:
            runs[
                current_state
            ].append(
                current_length
            )

            current_state = value
            current_length = 1

    runs[
        current_state
    ].append(
        current_length
    )

    return {
        key: np.asarray(
            values,
            dtype=int,
        )
        for key, values
        in runs.items()
    }


def estimate_stay_probability(state, target_state):
    """Estimar P(S_t+1=s | S_t=s)."""

    current = state[:-1]
    following = state[1:]

    mask = (
        current == target_state
    )

    return float(
        np.mean(
            following[mask]
            == target_state
        )
    )


def geometric_quantile(
    stay_probability,
    probability,
):
    """Cuantil de duracion geometrica con soporte 1,2,..."""

    return int(
        math.ceil(
            math.log(
                1.0 - probability
            )
            / math.log(
                stay_probability
            )
        )
    )


def summarize_runs(
    runs,
    state_name,
    dataset_name,
    stay_probability,
):
    """Comparar duraciones empiricas y geometricas."""

    return {
        "dataset": dataset_name,
        "state": state_name,
        "episodes": int(
            len(runs)
        ),
        "empirical_mean_hours": float(
            np.mean(runs)
        ),
        "empirical_median_hours": float(
            np.median(runs)
        ),
        "empirical_p90_hours": float(
            np.quantile(
                runs,
                0.90,
            )
        ),
        "empirical_p95_hours": float(
            np.quantile(
                runs,
                0.95,
            )
        ),
        "empirical_max_hours": int(
            np.max(runs)
        ),
        "markov_stay_probability": float(
            stay_probability
        ),
        "geometric_mean_hours": float(
            1.0
            / (
                1.0
                - stay_probability
            )
        ),
        "geometric_median_hours": (
            geometric_quantile(
                stay_probability,
                0.50,
            )
        ),
        "geometric_p90_hours": (
            geometric_quantile(
                stay_probability,
                0.90,
            )
        ),
        "geometric_p95_hours": (
            geometric_quantile(
                stay_probability,
                0.95,
            )
        ),
    }


def continuation_table(
    runs,
    state_name,
    stay_probability,
):
    """P(L >= d+1 | L >= d) para distintas duraciones."""

    rows = []

    for duration in DURATION_CHECKS:

        survived = np.sum(
            runs >= duration
        )

        continued = np.sum(
            runs >= duration + 1
        )

        if survived == 0:
            empirical = np.nan
        else:
            empirical = (
                continued
                / survived
            )

        rows.append(
            {
                "state": state_name,
                "duration_hours": duration,
                "episodes_surviving": int(
                    survived
                ),
                "empirical_continue_probability": (
                    float(empirical)
                ),
                "markov_expected_probability": (
                    float(
                        stay_probability
                    )
                ),
                "difference": float(
                    empirical
                    - stay_probability
                ),
            }
        )

    return rows


def main():
    """Ejecutar ambos diagnosticos."""

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    df = pd.read_csv(
        DATA_PATH,
        parse_dates=["timestamp"],
    )

    split_matches = np.flatnonzero(
        df[
            "timestamp"
        ].to_numpy()
        >= np.datetime64(
            SPLIT_DATE
        )
    )

    if len(split_matches) == 0:
        raise ValueError(
            "No se encontro la fecha de corte."
        )

    split_index = int(
        split_matches[0]
    )

    print(
        "=== HORIZONTES DE TEMPERATURA ==="
    )

    (
        temperature,
        deterministic,
        residual,
        slope,
    ) = build_deterministic_temperature(
        df,
        split_index,
    )

    forecast_rows = []

    temperature_results = {}

    for horizon in FORECAST_HORIZONS:

        results = (
            evaluate_temperature_horizon(
                temperature,
                deterministic,
                residual,
                split_index,
                horizon,
            )
        )

        temperature_results[
            str(horizon)
        ] = results

        print(
            f"\nHorizonte: {horizon} h"
        )

        for model, metrics in results.items():

            forecast_rows.append(
                {
                    "horizon_hours": horizon,
                    "model": model,
                    **metrics,
                }
            )

            print(
                f"{model:14s} "
                f"MAE={metrics['mae']:.4f} "
                f"RMSE={metrics['rmse']:.4f} "
                f"R2={metrics['r2']:.4f}"
            )

    forecast_df = pd.DataFrame(
        forecast_rows
    )

    forecast_df.to_csv(
        FORECAST_PATH,
        index=False,
    )

    print(
        "\n=== DURACION DE ESTADOS DE LLUVIA ==="
    )

    rain_state = (
        df[
            "precipitation"
        ].to_numpy(
            dtype=float
        )
        >= RAIN_THRESHOLD
    ).astype(
        np.int8
    )

    train_state = rain_state[
        :split_index
    ]

    test_state = rain_state[
        split_index:
    ]

    dry_stay = (
        estimate_stay_probability(
            train_state,
            0,
        )
    )

    rain_stay = (
        estimate_stay_probability(
            train_state,
            1,
        )
    )

    train_runs = extract_run_lengths(
        train_state
    )

    test_runs = extract_run_lengths(
        test_state
    )

    spell_rows = []

    for (
        state_value,
        state_name,
        stay_probability,
    ) in (
        (
            0,
            "dry",
            dry_stay,
        ),
        (
            1,
            "rain",
            rain_stay,
        ),
    ):

        for dataset_name, runs in (
            (
                "train",
                train_runs[
                    state_value
                ],
            ),
            (
                "test",
                test_runs[
                    state_value
                ],
            ),
        ):

            summary = summarize_runs(
                runs,
                state_name,
                dataset_name,
                stay_probability,
            )

            spell_rows.append(
                summary
            )

            if dataset_name == "test":

                print(
                    f"\nEstado: {state_name}"
                )

                print(
                    "Media empirica: "
                    f"{summary['empirical_mean_hours']:.3f} h"
                )

                print(
                    "Media geometrica esperada: "
                    f"{summary['geometric_mean_hours']:.3f} h"
                )

                print(
                    "Mediana empirica: "
                    f"{summary['empirical_median_hours']:.1f} h"
                )

                print(
                    "P95 empirico: "
                    f"{summary['empirical_p95_hours']:.1f} h"
                )

                print(
                    "Maximo observado: "
                    f"{summary['empirical_max_hours']} h"
                )

    spell_df = pd.DataFrame(
        spell_rows
    )

    spell_df.to_csv(
        SPELL_PATH,
        index=False,
    )

    continuation_rows = []

    for (
        state_value,
        state_name,
        stay_probability,
    ) in (
        (
            0,
            "dry",
            dry_stay,
        ),
        (
            1,
            "rain",
            rain_stay,
        ),
    ):

        continuation_rows.extend(
            continuation_table(
                test_runs[
                    state_value
                ],
                state_name,
                stay_probability,
            )
        )

    continuation_df = pd.DataFrame(
        continuation_rows
    )

    continuation_df.to_csv(
        CONTINUATION_PATH,
        index=False,
    )

    print(
        "\n=== PROBABILIDAD DE CONTINUAR ==="
    )

    print(
        continuation_df.to_string(
            index=False
        )
    )

    summary = {
        "split_date": str(
            SPLIT_DATE
        ),
        "temperature": {
            "training_trend_c_per_decade": (
                float(
                    slope * 10
                )
            ),
            "horizons": (
                temperature_results
            ),
        },
        "rain": {
            "threshold_mm": (
                RAIN_THRESHOLD
            ),
            "training_stay_probability": {
                "dry": dry_stay,
                "rain": rain_stay,
            },
            "spell_summaries": (
                spell_rows
            ),
            "continuation": (
                continuation_rows
            ),
        },
    }

    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        "\nResultados guardados en:"
    )

    print(SUMMARY_PATH)
    print(FORECAST_PATH)
    print(SPELL_PATH)
    print(CONTINUATION_PATH)


if __name__ == "__main__":
    main()
