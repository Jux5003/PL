# -*- coding: utf-8 -*-
"""
최저 온도에서 3000시간까지의 부분 데이터로 50% 신장 시점(끝점) 예측.
- 방법 1: Arrhenius 외삽 (상위 3개 온도로 Ea 추정 후 최저온도 시간 예측)
- 방법 2: 최저온도에서 신장률-시간 곡선을 모델링 후 50% 도달 시간 외삽 (지수/멱함수 등)
"""

import numpy as np
from scipy.optimize import curve_fit
from .arrhenius import arrhenius_fit, predict_life_at_temperature


def _exponential_decay(t, a, k, c):
    """신장율 = a * exp(-k*t) + c  (t 증가 시 감소)"""
    return a * np.exp(-k * np.asarray(t)) + c


def _power_law(t, a, b, c):
    """신장율 = a * t^b + c"""
    t = np.asarray(t).astype(float)
    t = np.maximum(t, 1e-6)
    return a * np.power(t, b) + c


def _weibull_style(t, scale, shape, loc):
    """신장율 감쇠: 100 * exp(-((t-loc)/scale)^shape) 형태에 가깝게"""
    t = np.asarray(t).astype(float)
    return 100 * np.exp(-np.power(np.maximum(t - loc, 1e-6) / scale, shape))


def fit_degradation_curve(times_h: np.ndarray, elongation_percent: np.ndarray, model="exponential"):
    """
    신장율(%) vs 시간(h) 곡선 피팅.
    elongation_percent: 상대 신장율 (상온 대비 %, 50% 도달 시점을 구함)
    """
    t = np.asarray(times_h).ravel()
    y = np.asarray(elongation_percent).ravel()
    if len(t) != len(y) or len(t) < 3:
        return None, None

    if model == "exponential":
        # y = a*exp(-k*t) + c, 50% 도달: a*exp(-k*t)+c = 50 => t = -ln((50-c)/a)/k
        try:
            popt, _ = curve_fit(
                _exponential_decay,
                t,
                y,
                p0=[80, 1e-4, 20],
                bounds=([0, 1e-8, 0], [200, 1, 100]),
                maxfev=5000,
            )
            a, k, c = popt
            if k <= 0 or (50 - c) / a <= 0:
                return None, None
            t50 = -np.log((50 - c) / a) / k
            if t50 <= 0 or t50 > 1e7:
                return None, None
            return {"a": a, "k": k, "c": c, "t50_h": t50}, popt
        except Exception:
            return None, None

    if model == "power":
        try:
            popt, _ = curve_fit(
                _power_law,
                t,
                y,
                p0=[100, -0.1, 0],
                bounds=([0, -2, -100], [200, 0, 100]),
                maxfev=5000,
            )
            a, b, c = popt
            # 50 = a*t^b + c  =>  t = ((50-c)/a)^(1/b), b < 0
            if b >= 0 or (50 - c) / a <= 0:
                return None, None
            t50 = np.power((50 - c) / a, 1.0 / b)
            if t50 <= 0 or t50 > 1e7:
                return None, None
            return {"a": a, "b": b, "c": c, "t50_h": t50}, popt
        except Exception:
            return None, None

    return None, None


def predict_lowest_temp_endpoint_arrhenius(
    temperatures_K: list,
    times_h: list,
    T_lowest_K: float,
):
    """
    상위 3개 온도에서 측정된 50% 시간으로 Arrhenius 피팅 후,
    최저 온도에서의 50% 도달 시간 예측.
    times_h[0]은 최저온도(미측정이면 None). 나머지 3개는 측정값.
    """
    # 최저온도 시간을 None으로 두고 나머지 3개로 피팅
    T_fit = []
    t_fit = []
    for T, t in zip(temperatures_K, times_h):
        if t is not None and t > 0:
            T_fit.append(T)
            t_fit.append(t)
    if len(T_fit) < 3:
        return {"ok": False, "message": "최소 3개 온도에서의 50% 도달 시간이 필요합니다."}

    fit = arrhenius_fit(np.array(T_fit), np.array(t_fit))
    Ea = fit["Ea_J_per_mol"]
    t0 = fit["t0_h"]
    t_lowest = predict_life_at_temperature(Ea, t0, T_lowest_K)
    return {
        "ok": True,
        "Ea_kJ_per_mol": Ea / 1000,
        "r_squared": fit["r_squared"],
        "predicted_t50_lowest_h": t_lowest,
        "predicted_t50_lowest_years": t_lowest / (365.25 * 24),
    }


def predict_lowest_temp_endpoint_curve(
    times_h: np.ndarray,
    elongation_percent: np.ndarray,
    model="exponential",
):
    """
    최저 온도에서 3000시간까지의 (시간, 신장율) 데이터로
    50% 도달 시간 외삽 예측.
    """
    res, _ = fit_degradation_curve(times_h, elongation_percent, model=model)
    if res is None:
        return {"ok": False, "message": "곡선 피팅 실패. 데이터 구간과 모델을 확인하세요."}
    return {
        "ok": True,
        "model": model,
        "predicted_t50_h": res["t50_h"],
        "predicted_t50_years": res["t50_h"] / (365.25 * 24),
        "params": {k: v for k, v in res.items() if k != "t50_h"},
    }


def hybrid_predict(
    temperatures_K: list,
    times_h: list,
    T_lowest_K: float,
    times_lowest_h: np.ndarray = None,
    elongation_lowest: np.ndarray = None,
):
    """
    혼합 예측:
    1) 상위 3개 온도로 Arrhenius 예측값 계산
    2) 최저온도에서 부분 곡선 데이터가 있으면 곡선 외삽 예측도 계산
    3) 두 예측의 가중 평균 또는 Arrhenius만 반환
    """
    arr = predict_lowest_temp_endpoint_arrhenius(
        temperatures_K, times_h, T_lowest_K
    )
    if not arr["ok"]:
        return arr

    out = {
        "arrhenius": arr,
        "curve": None,
        "hybrid_t50_h": arr["predicted_t50_lowest_h"],
        "method": "arrhenius_only",
    }

    if times_lowest_h is not None and elongation_lowest is not None and len(times_lowest_h) >= 3:
        for model in ["exponential", "power"]:
            curve = predict_lowest_temp_endpoint_curve(
                times_lowest_h, elongation_lowest, model=model
            )
            if curve["ok"]:
                out["curve"] = curve
                # 곡선 예측이 3000h 이상이고 합리적 범위면 혼합 (신뢰도 가중)
                t_curve = curve["predicted_t50_h"]
                if 3000 < t_curve < 1e6:
                    # Arrhenius와 곡선 예측의 평균 (또는 가중평균)
                    w = 0.5
                    out["hybrid_t50_h"] = w * arr["predicted_t50_lowest_h"] + (1 - w) * t_curve
                    out["method"] = "hybrid"
                break

    out["predicted_t50_lowest_h"] = out["hybrid_t50_h"]
    out["predicted_t50_lowest_years"] = out["predicted_t50_lowest_h"] / (365.25 * 24)
    return out
