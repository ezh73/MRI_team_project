<script>
  import { tick } from 'svelte';

  let original = [];
  let mask = [];
  let uploaded = false;
  let alpha = 0.5;
  let loading = false;

  let canvasOriginal;
  let canvasOverlay;
  let canvasCombined;

  async function handleUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    loading = true;
    uploaded = false;

    const formData = new FormData();
    formData.append("file", file);
    
    try {
      const res = await fetch("http://192.168.3.19:5982/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error("서버 오류 발생");

      const data = await res.json();

      // 기본 유효성 검사
      if (!data.original || !data.mask || data.original.length === 0) {
        throw new Error("유효한 이미지가 아닙니다.");
      }

      original = data.original;
      mask = data.mask;

      uploaded = true;
    } catch (err) {
      alert("❌ 오류 발생: " + err.message);
    } finally {
      loading = false;
      await tick();
      drawImages();
    }
  }

  function drawImages() {
    const height = original.length;
    const width = original[0].length;

    canvasOriginal.width = width;
    canvasOriginal.height = height;
    canvasOverlay.width = width;
    canvasOverlay.height = height;
    canvasCombined.width = width;
    canvasCombined.height = height;

    const ctxOrig = canvasOriginal.getContext("2d");
    const ctxBase = canvasOverlay.getContext("2d");
    const ctxMask = canvasCombined.getContext("2d");

    const imgDataOrig = ctxOrig.createImageData(width, height);
    const imgDataBase = ctxBase.createImageData(width, height);
    const imgDataMask = ctxMask.createImageData(width, height);

    for (let i = 0; i < height; i++) {
      for (let j = 0; j < width; j++) {
        const index = (i * width + j) * 4;
        const val = original[i][j];
        const maskVal = mask[i][j];

        imgDataOrig.data.set([val, val, val, 255], index);
        imgDataBase.data.set([val, val, val, 255], index);

        if (maskVal > 0) {
          imgDataMask.data.set([255, 0, 0, alpha * 255], index);
        } else {
          imgDataMask.data.set([0, 0, 0, 0], index);
        }
      }
    }

    ctxOrig.putImageData(imgDataOrig, 0, 0);
    ctxBase.putImageData(imgDataBase, 0, 0);
    ctxMask.putImageData(imgDataMask, 0, 0);
  }

  function handleAlphaChange(e) {
    alpha = e.target.value;
    drawImages();
  }

function downloadConcatImage() {
  const w = canvasOriginal.width;
  const h = canvasOriginal.height;

  // 최종 concat 이미지 (좌: 원본 / 우: 오버레이+마스크)
  const concatCanvas = document.createElement("canvas");
  concatCanvas.width = w * 2;
  concatCanvas.height = h;
  const ctx = concatCanvas.getContext("2d");

  // 왼쪽: 원본
  ctx.drawImage(canvasOriginal, 0, 0);

  // 오른쪽: 오버레이 + 마스크를 임시 캔버스에 그리기
  const overlayCanvas = document.createElement("canvas");
  overlayCanvas.width = w;
  overlayCanvas.height = h;
  const overlayCtx = overlayCanvas.getContext("2d");

  // 회색 이미지 먼저
  overlayCtx.drawImage(canvasOverlay, 0, 0);
  // 그 위에 빨간 마스크 올리기
  overlayCtx.drawImage(canvasCombined, 0, 0);

  // 오른쪽에 합쳐서 붙이기
  ctx.drawImage(overlayCanvas, w, 0);

  // 다운로드
  const link = document.createElement("a");
  link.download = "concat_image.png";
  link.href = concatCanvas.toDataURL("image/png");
  link.click();
}

</script>

<h2> 🖼️ MRI 슬라이스 및 세그멘테이션 결과 </h2>

<!-- 📁 파일 업로드 입력 + 안내 문구 -->
<div style="margin-bottom: 10px;">
  <label for="fileUpload">
    <strong>📁 파일 선택</strong> <span style="font-size: 0.9em; color: gray;">(NIfTI 원본)</span>
  </label><br />
  <input id="fileUpload" type="file" accept=".nii,.nii.gz" on:change={handleUpload} />
</div>

<!-- ⏳ 로딩 중 상태 표시 -->
{#if loading}
  <p style="margin-top:10px;">⏳ HD-BET 전처리 및 모델 추론 중입니다...</p>
{/if}

<!-- ✅ 업로드 및 추론 완료 시 결과 시각화 -->
{#if uploaded}
  <p>투명도: {Math.round(alpha * 100)}%</p>
  <input type="range" min="0" max="1" step="0.01" bind:value={alpha} on:input={handleAlphaChange} />

  <div class="canvas-container">
    <canvas bind:this={canvasOriginal} />
    <div style="position: relative;">
      <canvas bind:this={canvasOverlay} style="position: absolute; left: 0; top: 0; z-index: 0;" />
      <canvas bind:this={canvasCombined} style="position: absolute; left: 0; top: 0; z-index: 1;" />
    </div>
  </div>

  <button on:click={downloadConcatImage}>Concat 이미지 다운로드</button>
{/if}

<style>
  h2 {
    font-weight: bold;
    margin-bottom: 10px;
  }

  .canvas-container {
    display: flex;
    gap: 40px;
    margin-top: 20px;
    margin-bottom: 10px;
  }

  canvas {
    border: 1px solid gray;
    width: 320px;
    height: 320px;
    image-rendering: pixelated;
  }

  button {
    margin-top: 10px;
    padding: 6px 12px;
    font-size: 14px;
  }
</style>
