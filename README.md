# IEC 60216-2 고분자 장기 수명 예측

(index.html 파일은 templates 폴더를 생성하고 거기로 옮길 것)

Arrhenius 식과 Arrhenius plot을 사용하며, **IEC 60216-2** 국제 규격을 만족하는 고분자 재료의 장기 수명 예측 도구입니다. TTS(Time-Temperature Superposition) 개념을 적용합니다.

## 규격 요약 (IEC 60216-2)

1. 사용 허용 온도보다 높은 **서로 다른 4개 온도**에서 평가
2. 4개 온도는 **최소 10°C** 간격
3. 각 온도에서 신장율이 **상온 측정값의 50%**가 되는 시점 확인
4. **최고 온도**: 50% 시점이 **최소 100시간** 이후
5. **최저 온도**: 50% 시점이 **최소 5000시간** 이후

최저 온도에서 5000시간까지 시험하는 데 시간이 오래 걸리므로, **상위 3개 온도 데이터 + 최저 온도 3000시간까지의 부분 데이터**로 머신러닝/통계를 이용해 최저 온도 끝점을 예측할 수 있습니다.

## 설치

```bash
cd cursorstudy
pip install -r polymer_life/requirements.txt
```

**참고:** `cursorstudy` 폴더가 프로젝트 루트이므로, 스크립트 실행 시 이 폴더를 현재 디렉터리로 두고 실행하는 것이 좋습니다.

## 사용 방법

### 1) 웹 앱 (권장)

**현재 디렉터리를 프로젝트 루트(cursorstudy)로 둔 뒤:**

```bash
cd cursorstudy
python polymer_life/app.py
```

또는 `polymer_life` 폴더에서 실행하려면 상위 경로가 Python path에 있어야 하므로, 프로젝트 루트에서 실행하는 것을 권장합니다.

브라우저에서 **http://127.0.0.1:5050** 접속 후:

- **온도 4개**와 **각 온도에서 50% 도달 시간(h)** 입력
- 최저 온도 시간을 **비워두면** → 상위 3개 온도로 Arrhenius 피팅 후 최저 온도 끝점 **예측**
- 선택적으로 **최저 온도에서의 시간–신장율(%)** 부분 데이터를 넣으면, 곡선 피팅(지수/멱함수)과 Arrhenius를 혼합해 예측
- **사용 허용 온도**를 입력한 뒤 **Arrhenius 피팅 및 수명 예측**으로 해당 온도에서의 예측 수명 확인

### 2) Python 스크립트

**프로젝트 루트(cursorstudy)에서:**

```bash
cd cursorstudy
python polymer_life/run_prediction.py
```

**인자로 온도/시간 지정:**

```bash
python polymer_life/run_prediction.py --t1 140 --t2 150 --t3 160 --t4 170 --h2 2500 --h3 800 --h4 200 --use-temp 120
```

**최저 온도 h1 없이 예측만 (상위 3개로 Arrhenius 외삽):**

```bash
python polymer_life/run_prediction.py --t1 140 --t2 150 --t3 160 --t4 170 --h2 2500 --h3 800 --h4 200 --use-temp 120
```

### 3) Python에서 모듈로 사용

```python
from polymer_life import arrhenius, ml_predictor

# Kelvin
temps_k = [413.15, 423.15, 433.15, 443.15]  # 140, 150, 160, 170 °C
# 최저 온도는 None으로 두고 예측
times_h = [None, 2500, 800, 200]

# 최저 온도 끝점 예측 (상위 3개 Arrhenius)
pred = ml_predictor.predict_lowest_temp_endpoint_arrhenius(
    temperatures_K=temps_k, times_h=times_h, T_lowest_K=temps_k[0]
)
print("예측 50% 시간 (h):", pred["predicted_t50_lowest_h"])

# 전체 4점으로 수명 예측 (예측된 t1 사용 시)
times_h[0] = pred["predicted_t50_lowest_h"]
result = arrhenius.fit_and_predict(
    temperatures_K=temps_k, times_h=times_h,
    T_use_K=393.15,  # 120 °C
)
print("사용 온도 예측 수명 (년):", result["life_at_use_temp_years"])
```

## 폴더 구조

```
polymer_life/
  __init__.py
  arrhenius.py      # Arrhenius 피팅, IEC 60216-2 검증, 수명 예측
  ml_predictor.py   # 최저 온도 끝점 예측 (Arrhenius 외삽 + 곡선 피팅)
  app.py            # Flask 웹 앱
  run_prediction.py # CLI 스크립트
  requirements.txt
  templates/
    index.html
  README.md
```

## 참고

- **Arrhenius**: \( t = t_0 \exp(E_a/(RT)) \), 즉 \( \ln t = \ln t_0 + E_a/(R \cdot T) \). `ln(t)` vs `1/T` 선형 회귀로 \(E_a\) 추정.
- **최저 온도 예측**: 상위 3개 온도에서 구한 \(E_a\), \(t_0\)로 최저 온도에서의 50% 도달 시간 예측.
- **곡선 피팅**: 최저 온도에서 3000시간까지 (시간, 신장율%) 데이터가 있으면 지수/멱함수 모델로 50% 시점 외삽 후, 필요 시 Arrhenius 예측과 혼합.

---

## 실행 테스트가 멈추거나 실패하는 경우

1. **"Command failed to spawn: Aborted"** — 터미널/한글 경로 문제일 수 있음. Cursor 통합 터미널에서 `cd`로 `cursorstudy` 이동 후 `python polymer_life/app.py` 실행.
2. **PowerShell에서 `&&` 오류** — PowerShell은 `&&` 미지원. `;` 사용: `cd cursorstudy; python polymer_life/app.py`
3. **`python`을 찾을 수 없음** — 가상환경 활성화(`venv\Scripts\activate`) 후 실행하거나 `py polymer_life/app.py` 시도.
4. **import 오류** — 반드시 **프로젝트 루트(cursorstudy)**에서 `python polymer_life/app.py` 실행.

