# -*- coding: utf-8 -*-
"""
IEC 60216-2 / Arrhenius 기반 고분자 장기 수명 예측
- Arrhenius equation: t = t0 * exp(Ea/(R*T))  =>  ln(t) = ln(t0) + Ea/(R*T)
- TTS 개념: 온도-시간 치환
"""

import numpy as np
from scipy import stats

R_GAS = 8.314462618  # J/(mol·K)


def validate_iec60216_2(temperatures_K: list, times_h: list) -> dict:
    """
    IEC 60216-2 조건 검증.
    temperatures_K: 4개 온도 [최저온도, ..., 최고온도] (Kelvin)
    times_h: 각 온도에서 신장율 50% 도달 시간 (h)
    """
    temps = np.array(temperatures_K)
    times = np.array(times_h)
    if len(temps) != 4 or len(times) != 4:
        return {"ok": False, "message": "온도 4개와 시간 4개가 필요합니다."}

    # 1. 온도 간격 최소 10°C
    temps_C = temps - 273.15
    for i in range(3):
        if temps_C[i + 1] - temps_C[i] < 10:
            return {"ok": False, "message": f"온도 간격이 10°C 이상이어야 합니다. (T{i+1}={temps_C[i]:.1f}°C, T{i+2}={temps_C[i+1]:.1f}°C)"}

    # 2. 최고온도: 50% 시점 >= 100h
    if times[-1] < 100:
        return {"ok": False, "message": f"최고 온도에서 50% 시점은 최소 100시간 이상이어야 합니다. (현재 {times[-1]:.0f}h)"}

    # 3. 최저온도: 50% 시점 >= 5000h
    if times[0] < 5000:
        return {"ok": False, "message": f"최저 온도에서 50% 시점은 최소 5000시간 이상이어야 합니다. (현재 {times[0]:.0f}h)"}

    return {"ok": True, "message": "IEC 60216-2 조건을 만족합니다."}


def arrhenius_fit(temperatures_K: np.ndarray, times_h: np.ndarray):
    """
    Arrhenius plot: ln(t) = a + Ea/(R*T)
    x = 1/T (K^-1), y = ln(t)
    slope = Ea/R  =>  Ea = slope * R
    """
    x = 1.0 / np.asarray(temperatures_K)
    y = np.log(np.asarray(times_h))
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    Ea = slope * R_GAS  # J/mol
    ln_t0 = intercept
    t0 = np.exp(intercept)
    return {
        "Ea_J_per_mol": Ea,
        "Ea_kJ_per_mol": Ea / 1000,
        "t0_h": t0,
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_value ** 2,
        "x": x.tolist(),
        "y": y.tolist(),
    }


def predict_life_at_temperature(Ea_J_per_mol: float, t0_h: float, T_use_K: float) -> float:
    """사용 온도에서의 예측 수명 (h). t = t0 * exp(Ea/(R*T))"""
    return t0_h * np.exp(Ea_J_per_mol / (R_GAS * T_use_K))


def predict_time_at_temperature(Ea_J_per_mol: float, t_ref_h: float, T_ref_K: float, T_target_K: float) -> float:
    """기준점 (T_ref, t_ref)에서 목표 온도 T_target에서의 시간 예측."""
    return t_ref_h * np.exp((Ea_J_per_mol / R_GAS) * (1 / T_target_K - 1 / T_ref_K))


def fit_and_predict(
    temperatures_K: list,
    times_h: list,
    T_use_K: float = None,
    T_lowest_K: float = None,
):
    """
    Arrhenius 피팅 후 사용온도·최저온도 수명 예측.
    times_h에 None이 있으면 해당 온도는 피팅에서 제외 (ML로 예측된 값 사용 시).
    """
    temps = np.array(temperatures_K)
    valid = np.array([t is not None and t > 0 for t in times_h])
    if not np.any(valid):
        return {"error": "유효한 (온도, 시간) 쌍이 없습니다."}

    T_fit = temps[valid]
    t_fit = np.array([t for t, v in zip(times_h, valid) if v])

    fit = arrhenius_fit(T_fit, t_fit)
    Ea = fit["Ea_J_per_mol"]
    t0 = fit["t0_h"]

    result = {"fit": fit}

    if T_use_K is not None and T_use_K > 0:
        result["life_at_use_temp_h"] = predict_life_at_temperature(Ea, t0, T_use_K)
        result["life_at_use_temp_years"] = result["life_at_use_temp_h"] / (365.25 * 24)

    if T_lowest_K is not None and T_lowest_K > 0:
        # 이미 있는 경우와 동일하게 t0 기반 예측
        result["predicted_t_lowest_h"] = predict_life_at_temperature(Ea, t0, T_lowest_K)

    return result
