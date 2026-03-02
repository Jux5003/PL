# -*- coding: utf-8 -*-
"""
IEC 60216-2 / Arrhenius 고분자 장기 수명 예측 웹 앱
"""
import json
import math
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# 프로젝트 루트(cursorstudy)를 path에 추가하여 polymer_life 패키지 로드
import sys
from pathlib import Path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
from polymer_life import arrhenius, ml_predictor


def celsius_to_kelvin(c):
    if c is None:
        return None
    return float(c) + 273.15


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/validate", methods=["POST"])
def api_validate():
    """IEC 60216-2 조건 검증"""
    data = request.get_json() or {}
    temps_c = data.get("temperatures_c") or []
    times_h = data.get("times_h") or []
    if len(temps_c) != 4 or len(times_h) != 4:
        return jsonify({"ok": False, "message": "온도 4개와 시간 4개를 입력하세요."})
    temps_k = [celsius_to_kelvin(t) for t in temps_c]
    times = []
    for t in times_h:
        if t is None or str(t).strip() == "":
            times.append(None)
        else:
            try:
                times.append(float(t))
            except (TypeError, ValueError):
                times.append(None)
    valid_times = [t for t in times if t is not None]
    if len(valid_times) != 4:
        return jsonify({
            "ok": True,
            "message": "최저 온도 시간이 비어 있으면 예측 모드입니다. 나머지 3개 온도 데이터로 최저 온도 끝점을 예측할 수 있습니다.",
            "prediction_mode": True,
        })
    result = arrhenius.validate_iec60216_2(temps_k, times)
    return jsonify(result)


@app.route("/api/arrhenius", methods=["POST"])
def api_arrhenius():
    """Arrhenius 피팅 및 수명 예측"""
    data = request.get_json() or {}
    temps_c = data.get("temperatures_c") or []
    times_h = data.get("times_h") or []
    use_temp_c = data.get("use_temp_c")
    if len(temps_c) != 4 or len(times_h) != 4:
        return jsonify({"error": "온도 4개와 시간 4개를 입력하세요."})
    temps_k = [celsius_to_kelvin(t) for t in temps_c]
    times = []
    for t in times_h:
        if t is None or str(t).strip() == "":
            times.append(None)
        else:
            try:
                times.append(float(t))
            except (TypeError, ValueError):
                times.append(None)
    T_use_K = celsius_to_kelvin(use_temp_c) if use_temp_c is not None and str(use_temp_c).strip() != "" else None
    T_lowest_K = temps_k[0] if temps_k else None
    result = arrhenius.fit_and_predict(
        temperatures_K=temps_k,
        times_h=times,
        T_use_K=T_use_K,
        T_lowest_K=T_lowest_K,
    )
    if "error" in result:
        return jsonify(result)
    fit = result.get("fit", {})
    for key in ("x", "y"):
        if key in fit and hasattr(fit[key], "__iter__") and not isinstance(fit[key], list):
            fit[key] = [float(v) for v in fit[key]]
    for k, v in list(result.get("fit", {}).items()):
        if hasattr(v, "item"):
            result["fit"][k] = float(v) if not isinstance(v, (list, dict)) else v
    return jsonify(result)


@app.route("/api/predict_lowest", methods=["POST"])
def api_predict_lowest():
    """최저 온도 끝점 예측 (상위 3개 온도 Arrhenius + 선택적 곡선 데이터)"""
    data = request.get_json() or {}
    temps_c = data.get("temperatures_c") or []
    times_h = data.get("times_h") or []
    curve_times = data.get("curve_times") or []
    curve_elongation = data.get("curve_elongation") or []
    if len(temps_c) != 4:
        return jsonify({"ok": False, "message": "온도 4개를 입력하세요."})
    temps_k = [celsius_to_kelvin(t) for t in temps_c]
    times = []
    for t in times_h:
        if t is None or str(t).strip() == "":
            times.append(None)
        else:
            try:
                times.append(float(t))
            except (TypeError, ValueError):
                times.append(None)
    if sum(1 for x in times if x is not None and x > 0) < 3:
        return jsonify({"ok": False, "message": "최소 3개 온도에서 50% 도달 시간(h)을 입력하세요. (최저 온도는 비워두고 예측)"})
    T_lowest_K = temps_k[0]
    times_lowest = None
    elongation_lowest = None
    if curve_times and curve_elongation and len(curve_times) == len(curve_elongation) and len(curve_times) >= 3:
        try:
            times_lowest = [float(x) for x in curve_times]
            elongation_lowest = [float(x) for x in curve_elongation]
        except (TypeError, ValueError):
            pass
    result = ml_predictor.hybrid_predict(
        temperatures_K=temps_k,
        times_h=times,
        T_lowest_K=T_lowest_K,
        times_lowest_h=times_lowest if times_lowest else None,
        elongation_lowest=elongation_lowest if elongation_lowest else None,
    )
    if not result.get("ok", True):
        arr = result.get("arrhenius", {})
        if arr and arr.get("ok"):
            return jsonify(result)
        return jsonify({"ok": False, "message": result.get("message", "예측 실패")})
    def to_serializable(obj):
        if hasattr(obj, "item"):
            return float(obj)
        if isinstance(obj, dict):
            return {k: to_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [to_serializable(x) for x in obj]
        return obj
    return jsonify(to_serializable(result))


if __name__ == "__main__":
    app.run(debug=True, port=5050)
