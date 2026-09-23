"""Generar las cinco figuras finales de la Tarea 01."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT / "data"
ANALYSIS_DIR = DATA_DIR / "analysis"
PROCESSED_DIR = DATA_DIR / "processed"
FIGURES_DIR = ROOT / "figures"

FIGURES_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def save_figure(fig, filename):
    """Guardar una figura final."""

    path = FIGURES_DIR / filename

    fig.tight_layout()

    fig.savefig(
        path,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(fig)

    print(f"OK: {path}")


def figure_1_temperature_trend():
    """Temperatura media anual y tendencia lineal."""

    annual = pd.read_csv(
        ANALYSIS_DIR / "annual_summary.csv"
    )

    years = annual["year"].to_numpy()
    temperature = annual[
        "temperature_mean"
    ].to_numpy()

    slope, intercept = np.polyfit(
        years,
        temperature,
        deg=1,
    )

    fitted = (
        intercept
        + slope * years
    )

    fig, ax = plt.subplots(
        figsize=(10, 5.5)
    )

    ax.plot(
        years,
        temperature,
        linewidth=1.3,
        label="Temperatura media anual",
    )

    ax.plot(
        years,
        fitted,
        linestyle="--",
        linewidth=2,
        label=(
            "Tendencia lineal "
            f"({slope * 10:.3f} °C/década)"
        ),
    )

    ax.set_title(
        "Temperatura media anual según ERA5\n"
        "Celda representativa de San Gabriel, 1940–2025"
    )

    ax.set_xlabel("Año")
    ax.set_ylabel("Temperatura media (°C)")
    ax.grid(alpha=0.25)
    ax.legend()

    save_figure(
        fig,
        "01_temperatura_anual_tendencia.png",
    )


def figure_2_month_hour_climatology():
    """Climatología media de temperatura por mes y hora."""

    master = pd.read_csv(
        PROCESSED_DIR
        / "era5_master_1940_2025.csv",
        parse_dates=["timestamp"],
        usecols=[
            "timestamp",
            "temperature_2m",
        ],
    )

    master["month"] = (
        master["timestamp"].dt.month
    )

    master["hour"] = (
        master["timestamp"].dt.hour
    )

    climatology = (
        master.groupby(
            ["month", "hour"]
        )["temperature_2m"]
        .mean()
        .unstack("hour")
    )

    values = climatology.to_numpy()

    fig, ax = plt.subplots(
        figsize=(11, 5.8)
    )

    image = ax.imshow(
        values,
        aspect="auto",
        origin="lower",
    )

    ax.set_title(
        "Climatología horaria de temperatura según ERA5\n"
        "Celda representativa de San Gabriel, promedio 1940–2025"
    )

    ax.set_xlabel("Hora del día")
    ax.set_ylabel("Mes")

    ax.set_xticks(
        np.arange(0, 24, 2)
    )

    ax.set_xticklabels(
        np.arange(0, 24, 2)
    )

    ax.set_yticks(
        np.arange(12)
    )

    ax.set_yticklabels(
        [
            "Ene",
            "Feb",
            "Mar",
            "Abr",
            "May",
            "Jun",
            "Jul",
            "Ago",
            "Sep",
            "Oct",
            "Nov",
            "Dic",
        ]
    )

    colorbar = fig.colorbar(
        image,
        ax=ax,
    )

    colorbar.set_label(
        "Temperatura media (°C)"
    )

    save_figure(
        fig,
        "02_climatologia_mes_hora.png",
    )


def figure_3_forecast_horizons():
    """RMSE por horizonte y modelo."""

    metrics = pd.read_csv(
        ANALYSIS_DIR
        / "temperature_horizon_metrics.csv"
    )

    model_labels = {
        "persistence": "Persistencia",
        "daily_naive": "Misma hora del día anterior",
        "deterministic": "Tendencia + climatología",
        "direct_ar": "Autoregresivo",
    }

    fig, ax = plt.subplots(
        figsize=(9, 5.5)
    )

    for model, label in model_labels.items():

        subset = metrics[
            metrics["model"] == model
        ].sort_values(
            "horizon_hours"
        )

        ax.plot(
            subset["horizon_hours"],
            subset["rmse"],
            marker="o",
            linewidth=2,
            label=label,
        )

    ax.set_title(
        "Error de predicción de temperatura\n"
        "Evaluación temporal 2016–2025"
    )

    ax.set_xlabel(
        "Horizonte de predicción (horas)"
    )

    ax.set_ylabel(
        "RMSE (°C)"
    )

    ax.set_xticks(
        sorted(
            metrics[
                "horizon_hours"
            ].unique()
        )
    )

    ax.grid(alpha=0.25)
    ax.legend()

    save_figure(
        fig,
        "03_rmse_horizonte_prediccion.png",
    )


def figure_4_markov_transition():
    """Matriz de transición seco/lluvia."""

    transitions = pd.read_csv(
        ANALYSIS_DIR
        / "rain_transition_probabilities.csv"
    )

    row = transitions[
        transitions[
            "threshold_label"
        ] == "ge_0_1"
    ].iloc[0]

    matrix = np.array(
        [
            [
                row["p_dry_to_dry"],
                row["p_dry_to_rain"],
            ],
            [
                row["p_rain_to_dry"],
                row["p_rain_to_rain"],
            ],
        ]
    )

    fig, ax = plt.subplots(
        figsize=(6.5, 5.5)
    )

    image = ax.imshow(
        matrix,
        vmin=0,
        vmax=1,
    )

    states = [
        "Seco",
        "Lluvia",
    ]

    ax.set_xticks(
        [0, 1],
        labels=states,
    )

    ax.set_yticks(
        [0, 1],
        labels=states,
    )

    ax.set_xlabel(
        "Estado en la hora siguiente"
    )

    ax.set_ylabel(
        "Estado actual"
    )

    ax.set_title(
        "Probabilidades de transición de lluvia, 1940–2025\n"
        "Umbral: precipitación ≥ 0.1 mm/h"
    )

    for i in range(2):
        for j in range(2):

            text_color = (
                "black"
                if matrix[i, j] >= 0.5
                else "white"
            )

            ax.text(
                j,
                i,
                f"{matrix[i, j]:.3f}",
                ha="center",
                va="center",
                fontsize=13,
                color=text_color,
            )

    colorbar = fig.colorbar(
        image,
        ax=ax,
    )

    colorbar.set_label(
        "Probabilidad"
    )

    save_figure(
        fig,
        "04_matriz_transicion_lluvia.png",
    )


def figure_5_duration_dependence():
    """Probabilidad futura según duración del estado."""

    duration = pd.read_csv(
        ANALYSIS_DIR
        / "rain_duration_model_probabilities.csv"
    )

    transitions = pd.read_csv(
        ANALYSIS_DIR
        / "rain_transition_probabilities.csv"
    )

    markov = transitions[
        transitions["threshold_label"]
        == "ge_0_1"
    ].iloc[0]

    order = [
        "1",
        "2",
        "3",
        "4-6",
        "7-12",
        "13-24",
        "25-48",
        "49+",
    ]

    labels = {
        "dry": "Estado seco",
        "rain": "Estado lluvioso",
    }

    fig, ax = plt.subplots(
        figsize=(10, 5.5)
    )

    for state, label in labels.items():

        subset = (
            duration[
                duration["state"] == state
            ]
            .set_index(
                "duration_bin"
            )
            .loc[order]
            .reset_index()
        )

        ax.plot(
            np.arange(
                len(order)
            ),
            subset[
                "p_rain_next_hour"
            ],
            marker="o",
            linewidth=2,
            label=label,
        )

    ax.axhline(
        markov["p_dry_to_rain"],
        linestyle="--",
        linewidth=1.5,
        label="Markov-1: desde seco",
    )

    ax.axhline(
        markov["p_rain_to_rain"],
        linestyle="--",
        linewidth=1.5,
        label="Markov-1: desde lluvia",
    )

    ax.set_xticks(
        np.arange(
            len(order)
        )
    )

    ax.set_xticklabels(
        order
    )

    ax.set_ylim(
        0,
        1,
    )

    ax.set_xlabel(
        "Duración del estado actual (horas)"
    )

    ax.set_ylabel(
        "P(lluvia en la hora siguiente)"
    )

    ax.set_title(
        "Dependencia de la lluvia respecto a la duración del estado\n"
        "Modelo estimado con datos 1940–2015"
    )

    ax.grid(alpha=0.25)
    ax.legend()

    save_figure(
        fig,
        "05_probabilidad_lluvia_duracion.png",
    )


def main():
    """Generar todas las figuras finales."""

    print(
        "=== GENERANDO FIGURAS FINALES ==="
    )

    figure_1_temperature_trend()
    figure_2_month_hour_climatology()
    figure_3_forecast_horizons()
    figure_4_markov_transition()
    figure_5_duration_dependence()

    print(
        "\nFiguras generadas: 5"
    )


if __name__ == "__main__":
    main()






