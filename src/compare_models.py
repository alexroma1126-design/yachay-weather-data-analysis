"""Comparacion predictiva inicial: autoregresion y cadenas de Markov."""

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
    / "model_comparison_summary.json"
)

METRICS_PATH = (
    OUTPUT_DIR
    / "forecast_metrics.csv"
)

MARKOV2_PATH = (
    OUTPUT_DIR
    / "markov_order2_probabilities.csv"
)

SPLIT_DATE = pd.Timestamp("2016-01-01 00:00:00")

RAIN_THRESHOLD = 0.1

AR_LAGS = np.array(
    [1, 2, 3, 6, 12, 24, 48, 168],
    dtype=int,
)


def regression_metrics(y_true, y_pred):
    """MAE, RMSE y R2."""

    error = y_true - y_pred

    mae = np.mean(np.abs(error))
    rmse = np.sqrt(np.mean(error ** 2))

    denominator = np.sum(
        (y_true - np.mean(y_true)) ** 2
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


def classification_metrics(y_true, probability):
    """Brier, log-loss y accuracy."""

    probability = np.asarray(
        probability,
        dtype=float,
    )

    y_true = np.asarray(
        y_true,
        dtype=float,
    )

    clipped = np.clip(
        probability,
        1e-12,
        1.0 - 1e-12,
    )

    brier = np.mean(
        (probability - y_true) ** 2
    )

    log_loss = -np.mean(
        y_true * np.log(clipped)
        + (1.0 - y_true)
        * np.log(1.0 - clipped)
    )

    predicted_state = (
        probability >= 0.5
    ).astype(int)

    accuracy = np.mean(
        predicted_state == y_true
    )

    return {
        "brier": float(brier),
        "log_loss": float(log_loss),
        "accuracy": float(accuracy),
    }


def fit_temperature_model(df, split_index):
    """Ajustar tendencia, climatologia y autoregresion."""

    timestamp = df["timestamp"]
    temperature = df[
        "temperature_2m"
    ].to_numpy(dtype=float)

    start_time = timestamp.iloc[0]

    elapsed_years = (
        (
            timestamp - start_time
        ).dt.total_seconds().to_numpy()
        / (
            365.2425
            * 24
            * 60
            * 60
        )
    )

    train_years = elapsed_years[
        :split_index
    ]

    train_temperature = temperature[
        :split_index
    ]

    slope, intercept = np.polyfit(
        train_years,
        train_temperature,
        deg=1,
    )

    trend = (
        intercept
        + slope * elapsed_years
    )

    detrended = temperature - trend

    climatology_frame = pd.DataFrame(
        {
            "month": timestamp.dt.month,
            "hour": timestamp.dt.hour,
            "detrended": detrended,
        }
    )

    train_climatology = (
        climatology_frame.iloc[
            :split_index
        ]
        .groupby(
            ["month", "hour"]
        )["detrended"]
        .mean()
    )

    seasonal = np.array(
        [
            train_climatology.loc[
                (month, hour)
            ]
            for month, hour in zip(
                timestamp.dt.month,
                timestamp.dt.hour,
            )
        ],
        dtype=float,
    )

    deterministic = trend + seasonal

    residual = (
        temperature - deterministic
    )

    max_lag = int(
        AR_LAGS.max()
    )

    train_targets = np.arange(
        max_lag,
        split_index,
    )

    x_train = np.column_stack(
        [
            residual[
                train_targets - lag
            ]
            for lag in AR_LAGS
        ]
    )

    y_train = residual[
        train_targets
    ]

    x_train = np.column_stack(
        [
            np.ones(len(x_train)),
            x_train,
        ]
    )

    coefficients, *_ = np.linalg.lstsq(
        x_train,
        y_train,
        rcond=None,
    )

    test_targets = np.arange(
        split_index,
        len(df),
    )

    x_test = np.column_stack(
        [
            residual[
                test_targets - lag
            ]
            for lag in AR_LAGS
        ]
    )

    x_test = np.column_stack(
        [
            np.ones(len(x_test)),
            x_test,
        ]
    )

    predicted_residual = (
        x_test @ coefficients
    )

    y_true = temperature[
        test_targets
    ]

    prediction_deterministic = (
        deterministic[
            test_targets
        ]
    )

    prediction_ar = (
        prediction_deterministic
        + predicted_residual
    )

    prediction_persistence = (
        temperature[
            test_targets - 1
        ]
    )

    results = {
        "persistence": regression_metrics(
            y_true,
            prediction_persistence,
        ),
        "deterministic": regression_metrics(
            y_true,
            prediction_deterministic,
        ),
        "autoregressive": regression_metrics(
            y_true,
            prediction_ar,
        ),
    }

    model_info = {
        "trend_c_per_year": float(slope),
        "trend_c_per_decade": float(
            slope * 10
        ),
        "ar_lags_hours": (
            AR_LAGS.tolist()
        ),
        "ar_coefficients": [
            float(value)
            for value in coefficients
        ],
    }

    return results, model_info


def estimate_markov_order1(train_state):
    """Probabilidades de Markov de primer orden."""

    previous = train_state[:-1]
    current = train_state[1:]

    probabilities = {}

    for state in (0, 1):
        mask = previous == state

        probabilities[state] = float(
            current[mask].mean()
        )

    return probabilities


def estimate_markov_order2(train_state):
    """Probabilidades de Markov de segundo orden."""

    first = train_state[:-2]
    second = train_state[1:-1]
    target = train_state[2:]

    probabilities = {}

    for state1 in (0, 1):
        for state2 in (0, 1):

            mask = (
                (first == state1)
                & (second == state2)
            )

            probabilities[
                (state1, state2)
            ] = float(
                target[mask].mean()
            )

    return probabilities


def evaluate_rain_models(
    precipitation,
    split_index,
):
    """Comparar baseline y Markov orden 1/2."""

    state = (
        precipitation >= RAIN_THRESHOLD
    ).astype(int)

    train_state = state[
        :split_index
    ]

    baseline_probability = float(
        train_state.mean()
    )

    order1 = estimate_markov_order1(
        train_state
    )

    order2 = estimate_markov_order2(
        train_state
    )

    targets = np.arange(
        split_index,
        len(state),
    )

    y_true = state[
        targets
    ]

    baseline_prediction = np.full(
        len(targets),
        baseline_probability,
    )

    markov1_prediction = np.array(
        [
            order1[
                int(state[index - 1])
            ]
            for index in targets
        ]
    )

    markov2_prediction = np.array(
        [
            order2[
                (
                    int(state[index - 2]),
                    int(state[index - 1]),
                )
            ]
            for index in targets
        ]
    )

    results = {
        "rain_baseline": (
            classification_metrics(
                y_true,
                baseline_prediction,
            )
        ),
        "markov_order1": (
            classification_metrics(
                y_true,
                markov1_prediction,
            )
        ),
        "markov_order2": (
            classification_metrics(
                y_true,
                markov2_prediction,
            )
        ),
    }

    return (
        results,
        baseline_probability,
        order1,
        order2,
    )


def main():
    """Ejecutar comparacion temporal."""

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "=== COMPARACION DE MODELOS ==="
    )

    df = pd.read_csv(
        DATA_PATH,
        parse_dates=["timestamp"],
    )

    split_matches = np.flatnonzero(
        df["timestamp"].to_numpy()
        >= np.datetime64(SPLIT_DATE)
    )

    if len(split_matches) == 0:
        raise ValueError(
            "No se encontro la fecha de corte."
        )

    split_index = int(
        split_matches[0]
    )

    print(
        "Entrenamiento: "
        f"{df['timestamp'].iloc[0]} "
        "a "
        f"{df['timestamp'].iloc[split_index - 1]}"
    )

    print(
        "Prueba: "
        f"{df['timestamp'].iloc[split_index]} "
        "a "
        f"{df['timestamp'].iloc[-1]}"
    )

    temperature_results, model_info = (
        fit_temperature_model(
            df,
            split_index,
        )
    )

    (
        rain_results,
        baseline_probability,
        order1,
        order2,
    ) = evaluate_rain_models(
        df["precipitation"].to_numpy(
            dtype=float
        ),
        split_index,
    )

    metric_rows = []

    for model, metrics in (
        temperature_results.items()
    ):
        metric_rows.append(
            {
                "task": "temperature_1h",
                "model": model,
                **metrics,
            }
        )

    for model, metrics in (
        rain_results.items()
    ):
        metric_rows.append(
            {
                "task": "rain_1h",
                "model": model,
                **metrics,
            }
        )

    metrics_df = pd.DataFrame(
        metric_rows
    )

    markov2_df = pd.DataFrame(
        [
            {
                "state_t_minus_1": state1,
                "state_t": state2,
                "p_rain_next_hour": (
                    probability
                ),
            }
            for (
                state1,
                state2
            ), probability in order2.items()
        ]
    )

    metrics_df.to_csv(
        METRICS_PATH,
        index=False,
    )

    markov2_df.to_csv(
        MARKOV2_PATH,
        index=False,
    )

    summary = {
        "split_date": str(
            SPLIT_DATE
        ),
        "train_start": str(
            df["timestamp"].iloc[0]
        ),
        "train_end": str(
            df["timestamp"].iloc[
                split_index - 1
            ]
        ),
        "test_start": str(
            df["timestamp"].iloc[
                split_index
            ]
        ),
        "test_end": str(
            df["timestamp"].iloc[-1]
        ),
        "temperature": {
            "model_info": model_info,
            "metrics": (
                temperature_results
            ),
        },
        "rain": {
            "threshold_mm": (
                RAIN_THRESHOLD
            ),
            "baseline_probability": (
                baseline_probability
            ),
            "order1_probability_rain": {
                "given_dry": order1[0],
                "given_rain": order1[1],
            },
            "order2_probability_rain": {
                f"{a}{b}": probability
                for (
                    a,
                    b
                ), probability
                in order2.items()
            },
            "metrics": rain_results,
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
        "\n=== TEMPERATURA: PRONOSTICO 1 HORA ==="
    )

    for model, metrics in (
        temperature_results.items()
    ):
        print(
            f"{model:16s} "
            f"MAE={metrics['mae']:.4f} "
            f"RMSE={metrics['rmse']:.4f} "
            f"R2={metrics['r2']:.4f}"
        )

    print(
        "\n=== LLUVIA: PRONOSTICO 1 HORA ==="
    )

    for model, metrics in (
        rain_results.items()
    ):
        print(
            f"{model:16s} "
            f"Brier={metrics['brier']:.4f} "
            f"LogLoss={metrics['log_loss']:.4f} "
            f"Accuracy={metrics['accuracy']:.4f}"
        )

    print(
        "\n=== MARKOV ORDEN 1 ==="
    )

    print(
        "P(lluvia siguiente | seco)   = "
        f"{order1[0]:.6f}"
    )

    print(
        "P(lluvia siguiente | lluvia) = "
        f"{order1[1]:.6f}"
    )

    print(
        "\n=== MARKOV ORDEN 2 ==="
    )

    for key in sorted(order2):
        print(
            f"P(lluvia siguiente | {key[0]}{key[1]}) "
            f"= {order2[key]:.6f}"
        )

    print(
        "\nResultados guardados en:"
    )

    print(SUMMARY_PATH)
    print(METRICS_PATH)
    print(MARKOV2_PATH)


if __name__ == "__main__":
    main()
