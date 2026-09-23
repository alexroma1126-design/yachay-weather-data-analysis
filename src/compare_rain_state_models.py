"""Comparacion de modelos estocasticos para ocurrencia de lluvia."""

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
    / "rain_state_model_comparison.json"
)

METRICS_PATH = (
    OUTPUT_DIR
    / "rain_state_model_metrics.csv"
)

DURATION_PATH = (
    OUTPUT_DIR
    / "rain_duration_model_probabilities.csv"
)


SPLIT_DATE = pd.Timestamp("2016-01-01 00:00:00")
RAIN_THRESHOLD = 0.1


DURATION_BINS = (
    ("1", 1, 1),
    ("2", 2, 2),
    ("3", 3, 3),
    ("4-6", 4, 6),
    ("7-12", 7, 12),
    ("13-24", 13, 24),
    ("25-48", 25, 48),
    ("49+", 49, None),
)


def classification_metrics(y_true, probability):
    """Evaluar pronosticos probabilisticos binarios."""

    y_true = np.asarray(
        y_true,
        dtype=float,
    )

    probability = np.asarray(
        probability,
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

    predicted = (
        probability >= 0.5
    ).astype(int)

    accuracy = np.mean(
        predicted == y_true
    )

    return {
        "brier": float(brier),
        "log_loss": float(log_loss),
        "accuracy": float(accuracy),
    }


def current_durations(state):
    """Duracion consecutiva del estado actual en cada instante."""

    state = np.asarray(
        state,
        dtype=np.int8,
    )

    durations = np.ones(
        len(state),
        dtype=int,
    )

    for index in range(
        1,
        len(state),
    ):
        if state[index] == state[index - 1]:
            durations[index] = (
                durations[index - 1] + 1
            )

    return durations


def duration_bin_label(duration):
    """Asignar una duracion a un intervalo."""

    for label, minimum, maximum in DURATION_BINS:

        if duration < minimum:
            continue

        if maximum is None:
            return label

        if duration <= maximum:
            return label

    raise ValueError(
        f"Duracion fuera de rango: {duration}"
    )


def fit_order1(state):
    """P(lluvia siguiente | estado actual)."""

    current = state[:-1]
    target = state[1:]

    probabilities = {}

    for current_state in (0, 1):

        mask = (
            current == current_state
        )

        probabilities[current_state] = float(
            target[mask].mean()
        )

    return probabilities


def fit_order2(state):
    """P(lluvia siguiente | dos estados previos)."""

    previous = state[:-2]
    current = state[1:-1]
    target = state[2:]

    probabilities = {}

    for previous_state in (0, 1):
        for current_state in (0, 1):

            mask = (
                (previous == previous_state)
                & (current == current_state)
            )

            probabilities[
                (
                    previous_state,
                    current_state,
                )
            ] = float(
                target[mask].mean()
            )

    return probabilities


def fit_duration_model(
    state,
    durations,
    order1_probabilities,
):
    """P(lluvia siguiente | estado actual, duracion actual)."""

    current = state[:-1]
    target = state[1:]
    current_duration = durations[:-1]

    rows = []
    probabilities = {}

    for state_value in (0, 1):

        for label, minimum, maximum in DURATION_BINS:

            mask = (
                current == state_value
            )

            mask &= (
                current_duration >= minimum
            )

            if maximum is not None:
                mask &= (
                    current_duration <= maximum
                )

            count = int(
                mask.sum()
            )

            if count == 0:
                probability = (
                    order1_probabilities[
                        state_value
                    ]
                )

            else:
                probability = float(
                    target[mask].mean()
                )

            probabilities[
                (
                    state_value,
                    label,
                )
            ] = probability

            rows.append(
                {
                    "state": (
                        "rain"
                        if state_value == 1
                        else "dry"
                    ),
                    "duration_bin": label,
                    "train_examples": count,
                    "p_rain_next_hour": (
                        probability
                    ),
                }
            )

    return probabilities, rows


def main():
    """Comparar modelos en periodo futuro."""

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "=== MODELOS DE ESTADO DE LLUVIA ==="
    )

    df = pd.read_csv(
        DATA_PATH,
        parse_dates=["timestamp"],
    )

    state = (
        df[
            "precipitation"
        ].to_numpy(
            dtype=float
        )
        >= RAIN_THRESHOLD
    ).astype(
        np.int8
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
            "No se encontro fecha de corte."
        )

    split_index = int(
        split_matches[0]
    )

    train_state = state[
        :split_index
    ]

    train_durations = (
        current_durations(
            train_state
        )
    )

    all_durations = (
        current_durations(
            state
        )
    )

    baseline_probability = float(
        train_state.mean()
    )

    order1 = fit_order1(
        train_state
    )

    order2 = fit_order2(
        train_state
    )

    (
        duration_probabilities,
        duration_rows,
    ) = fit_duration_model(
        train_state,
        train_durations,
        order1,
    )

    # Pronosticos rolling de una hora.
    # El origen esta dentro del periodo de prueba
    # y el objetivo es la hora siguiente.

    origins = np.arange(
        split_index,
        len(state) - 1,
    )

    targets = origins + 1

    y_true = state[
        targets
    ]

    baseline_prediction = np.full(
        len(origins),
        baseline_probability,
    )

    order1_prediction = np.array(
        [
            order1[
                int(state[index])
            ]
            for index in origins
        ],
        dtype=float,
    )

    order2_prediction = np.array(
        [
            order2[
                (
                    int(state[index - 1]),
                    int(state[index]),
                )
            ]
            for index in origins
        ],
        dtype=float,
    )

    duration_prediction = np.array(
        [
            duration_probabilities[
                (
                    int(state[index]),
                    duration_bin_label(
                        int(
                            all_durations[
                                index
                            ]
                        )
                    ),
                )
            ]
            for index in origins
        ],
        dtype=float,
    )

    models = {
        "baseline": baseline_prediction,
        "markov_order1": order1_prediction,
        "markov_order2": order2_prediction,
        "duration_model": duration_prediction,
    }

    metric_rows = []

    print(
        "\n=== RESULTADOS EN 2016-2025 ==="
    )

    for model_name, prediction in models.items():

        metrics = classification_metrics(
            y_true,
            prediction,
        )

        metric_rows.append(
            {
                "model": model_name,
                **metrics,
            }
        )

        print(
            f"{model_name:16s} "
            f"Brier={metrics['brier']:.6f} "
            f"LogLoss={metrics['log_loss']:.6f} "
            f"Accuracy={metrics['accuracy']:.6f}"
        )

    metrics_df = pd.DataFrame(
        metric_rows
    )

    metrics_df.to_csv(
        METRICS_PATH,
        index=False,
    )

    duration_df = pd.DataFrame(
        duration_rows
    )

    duration_df.to_csv(
        DURATION_PATH,
        index=False,
    )

    print(
        "\n=== PROBABILIDADES POR DURACION ==="
    )

    print(
        duration_df.to_string(
            index=False
        )
    )

    metrics_lookup = {
        row["model"]: row
        for row in metric_rows
    }

    order1_brier = (
        metrics_lookup[
            "markov_order1"
        ]["brier"]
    )

    duration_brier = (
        metrics_lookup[
            "duration_model"
        ]["brier"]
    )

    relative_brier_improvement = (
        (
            order1_brier
            - duration_brier
        )
        / order1_brier
    )

    summary = {
        "train_start": str(
            df[
                "timestamp"
            ].iloc[0]
        ),
        "train_end": str(
            df[
                "timestamp"
            ].iloc[
                split_index - 1
            ]
        ),
        "test_start": str(
            df[
                "timestamp"
            ].iloc[
                split_index
            ]
        ),
        "test_end": str(
            df[
                "timestamp"
            ].iloc[-1]
        ),
        "rain_threshold_mm": (
            RAIN_THRESHOLD
        ),
        "baseline_probability": (
            baseline_probability
        ),
        "markov_order1": {
            "p_rain_given_dry": (
                order1[0]
            ),
            "p_rain_given_rain": (
                order1[1]
            ),
        },
        "metrics": metric_rows,
        "duration_model_brier_improvement_vs_order1": float(
            relative_brier_improvement
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

    print(
        "\n=== MEJORA DEL MODELO DE DURACION ==="
    )

    print(
        "Mejora relativa Brier vs Markov orden 1: "
        f"{100 * relative_brier_improvement:.3f} %"
    )

    print(
        "\nResultados guardados en:"
    )

    print(SUMMARY_PATH)
    print(METRICS_PATH)
    print(DURATION_PATH)


if __name__ == "__main__":
    main()
