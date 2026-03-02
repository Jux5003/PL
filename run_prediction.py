# -*- coding: utf-8 -*-
"""
IEC 60216-2 / Arrhenius 고분자 장기 수명 예측 — 독립 실행 스크립트
사용법:
  python run_prediction.py
또는
  python run_prediction.py --t1 140 --t2 150 --t3 160 --t4 170 --h2 2500 --h3 800 --h4 200 --use-temp 120
"""
import argparse
import sys
from pathlib import Path

# 상위(cursorstudy)를 path에 추가하여 polymer_life 패키지 import
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
from polymer_life import arrhenius, ml_predictor


def main():
    parser = argparse.ArgumentParser(description="IEC 60216-2 Arrhenius 장기 수명 예측")
    parser.add_argument("--t1", type=float, default=140, help="최저 온도 °C")
    parser.add_argument("--t2", type=float, default=150, help="온도 2 °C")
    parser.add_argument("--t3", type=float, default=160, help="온도 3 °C")
    parser.add_argument("--t4", type=float, default=170, help="최고 온도 °C")
    parser.add_argument("--h1", type=float, default=None, help="온도1 50%% 도달 시간 (h), 비우면 예측")
    parser.add_argument("--h2", type=float, default=2500, help="온도2 50%% 도달 시간 (h)")
    parser.add_argument("--h3", type=float, default=800, help="온도3 50%% 도달 시간 (h)")
    parser.add_argument("--h4", type=float, default=200, help="온도4 50%% 도달 시간 (h)")
    parser.add_argument("--use-temp", type=float, default=120, help="사용 허용 온도 °C")
    args = parser.parse_args()

    def c2k(c):
        return c + 273.15

    temps_k = [c2k(args.t1), c2k(args.t2), c2k(args.t3), c2k(args.t4)]
    times_h = [args.h1, args.h2, args.h3, args.h4]

    print("=== IEC 60216-2 고분자 장기 수명 예측 ===\n")
    print("온도 (°C):", [args.t1, args.t2, args.t3, args.t4])
    print("50% 도달 시간 (h):", times_h)
    print("사용 허용 온도 (°C):", args.use_temp)
    print()

    # 1) 최저 온도가 비어 있으면 ML 예측
    if args.h1 is None or args.h1 <= 0:
        print("[1] 최저 온도 끝점 예측 (상위 3개 온도 Arrhenius)")
        pred = ml_predictor.predict_lowest_temp_endpoint_arrhenius(
            temperatures_K=temps_k,
            times_h=times_h,
            T_lowest_K=temps_k[0],
        )
        if not pred.get("ok"):
            print("오류:", pred.get("message", "예측 실패"))
            return
        t_lowest = pred["predicted_t50_lowest_h"]
        print("  예측 최저온도 50% 도달 시간: {:.0f} h ({:.2f}년)".format(
            t_lowest, pred["predicted_t50_lowest_years"]))
        print("  Ea: {:.2f} kJ/mol, R²: {:.4f}".format(
            pred["Ea_kJ_per_mol"], pred["r_squared"]))
        times_h = [t_lowest, args.h2, args.h3, args.h4]
        print()

    # 2) IEC 검증 (4개 모두 있을 때)
    valid = arrhenius.validate_iec60216_2(temps_k, times_h)
    print("[2] IEC 60216-2 검증:", valid["message"])
    if not valid["ok"]:
        print()
        return
    print()

    # 3) Arrhenius 피팅 및 사용 온도 수명
    result = arrhenius.fit_and_predict(
        temperatures_K=temps_k,
        times_h=times_h,
        T_use_K=c2k(args.use_temp),
        T_lowest_K=temps_k[0],
    )
    if "error" in result:
        print("오류:", result["error"])
        return
    fit = result["fit"]
    print("[3] Arrhenius 피팅")
    print("  Ea: {:.2f} kJ/mol".format(fit["Ea_kJ_per_mol"]))
    print("  R²: {:.4f}".format(fit["r_squared"]))
    if "life_at_use_temp_h" in result:
        print("  사용 온도({}°C) 예측 수명: {:.0f} h ({:.2f}년)".format(
            args.use_temp,
            result["life_at_use_temp_h"],
            result["life_at_use_temp_years"],
        ))
    print("\n완료.")


if __name__ == "__main__":
    main()
