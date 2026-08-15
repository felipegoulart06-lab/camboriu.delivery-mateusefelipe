(function () {
  const url = document.body && document.body.dataset.liveAlerts;
  if (!url) return;

  const STORAGE_KEY = "camboriu-live-alerts";
  const POLL_MS = 4000;
  let lastId = Number(sessionStorage.getItem(STORAGE_KEY) || 0);
  let primed = false;

  function badge(name, count) {
    const node = document.querySelector(`[data-live-badge="${name}"]`);
    if (!node) return;
    const value = Number(count) || 0;
    node.textContent = value;
    node.hidden = value <= 0;
  }

  function chime() {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const now = ctx.currentTime;
    const master = ctx.createGain();
    master.gain.setValueAtTime(0.0001, now);
    master.gain.exponentialRampToValueAtTime(0.05, now + 0.02);
    master.gain.exponentialRampToValueAtTime(0.0001, now + 1.1);
    master.connect(ctx.destination);
    [784, 988].forEach((freq, index) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.7 / (index + 1), now);
      osc.connect(gain);
      gain.connect(master);
      osc.start(now + index * 0.08);
      osc.stop(now + 1.15);
    });
    setTimeout(() => ctx.close(), 1400);
  }

  function desktop(item) {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    try {
      new Notification(item.title || "SC Transporte Executivo", {
        body: "Há uma atualização no painel.",
        tag: `aviso-${item.id}`,
        silent: true,
      });
    } catch (error) {
      /* Safari privado e similares ignoram o aviso do sistema. */
    }
  }

  function apply(data) {
    badge("notifications", data.unread);
    badge("incoming", data.incoming);
    const newest = Number(data.latest_id) || 0;
    if (!primed) {
      lastId = newest;
      sessionStorage.setItem(STORAGE_KEY, String(lastId));
      primed = true;
      return;
    }
    const fresh = (data.items || []).filter((item) => item.id > lastId);
    if (fresh.length) {
      chime();
      desktop(fresh[fresh.length - 1]);
      lastId = newest;
      sessionStorage.setItem(STORAGE_KEY, String(lastId));
    }
  }

  async function tick() {
    try {
      const response = await fetch(`${url}?after=${lastId}`, {
        headers: { "X-Requested-With": "fetch" },
        credentials: "same-origin",
      });
      if (!response.ok) return;
      apply(await response.json());
    } catch (error) {
      /* Sem conexão: tenta de novo no próximo ciclo. */
    }
  }

  document.addEventListener("click", () => {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
  }, { once: true });

  tick();
  setInterval(tick, POLL_MS);
})();
