# main.py
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import os, tempfile, subprocess, sys
import numpy as np
import torch
import SimpleITK as sitk
import nibabel as nib

from model import AttentionUNet2p5D_ASPP

# ─────────────────────── FastAPI 설정 ───────────────────────
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────── 모델 로드 ───────────────────────
DEVICE = torch.device("cuda:1" if torch.cuda.is_available() else "cpu")
MODEL_PATH = "./0711_BDTLoss_arguments.pth"
IN_CHANNELS = 5

model = AttentionUNet2p5D_ASPP().to(DEVICE)
model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
model.eval()

# ─────────────────────── 리샘플링 함수 ───────────────────────
def resample_xy_sitk(img: sitk.Image, new_size_xy=(256, 256), interp=sitk.sitkLinear):
    size = list(img.GetSize())
    spacing = list(img.GetSpacing())

    size[0], size[1] = new_size_xy
    spacing[0] = img.GetSpacing()[0] * img.GetSize()[0] / new_size_xy[0]
    spacing[1] = img.GetSpacing()[1] * img.GetSize()[1] / new_size_xy[1]

    rf = sitk.ResampleImageFilter()
    rf.SetSize(size)
    rf.SetOutputSpacing(spacing)
    rf.SetOutputOrigin(img.GetOrigin())
    rf.SetOutputDirection(img.GetDirection())
    rf.SetInterpolator(interp)

    return rf.Execute(img)

# ─────────────────────── Z-score 정규화 ───────────────────────
def numpy_zscore_normalize(data: np.ndarray, mask: np.ndarray, clip_sigma: float = 5.0):
    vox = data[mask]
    mu = vox.mean()
    sigma = vox.std() if vox.std() > 0 else 1.0
    z = (data - mu) / sigma
    z = np.clip(z, -clip_sigma, clip_sigma)
    return (z + clip_sigma) / (2 * clip_sigma)

# ─────────────────────── HD-BET 실행 ───────────────────────
def run_hd_bet(input_path: str, output_path: str) -> str:
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"입력 파일이 존재하지 않음: {input_path}")
    if not output_path.endswith(".nii.gz"):
        raise ValueError(f"출력 파일은 .nii.gz로 끝나야 합니다: {output_path}")

    cmd = [
        "hd-bet",
        "-i", input_path,
        "-o", output_path,
        "-device", "cuda:1",
        "--save_bet_mask"
    ]

    print("🚀 HD-BET 실행 중:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    mask_path = output_path.replace(".nii.gz", "_bet.nii.gz")
    if not os.path.exists(mask_path):
        raise FileNotFoundError(f"❌ 마스크 파일이 생성되지 않음: {mask_path}")

    return mask_path

# ─────────────────────── 2.5D 입력 생성 ───────────────────────
def create_2p5d_input(volume: np.ndarray, z: int) -> np.ndarray:
    c, h, w = IN_CHANNELS, *volume.shape[1:]
    half = c // 2
    slices = []
    for dz in range(-half, half + 1):
        zz = np.clip(z + dz, 0, volume.shape[0] - 1)
        slices.append(volume[zz])
    return np.stack(slices, axis=0)  # [C, H, W]

# ─────────────────────── 업로드 및 추론 ───────────────────────
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, file.filename)
        with open(input_path, "wb") as f:
            f.write(await file.read())

        # 1. HD-BET 실행
        output_path = os.path.join(tmpdir, "stripped.nii.gz")
        mask_path = run_hd_bet(input_path, output_path)

        # 2. 리샘플링 및 정규화
        img_sitk = sitk.ReadImage(output_path)     
        mask_sitk = sitk.ReadImage(mask_path) 

        img_xy = resample_xy_sitk(img_sitk, (256, 256), sitk.sitkLinear)
        mask_xy = resample_xy_sitk(mask_sitk, (256, 256), sitk.sitkNearestNeighbor)

        img = sitk.GetArrayFromImage(img_xy).astype(np.float32)  # [Z, H, W]
        mask = sitk.GetArrayFromImage(mask_xy).astype(bool)

        norm = numpy_zscore_normalize(img, mask)  # [Z, H, W]

        # 3. 전체 슬라이스 추론
        pred_masks = []
        with torch.no_grad():
            for z in range(norm.shape[0]):
                input_tensor = create_2p5d_input(norm, z)
                input_tensor = torch.from_numpy(input_tensor).unsqueeze(0).to(DEVICE)
                pred = model(input_tensor)
                pred_mask = (torch.sigmoid(pred[0, 0]) > 0.5).cpu().numpy().astype(np.uint8)
                pred_masks.append(pred_mask)

        pred_volume = np.stack(pred_masks, axis=0)  # [Z, H, W]

        coords = np.argwhere(pred_volume == 1)
        if len(coords) == 0:
            z_index = norm.shape[0] // 2  # 종양 없을 때 중앙값으로 fallback
        else:
            z_index = int(round(coords[:, 0].mean()))  # Z 축 중심


        # 4. 시각화용 변환 - 전체 슬라이스 변환
        original_all = []
        mask_all = []

        for i in range(norm.shape[0]):
            slice_2d = norm[i]
            slice_vis = (slice_2d - np.min(slice_2d)) / (np.max(slice_2d) - np.min(slice_2d) + 1e-8)
            slice_vis = (slice_vis * 255).astype(np.uint8)
            original_all.append(slice_vis.tolist())  

            mask_slice = pred_volume[i].astype(np.uint8) * 255
            mask_all.append(mask_slice.tolist())     

        return {
            "original": original_all,
            "mask": mask_all,
            "z_index": z_index
        }