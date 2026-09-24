from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "processed" / "era5_master_1940_2025.csv"
ANALYSIS_DIR = ROOT / "data" / "analysis"
FIGURES_DIR = ROOT / "figures"


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    y_true = y_true[mask]
    y_pred = y_pred[mask]

    error = y_true - y_pred

    mae = float(np.mean(np.abs(error)))
    rmse = float(np.sqrt(np.mean(error**2)))

    ss_res = float(np.sum(error**2))
    ss_tot = float(np.sum((y_true - np.mean(y_true))**2))
    r2 = float(1.0 - ss_res / ss_tot)

    return {
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
    }


def deterministic_components(
    train: pd.DataFrame,
    test: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict]:
    origin = train["timestamp"].iloc[0]

    train_hours = (
        (train["timestamp"] - origin).dt.total_seconds() / 3600.0
    ).to_numpy()

    test_hours = (
        (test["timestamp"] - origin).dt.total_seconds() / 3600.0
    ).to_numpy()

    y_train = train["temperature_2m"].to_numpy(dtype=float)
    y_test = test["temperature_2m"].to_numpy(dtype=float)

    slope, intercept = np.polyfit(train_hours, y_train, 1)

    trend_train = intercept + slope * train_hours
    trend_test = intercept + slope * test_hours

    train_aux = train[["timestamp"]].copy()
    train_aux["detrended"] = y_train - trend_train
    train_aux["month"] = train_aux["timestamp"].dt.month
    train_aux["hour"] = train_aux["timestamp"].dt.hour

    climatology = (
        train_aux.groupby(["month", "hour"])["detrended"]
        .mean()
        .to_dict()
    )

    def get_climatology(df: pd.DataFrame) -> np.ndarray:
        return np.array(
            [
                climatology[(month, hour)]
                for month, hour in zip(
                    df["timestamp"].dt.month,
                    df["timestamp"].dt.hour,
                )
            ],
            dtype=float,
        )

    clim_train = get_climatology(train)
    clim_test = get_climatology(test)

    deterministic_train = trend_train + clim_train
    deterministic_test = trend_test + clim_test

    residual_train = y_train - deterministic_train
    residual_test = y_test - deterministic_test

    info = {
        "trend_slope_per_hour": float(slope),
        "trend_intercept": float(intercept),
        "climatology": "month-hour",
    }

    return (
        deterministic_train,
        deterministic_test,
        residual_train,
        residual_test,
        info,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SARIMA benchmark for hourly temperature residuals."
    )

    parser.add_argument(
        "--fit-years",
        type=int,
        default=5,
        help=(
            "Number of final training years used to estimate SARIMA parameters. "
            "Use 0 for the complete 1940-2015 training residual series."
        ),
    )

    args = parser.parse_args()

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading master dataset...")
    df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    train = df[df["timestamp"] < "2016-01-01"].copy()
    test = df[df["timestamp"] >= "2016-01-01"].copy()

    print(f"Training observations: {len(train):,}")
    print(f"Test observations:     {len(test):,}")

    (
        deterministic_train,
        deterministic_test,
        residual_train,
        residual_test,
        deterministic_info,
    ) = deterministic_components(train, test)

    if args.fit_years > 0:
        cutoff = pd.Timestamp("2016-01-01") - pd.DateOffset(
            years=args.fit_years
        )
        fit_mask = train["timestamp"] >= cutoff
    else:
        fit_mask = np.ones(len(train), dtype=bool)

    fit_residual = pd.Series(
        residual_train[fit_mask],
        dtype=float,
    ).reset_index(drop=True)

    print()
    print("Fitting SARIMA...")
    print("Order:          (2, 0, 1)")
    print("Seasonal order: (1, 0, 1, 24)")
    print(f"Fit observations: {len(fit_residual):,}")

    model = SARIMAX(
        fit_residual,
        order=(2, 0, 1),
        seasonal_order=(1, 0, 1, 24),
        trend="n",
        enforce_stationarity=False,
        enforce_invertibility=False,
    )

    result = model.fit(
        disp=False,
        maxiter=50,
    )

    print("SARIMA fit completed.")
    print(f"AIC: {result.aic:.3f}")
    print(f"BIC: {result.bic:.3f}")

    test_residual_series = pd.Series(
        residual_test,
        index=pd.RangeIndex(
            start=len(fit_residual),
            stop=len(fit_residual) + len(residual_test),
        ),
        dtype=float,
    )

    combined_result = result.append(
        test_residual_series,
        refit=False,
    )

    start = len(fit_residual)
    end = start + len(test_residual_series) - 1

    residual_prediction = (
        combined_result.get_prediction(
            start=start,
            end=end,
            dynamic=False,
        )
        .predicted_mean
        .to_numpy()
    )

    sarima_prediction = deterministic_test + residual_prediction

    y_train = train["temperature_2m"].to_numpy(dtype=float)
    y_test = test["temperature_2m"].to_numpy(dtype=float)

    persistence_prediction = np.concatenate(
        ([y_train[-1]], y_test[:-1])
    )

    rows = []

    for name, prediction in [
        ("persistence", persistence_prediction),
        ("deterministic", deterministic_test),
        ("sarima", sarima_prediction),
    ]:
        row = {"model": name}
        row.update(metrics(y_test, prediction))
        rows.append(row)

    metrics_df = pd.DataFrame(rows)

    metrics_path = ANALYSIS_DIR / "sarima_temperature_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False)

    summary = {
        "dataset": str(DATA_PATH.relative_to(ROOT)),
        "target": "temperature_2m",
        "train_start": str(train["timestamp"].min()),
        "train_end": str(train["timestamp"].max()),
        "test_start": str(test["timestamp"].min()),
        "test_end": str(test["timestamp"].max()),
        "sarima": {
            "order": [2, 0, 1],
            "seasonal_order": [1, 0, 1, 24],
            "fit_years": args.fit_years,
            "fit_observations": int(len(fit_residual)),
            "aic": float(result.aic),
            "bic": float(result.bic),
            "interpretation": (
                "SARIMA is applied to residual temperature after removing "
                "linear trend and month-hour climatology."
            ),
        },
        "deterministic_component": deterministic_info,
        "metrics": rows,
    }

    summary_path = ANALYSIS_DIR / "sarima_temperature_summary.json"

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # One-week visualization for presentation.
    sample_hours = min(168, len(test))

    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(
        test["timestamp"].iloc[:sample_hours],
        y_test[:sample_hours],
        label="Observed",
    )

    ax.plot(
        test["timestamp"].iloc[:sample_hours],
        persistence_prediction[:sample_hours],
        label="Persistence",
    )

    ax.plot(
        test["timestamp"].iloc[:sample_hours],
        sarima_prediction[:sample_hours],
        label="SARIMA",
    )

    ax.set_title(
        "Hourly temperature forecast: observed vs SARIMA"
    )
    ax.set_xlabel("Time")
    ax.set_ylabel("Temperature (°C)")
    ax.legend()

    fig.autofmt_xdate()
    fig.tight_layout()

    figure_path = FIGURES_DIR / "sarima_temperature_week.png"
    fig.savefig(figure_path, dpi=180)
    plt.close(fig)

    print()
    print("=" * 60)
    print("TEMPERATURE MODEL COMPARISON")
    print("=" * 60)
    print(metrics_df.to_string(index=False))
    print()
    print(f"Metrics: {metrics_path}")
    print(f"Summary: {summary_path}")
    print(f"Figure:  {figure_path}")


if __name__ == "__main__":
    main()
