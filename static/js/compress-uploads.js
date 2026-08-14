/** A Vercel recusa request acima de ~4,5 MB. Fotos de celular passam disso; comprimimos no aparelho. */
(function () {
  const MAX_LADO = 1280;
  const MAX_BYTES = 280 * 1024;
  const TETO_DO_PEDIDO = 4 * 1024 * 1024;

  function jpegName(name) {
    return String(name || "foto.jpg").replace(/\.[^.]+$/, "") + ".jpg";
  }

  function draw(image, lado) {
    const scale = Math.min(1, lado / Math.max(image.width, image.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(image.width * scale));
    canvas.height = Math.max(1, Math.round(image.height * scale));
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    return canvas;
  }

  function toBlob(canvas, quality) {
    return new Promise((resolve) => {
      canvas.toBlob((blob) => resolve(blob), "image/jpeg", quality);
    });
  }

  async function loadImage(file) {
    if (typeof createImageBitmap === "function") {
      try {
        return await createImageBitmap(file);
      } catch (_err) {
        /* HEIC ou formato que o bitmap não abre: cai no <img>. */
      }
    }
    const url = URL.createObjectURL(file);
    try {
      const image = await new Promise((resolve, reject) => {
        const el = new Image();
        el.onload = () => resolve(el);
        el.onerror = () => reject(new Error("foto inválida"));
        el.src = url;
      });
      return image;
    } finally {
      URL.revokeObjectURL(url);
    }
  }

  async function compressFile(file) {
    if (!file || !file.type.startsWith("image/")) return file;
    if (file.size <= MAX_BYTES && file.type === "image/jpeg") return file;
    const image = await loadImage(file);
    let lado = MAX_LADO;
    let quality = 0.72;
    let blob = await toBlob(draw(image, lado), quality);
    while (blob && blob.size > MAX_BYTES && (quality > 0.42 || lado > 720)) {
      if (quality > 0.42) quality -= 0.1;
      else lado = Math.round(lado * 0.8);
      blob = await toBlob(draw(image, lado), quality);
    }
    if (typeof image.close === "function") image.close();
    if (!blob) return file;
    return new File([blob], jpegName(file.name), { type: "image/jpeg", lastModified: Date.now() });
  }

  async function compressForm(form) {
    const inputs = Array.from(form.querySelectorAll('input[type="file"]'));
    for (const input of inputs) {
      if (!input.files || input.files.length === 0) continue;
      const next = new DataTransfer();
      for (const file of input.files) {
        next.items.add(await compressFile(file));
      }
      input.files = next.files;
    }
    const total = inputs.reduce((sum, input) => {
      return sum + Array.from(input.files || []).reduce((inner, file) => inner + file.size, 0);
    }, 0);
    if (total > TETO_DO_PEDIDO) {
      throw new Error("As fotos ainda estão pesadas demais para o servidor. Tire de novo, mais de perto e com menos zoom.");
    }
  }

  document.querySelectorAll('form[enctype="multipart/form-data"]').forEach((form) => {
    form.addEventListener("submit", async (event) => {
      if (form.dataset.compressed === "1") return;
      const requiredEmpty = Array.from(form.querySelectorAll('input[type="file"][required]')).filter(
        (input) => !input.files || input.files.length === 0
      );
      if (requiredEmpty.length) return;
      const hasImage = Array.from(form.querySelectorAll('input[type="file"]')).some((input) =>
        Array.from(input.files || []).some((file) => file.type.startsWith("image/"))
      );
      if (!hasImage) return;
      event.preventDefault();
      const button = form.querySelector('button[type="submit"], input[type="submit"]');
      const label = button && (button.tagName === "BUTTON" ? button.textContent : button.value);
      if (button) {
        button.disabled = true;
        if (button.tagName === "BUTTON") button.textContent = "Comprimindo fotos…";
      }
      try {
        await compressForm(form);
        form.dataset.compressed = "1";
        form.submit();
      } catch (err) {
        window.alert(err.message || "Não foi possível preparar as fotos.");
        if (button) {
          button.disabled = false;
          if (button.tagName === "BUTTON" && label) button.textContent = label;
        }
      }
    });
  });
})();
