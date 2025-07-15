from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import nibabel as nib
import tempfile
import subprocess
import os
import SimpleITK as sitk
import cv2
import torch
from model import AttentionUNet2p5D_ASPP

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 모델 로딩
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MODEL_PATH = "./best_model.pth"
IN_CHANNELS = 5

model = AttentionUNet2p5D_ASPP().to(DEVICE)
model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
model.eval()

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = os.path.join(tmpdir, file.filename)
        out_path = os.path.join(tmpdir, "output_bet.nii.gz")

        with open(in_path, "wb") as f:
            f.write(await file.read())

        ext = file.filename.lower()
        if not (ext.endswith(".nii") or ext.endswith(".nii.gz")):
            raise ValueError("NIfTI (.nii/.nii.gz) 파일만 지원합니다.")

        # HD-BET 실행
        print("🧠 HD-BET 실행")
        run_hd_bet(in_path, out_path)

        # HD-BET 결과 로딩
        sitk_img = sitk.ReadImage(out_path)

        # 1. Resample
        resampled = resample_to_spacing(sitk_img, new_spacing=(1.0, 1.0, 1.0))
        volume = sitk.GetArrayFromImage(resampled)  # (Z, H, W)
        volume = minmax_normalize(volume)


        # 2. 모든 z에 대해 예측
        preds = []
        for z in range(volume.shape[0]):
            input_2p5d = extract_2p5d_input(volume, z, in_channels=IN_CHANNELS)
            input_tensor = torch.from_numpy(input_2p5d).unsqueeze(0).to(DEVICE)
            with torch.no_grad():
                output = model(input_tensor)
                prob = torch.sigmoid(output)[0, 0].cpu().numpy()
            preds.append(prob)

        # 3. 종양 활성도 가장 높은 z 선택
        tumor_scores = [np.mean(p > 0.5) for p in preds]
        best_z = int(np.argmax(tumor_scores))
        best_prob = preds[best_z]

        # 4. 시각화용 데이터 준비
        orig_slice = volume[best_z]
        orig_resized = resize_to_512(orig_slice)
        slice_2d_vis = normalize_to_uint8(orig_resized)

        mask_uint8 = (best_prob > 0.5).astype(np.uint8) * 255

        return {
            "original": slice_2d_vis.tolist(),
            "mask": mask_uint8.tolist(),
            "z_index": best_z
        }

# ================================
# 🔧 유틸리티 함수들
# ================================

def run_hd_bet(in_path, out_path):
    try:
        subprocess.run(
            ["hd-bet", "-i", in_path, "-o", out_path, "-device", "cpu"],
            check=True
        )
    except subprocess.CalledProcessError:
        raise RuntimeError("HD-BET 실행 실패")

def resample_to_spacing(image, new_spacing=(1.0, 1.0, 1.0)):
    orig_spacing = image.GetSpacing()
    orig_size = image.GetSize()
    new_size = [
        int(round(orig_size[i] * (orig_spacing[i] / new_spacing[i])))
        for i in range(3)
    ]
    resampler = sitk.ResampleImageFilter()
    resampler.SetOutputSpacing(new_spacing)
    resampler.SetSize(new_size)
    resampler.SetOutputDirection(image.GetDirection())
    resampler.SetOutputOrigin(image.GetOrigin())
    resampler.SetInterpolator(sitk.sitkLinear)
    return resampler.Execute(image)

def minmax_normalize(volume):
    volume = np.nan_to_num(volume)
    v_min, v_max = volume.min(), volume.max()
    return (volume - v_min) / (v_max - v_min + 1e-8)


def normalize_to_uint8(img):
    img = np.nan_to_num(img)
    img = (img - img.min()) / (img.max() - img.min() + 1e-8)
    return (img * 255).astype(np.uint8)

def extract_2p5d_input(volume, z, in_channels=5):
    half = in_channels // 2
    z_indices = [np.clip(z + i, 0, volume.shape[0] - 1) for i in range(-half, half + 1)]
    slices = [resize_to_512(volume[zi]) for zi in z_indices]
    return np.stack(slices, axis=0).astype(np.float32)

def resize_to_512(img):
    return cv2.resize(img, (512, 512), interpolation=cv2.INTER_LINEAR)
