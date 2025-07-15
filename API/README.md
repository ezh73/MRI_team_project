# 🧠 MRI 시각화 웹 시스템 (FastAPI + Svelte)

---

## 📁 프로젝트 구조

```plaintext
API/
├── backend/
│   └── model.py
│   └── best_model.pth
│   └── main.py                # FastAPI 백엔드
├── frontend/
│   └── my-app/
│       └── src/
│           └── routes/
│               └── +page.svelte   # Svelte 프론트엔드
└── README.md
```

---

## ⚙️ 실행 명령어

- **프론트엔드 실행**
  ```bash
  npm run dev -- --host 0.0.0.0 --port 5173
  ```

- **백엔드 실행**
  ```bash
  uvicorn main:app --reload --host 0.0.0.0 --port 5982
  ```

---

## 🖥️ 백엔드 기능 (`main.py`)

- .nii, .nii.gz 3D NIfTI 파일만 입력 지원
→ .npy, 2D 이미지는 현재 미지원

- 전처리 
  - HD-BET 기반 두개골 제거 (CPU 사용 중)
  - 1mm³ spacing 기준으로 리샘플링 (SimpleITK)
  - min-max 정규화

- 모델 추론
  - 모델 미확정, 임시 모델 사용중
  - 모델은 best_model.pth를 로딩하여 CPU 또는 GPU 자동 선택

### 🔁 백엔드 처리 흐름 요약

파일 업로드 (.nii/.nii.gz)

HD-BET 실행 (두개골 제거)

1mm³ spacing으로 리샘플링

정규화 (min-max)

전체 z 슬라이스에 대해 2.5D 기반 추론

종양 활성도 기준 best_z 자동 선택

해당 z 슬라이스와 예측 마스크 반환

original, mask, z_index를 프론트로 응답
---

## 🎨 프론트엔드 기능 (`+page.svelte`)

- 파일 업로드 후 백엔드에 요청 → 이미지 수신
- 수신된 `original`, `mask` 데이터를 사용해 오버레이 이미지 생성
- **투명도 조절 슬라이더** 제공 (`0% ~ 100%`)
- 시각화 구성:
  - **좌측**: 원본 이미지
  - **우측**: 마스크가 덧씌워진 오버레이 이미지
- **concat 이미지 다운로드** 버튼 제공

---

## ⚠️ 참고 사항

- HD-BET이 미리 설치되어 있어야 합니다 pip install hd-bet
- 모델이 확정되면:
  - 슬라이스 선택 방식
  - 전처리 방식
  - 마스크 출력 방식 변경 예정
