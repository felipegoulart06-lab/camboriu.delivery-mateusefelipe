(function () {
  const node = document.getElementById("tracker");
  if (!node) return;

  const url = node.dataset.pingUrl;
  const csrf = node.dataset.csrf;
  const interval = Math.max(parseInt(node.dataset.interval, 10) || 15, 5) * 1000;
  const state = node.querySelector('[data-tracker="state"]');
  const detail = node.querySelector('[data-tracker="detail"]');

  if (!("geolocation" in navigator)) {
    state.textContent = "Este aparelho não informa localização";
    detail.textContent = "Avise a central para acompanhar por telefone.";
    return;
  }

  let sending = false;

  async function send(position) {
    if (sending) return;
    sending = true;
    const { latitude, longitude, accuracy, speed, heading } = position.coords;
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ lat: latitude, lng: longitude, accuracy, speed, heading }),
      });
      if (response.ok) {
        node.classList.add("live");
        state.textContent = "Rastreio ligado";
        detail.textContent = `Posição enviada às ${new Date().toLocaleTimeString("pt-BR")}.`;
      } else {
        node.classList.remove("live");
        const data = await response.json().catch(() => ({}));
        state.textContent = "Rastreio pausado";
        detail.textContent = data.reason || "A central já foi avisada.";
      }
    } catch (error) {
      node.classList.remove("live");
      state.textContent = "Sem internet";
      detail.textContent = "Vamos tentar novamente em alguns segundos.";
    } finally {
      sending = false;
    }
  }

  function fail(error) {
    node.classList.remove("live");
    state.textContent = "Localização bloqueada";
    detail.textContent =
      error.code === error.PERMISSION_DENIED
        ? "Libere a localização no navegador para a empresa ver sua chegada."
        : "Não foi possível obter o GPS agora.";
  }

  const options = { enableHighAccuracy: true, timeout: 20000, maximumAge: 5000 };
  navigator.geolocation.getCurrentPosition(send, fail, options);
  setInterval(() => navigator.geolocation.getCurrentPosition(send, fail, options), interval);
})();
