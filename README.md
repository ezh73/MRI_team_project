데이터셋 링크
https://drive.google.com/file/d/1RaClSp0GnWCLYqZ_dXpzHuA2F9Z7xqCl/view?usp=drive_link

.pth 링크, API/backend/.pth 파일로 사용
https://drive.google.com/file/d/1IZFHgvIIEhAKSEDym5IgSKSHMuvAkRCq/view?usp=drive_link

# 🧠 MRI 시각화 웹 시스템 (FastAPI + Svelte)

---

## 📁 프로젝트 구조

```plaintext
API/
├── backend/
│   └── model.py
│   └── 0711_BDTLoss_arguments.pth
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
  - HD-BET 기반 두개골 제거
  - XY 해상도 256×256으로 리샘플링 (Z축은 유지)
  - Z-score 정규화 (평균 0, 표준편차 1)


- 모델 추론
  - 모델은 확정, loss 함수나 기타 실험이 필요
  - 모델은 0711_BDTLoss_arguments.pth를 로딩하여 CPU 또는 GPU 자동 선택
  - 2.5D 입력 기반 추론 진행

### 🔁 백엔드 처리 흐름 요약

- 파일 업로드 (.nii 또는 .nii.gz)
- HD-BET 실행 → 두개골 제거
- XY 해상도 256×256으로 리샘플링
- Z-score 정규화
- 전체 z 슬라이스에 대해 2.5D 기반 추론 수행
- 종양 활성도 기준 best_z 자동 선택
- 선택된 z 슬라이스와 예측 마스크 반환
- original, mask, z_index를 프론트로 응답
---

## 🎨 프론트엔드 기능 (`+page.svelte`)

- 파일 업로드 후 백엔드에 요청 → 이미지 수신
- 수신된 `original`, `mask` 데이터를 사용해 오버레이 이미지 생성
- 투명도 조절 슬라이더
- 슬라이스 조절 슬라이더 
- 시각화 구성:
  - 좌측: 원본 이미지
  - 우측: 마스크가 덧씌워진 오버레이 이미지
- 현재 보고 있는 슬라이스의 concat 이미지 다운로드 버튼

---

## ⚠️ 참고 사항

- HD-BET이 미리 설치되어 있어야 합니다 pip install hd-bet

