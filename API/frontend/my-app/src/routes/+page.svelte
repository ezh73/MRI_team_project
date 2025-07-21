<script>
  import { tick } from 'svelte';

  let original = [];
  let mask = [];
  let uploaded = false;
  let alpha = 0.5;
  let loading = false;
  let z_index = 0;

  let canvasOriginal;
  let canvasOverlay;
  let canvasCombined;
  let currentSlice = 0;

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

      if (!data.original || !data.mask || data.original.length === 0) {
        throw new Error("유효한 이미지가 아닙니다.");
      }

      original = data.original;
      mask = data.mask;
      z_index = data.z_index || 0;
      currentSlice = z_index;

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
    if (!original || !mask || original.length === 0 || mask.length === 0) return;

    const height = original[0].length;
    const width = original[0][0].length;

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
        const val = original[currentSlice][i][j];
        const maskVal = mask[currentSlice][i][j];

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

  function handleSliceChange(e) {
    currentSlice = +e.target.value;
    drawImages();
  }

  function downloadConcatImage() {
    const w = canvasOriginal.width;
    const h = canvasOriginal.height;

    const concatCanvas = document.createElement("canvas");
    concatCanvas.width = w * 2;
    concatCanvas.height = h;
    const ctx = concatCanvas.getContext("2d");

    ctx.drawImage(canvasOriginal, 0, 0);

    const overlayCanvas = document.createElement("canvas");
    overlayCanvas.width = w;
    overlayCanvas.height = h;
    const overlayCtx = overlayCanvas.getContext("2d");
    overlayCtx.drawImage(canvasOverlay, 0, 0);
    overlayCtx.drawImage(canvasCombined, 0, 0);

    ctx.drawImage(overlayCanvas, w, 0);

    const link = document.createElement("a");
    link.download = `concat_slice_${currentSlice}.png`;
    link.href = concatCanvas.toDataURL("image/png");
    link.click();
  }

  function goPrev() {
    if (currentSlice > 0) {
      currentSlice--;
      drawImages();
    }
  }

  function goNext() {
    if (currentSlice < original.length - 1) {
      currentSlice++;
      drawImages();
    }
  }
</script>

<h2> 🖼️ MRI 슬라이스 및 세그멘테이션 결과 </h2>
<div style="margin-bottom: 10px;">
  <label for="fileUpload">
    <strong>📁 파일 선택</strong> <span style="font-size: 0.9em; color: gray;">(NIfTI 원본)</span>
  </label><br />
  <input id="fileUpload" type="file" accept=".nii,.nii.gz" on:change={handleUpload} />
</div>

{#if loading}
  <p style="margin-top:10px;">⏳ HD-BET 전처리 및 모델 추론 중입니다...</p>
{/if}

{#if uploaded}
  <p>마스크 투명도: {Math.round(alpha * 100)}%</p>
  <input type="range" min="0" max="1" step="0.01" bind:value={alpha} on:input={handleAlphaChange} />

  <p>슬라이스 선택: {currentSlice} / {original.length - 1}</p>
  <input type="range" min="0" max={original.length - 1} step="1" bind:value={currentSlice} on:input={handleSliceChange} />

  <div style="margin-bottom: 8px;">
    <button on:click={goPrev} disabled={currentSlice === 0}>◀ 이전</button>
    <button on:click={goNext} disabled={currentSlice === original.length - 1}>다음 ▶</button>
    <input type="number" min="0" max={original.length - 1} bind:value={currentSlice} on:input={handleSliceChange} />
  </div>

  {#if currentSlice === z_index}
    <p style="color: green;">📌 현재 슬라이스는 종양 중심 추정 슬라이스입니다 (z = {z_index})</p>
  {:else}
    <p style="color: gray;">🧠 종양 중심 슬라이스: z = {z_index} / 현재: z = {currentSlice}</p>
  {/if}

  <div class="canvas-container">
    <canvas bind:this={canvasOriginal} />
    <div style="position: relative;">
      <canvas bind:this={canvasOverlay} style="position: absolute; left: 0; top: 0; z-index: 0;" />
      <canvas bind:this={canvasCombined} style="position: absolute; left: 0; top: 0; z-index: 1;" />
    </div>
  </div>

  <button on:click={downloadConcatImage}>🖼️ Concat 이미지 다운로드</button>
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
    margin-right: 6px;
    margin-top: 6px;
    padding: 6px 12px;
    font-size: 14px;
  }
</style>
