"""Does the UPT Google Ads campaign being ON move organic GSC performance for "personality test"?

Design: the "[ACQ] Personality Test - UPT" PMax campaign switched on and off several times
inside GSC's 16-month window, and its search-term insights show it bought ads on the exact
query "personality test". So each switch is a natural experiment. Two estimators:

1. `switch_effects`: for every ON/OFF switch, mean outcome in the `window` days after vs
   before, signed so a positive number always means "ads ON is higher".
2. `regress_on_flag`: daily OLS of the outcome on the ON flag, a control series (site queries
   unrelated to personality tests, same device) and day-of-week, with Newey-West errors
   because daily GSC series are strongly autocorrelated.

Everything is pure: frames in, numbers out. Oct 2025 - Mar 2026 desktop data is poisoned by a
Google SERP artifact (desktop impressions x15, CTR collapse), so the headline uses MOBILE.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

UPT_CAMPAIGN_ID = 21002171932
QUERY = "personality test"
MIN_SPEND = 1.0  # a day with < $1 spend counts as OFF
MAX_GAP_DAYS = 2  # OFF gaps this short (a paused day) are merged into the surrounding ON run


def on_flag(spend: pd.Series, start: str, end: str) -> pd.Series:
    """Daily 0/1 ON flag over [start, end] from a date-indexed spend series.

    Gaps of <= MAX_GAP_DAYS OFF days between two ON days are filled in, so a one-day pause
    does not create two spurious switches.
    """
    idx = pd.date_range(start, end)
    s = spend.copy()
    s.index = pd.to_datetime(s.index)
    on = (s.groupby(level=0).sum().reindex(idx, fill_value=0) >= MIN_SPEND).astype(int)
    vals = on.to_numpy().copy()
    ons = np.flatnonzero(vals)
    for a, b in zip(ons[:-1], ons[1:]):
        if 1 < b - a <= MAX_GAP_DAYS + 1:
            vals[a:b] = 1
    return pd.Series(vals, index=idx, name="on")


def on_periods(spend: pd.Series, start: str, end: str) -> list[tuple[str, str]]:
    """Contiguous ON runs as (first_day, last_day) ISO strings."""
    on = on_flag(spend, start, end)
    runs, cur = [], None
    for d, v in on.items():
        if v and cur is None:
            cur = d
        if not v and cur is not None:
            runs.append((cur, d - pd.Timedelta(days=1)))
            cur = None
    if cur is not None:
        runs.append((cur, on.index[-1]))
    return [(a.date().isoformat(), b.date().isoformat()) for a, b in runs]


def switches(on: pd.Series) -> list[tuple[pd.Timestamp, int]]:
    """(first day of new state, +1 for OFF->ON / -1 for ON->OFF)."""
    d = on.diff()
    return [(ts, int(v)) for ts, v in d[d.fillna(0) != 0].items()]


def gsc_daily(gsc: pd.DataFrame, devices: list[str] | None = None) -> pd.DataFrame:
    """Collapse GSC rows (date[, device]) to one row per day.

    Position is impression-weighted across devices; ctr = clicks / impressions.
    """
    g = gsc if devices is None else gsc[gsc["device"].isin(devices)]
    g = g.assign(pos_x_imp=g["position"] * g["impressions"])
    out = g.groupby(pd.to_datetime(g["date"]))[["clicks", "impressions", "pos_x_imp"]].sum()
    out["position"] = out["pos_x_imp"] / out["impressions"].replace(0, np.nan)
    out["ctr"] = out["clicks"] / out["impressions"].replace(0, np.nan)
    return out.drop(columns="pos_x_imp")


def switch_effects(y: pd.Series, on: pd.Series, window: int = 14, min_days: int = 7) -> pd.DataFrame:
    """Before/after means around every switch, signed so positive = higher when ads are ON.

    `pct` compares on-side vs off-side as a percent of the off-side mean. Switches with fewer
    than `min_days` observed days on either side are dropped.
    """
    rows = []
    y = y.dropna()
    for ts, direction in switches(on):
        before = y[(y.index >= ts - pd.Timedelta(days=window)) & (y.index < ts)]
        after = y[(y.index >= ts) & (y.index < ts + pd.Timedelta(days=window))]
        if len(before) < min_days or len(after) < min_days:
            continue
        on_side, off_side = (after, before) if direction > 0 else (before, after)
        rows.append({
            "switch_date": ts.date().isoformat(),
            "direction": "OFF->ON" if direction > 0 else "ON->OFF",
            "before": before.mean(), "after": after.mean(),
            "on_minus_off": on_side.mean() - off_side.mean(),
            "pct": (on_side.mean() / off_side.mean() - 1) * 100 if off_side.mean() else np.nan,
            "n_before": len(before), "n_after": len(after),
        })
    return pd.DataFrame(rows)


def regress_on_flag(y: pd.Series, on: pd.Series, control: pd.Series | None = None,
                    hac_lags: int = 14) -> dict:
    """OLS y ~ on + control + day-of-week, Newey-West SEs. Returns the `on` coefficient."""
    df = pd.DataFrame({"y": y, "on": on}).dropna()
    x = df[["on"]].astype(float)
    if control is not None:
        x["control"] = control.reindex(df.index).astype(float)
    dow = pd.get_dummies(df.index.dayofweek, prefix="dow", drop_first=True).astype(float)
    dow.index = df.index
    x = sm.add_constant(x.join(dow), has_constant="add")
    ok = x.notna().all(axis=1)
    m = sm.OLS(df["y"][ok].astype(float), x[ok]).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})
    lo, hi = m.conf_int().loc["on"]
    return {"coef": float(m.params["on"]), "ci_low": float(lo), "ci_high": float(hi),
            "p_value": float(m.pvalues["on"]), "n": int(ok.sum())}


def sign_test_p(effects: pd.Series) -> float:
    """Two-sided exact sign test p-value for 'effects are centred on zero'."""
    from scipy.stats import binomtest
    e = effects.dropna()
    e = e[e != 0]
    if len(e) == 0:
        return float("nan")
    return float(binomtest(int((e > 0).sum()), len(e), 0.5).pvalue)


def shift_null(y: pd.Series, on: pd.Series, controls: pd.DataFrame | None = None,
               lag: int = 0, min_shift: int = 30) -> dict:
    """Circular-shift permutation test for the ON coefficient.

    Rotates the ON schedule by every offset of at least `min_shift` days and refits. Rotation
    keeps the schedule's block structure and the outcome's autocorrelation, so the null
    distribution reflects how big an "effect" an arbitrary on/off schedule of the same shape
    would show against the same slow-moving series. p = share of rotations at least as extreme.
    """
    def coef(flag):
        df = pd.DataFrame({"y": y, "on": flag.shift(lag)})
        if controls is not None:
            df = df.join(controls)
        df = df.dropna()
        x = sm.add_constant(df.drop(columns="y").astype(float), has_constant="add")
        return float(sm.OLS(df["y"].astype(float), x).fit().params["on"])

    on = on.reindex(y.index).fillna(0)
    real = coef(on)
    n = len(on)
    null = np.array([coef(pd.Series(np.roll(on.to_numpy(), k), index=on.index))
                     for k in range(min_shift, n - min_shift + 1)])
    return {"coef": real, "p_value": float((np.abs(null) >= abs(real) - 1e-12).mean()),
            "n_shifts": len(null), "null_sd": float(null.std())}


def period_means(y: pd.Series, on: pd.Series) -> pd.DataFrame:
    """Mean of y over each contiguous ON/OFF block, in order."""
    df = pd.DataFrame({"y": y, "on": on.reindex(y.index)}).dropna()
    block = (df["on"].diff() != 0).cumsum()
    out = df.groupby(block).agg(start=("y", lambda s: s.index.min().date().isoformat()),
                                end=("y", lambda s: s.index.max().date().isoformat()),
                                on=("on", "first"), mean=("y", "mean"), days=("y", "size"))
    return out.reset_index(drop=True)
