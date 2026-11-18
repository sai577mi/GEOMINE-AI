"""Sanity tests for the Python engine.   Run:  pytest -q"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

APP = Path(__file__).resolve().parent.parent / "streamlit_app"
sys.path.insert(0, str(APP))
import engine as E  # noqa: E402


@pytest.fixture(scope="module")
def models():
    return E.Models(str(APP))


def fresh_mine(models, seed=1, ticks=30):
    a, d, l = models.seed_hist
    mine = E.MineSim("test", seed, a, d, l)
    for _ in range(ticks):
        mine.tick()
    return mine


def test_storm_raises_risk(models):
    today = pd.Timestamp("2026-11-15")
    mine = fresh_mine(models)
    calm = E.evaluate(models, mine, E.simulated_forecast(today), today)
    storm = E.evaluate(models, mine, E.apply_storm(E.simulated_forecast(today), 90, today), today)
    assert storm["prob"] > calm["prob"]
    assert storm["level"] == "High"


def test_actions_never_hurt_and_respect_budget(models):
    today = pd.Timestamp("2026-11-15")
    mine = fresh_mine(models)
    r = E.evaluate(models, mine, E.apply_storm(E.simulated_forecast(today), 90, today), today)
    assert r["ach_after"] >= r["ach_before"]
    assert r["cost"] <= 3.0 + 1e-9


def test_failed_drill_is_seen(models):
    mine = fresh_mine(models)
    before = mine.snapshot()["drills_available"]
    assert mine.force_failure("drill") is not None
    assert mine.snapshot()["drills_available"] == before - 1


def test_open_meteo_parser_handles_missing_values():
    data = {"daily": {"time": ["2026-11-13", "2026-11-14"], "precipitation_sum": [1.5, None]}}
    df = E.parse_open_meteo(data)
    assert df.rain_mm.tolist() == [1.5, 0.0]


def test_reserve_model_is_reasonable():
    rm = E.fit_reserve(E.base_collars(30))
    assert rm.holdout_rmse < 3.0
    tn = E.tonnage(rm, 28)
    assert abs(tn["est"] - tn["truth"]) / tn["truth"] < 0.15
