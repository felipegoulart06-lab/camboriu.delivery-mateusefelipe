(function () {
  const configNode = document.getElementById("tracking-config");
  const mapNode = document.getElementById("tracking-map");
  if (!configNode || !mapNode || typeof L === "undefined") return;

  const config = JSON.parse(configNode.textContent);
  const map = L.map(mapNode).setView(config.center, 13);
  L.tileLayer(config.tileUrl, { attribution: config.attribution, maxZoom: 19 }).addTo(map);

  const field = (name) => document.querySelector(`[data-tracking="${name}"]`);
  const trail = L.polyline([], { color: "#0f7866", weight: 4, opacity: 0.7 }).addTo(map);
  const pin = (color) =>
    L.divIcon({ className: "map-pin", html: `<span style="--pin:${color}"></span>`, iconSize: [18, 18] });

  let driverMarker = null;
  let framed = false;

  function place(point, color, label) {
    if (!point) return null;
    return L.marker([point.lat, point.lng], { icon: pin(color), title: label })
      .addTo(map)
      .bindTooltip(`${label}<br>${point.label}`);
  }

  function frame(points) {
    if (framed || points.length === 0) return;
    map.fitBounds(L.latLngBounds(points).pad(0.25), { maxZoom: 16 });
    framed = true;
  }

  function render(data) {
    field("status").textContent = data.status_label;
    field("status").className = `badge ${data.status}`;

    const anchors = [];
    if (!render.staticDone) {
      const pickup = place(data.pickup, "#0f7866", "Coleta");
      const destination = place(data.destination, "#a13b3b", "Entrega");
      if (pickup) anchors.push(pickup.getLatLng());
      if (destination) anchors.push(destination.getLatLng());
      render.staticDone = true;
      render.anchors = anchors;
    }

    if (!data.trackable || !data.driver) {
      field("note").textContent = data.checklist_done
        ? "Corrida encerrada. O rastreio fica disponível apenas durante a execução."
        : "Aguardando a central acionar e o entregador aceitar a corrida.";
      frame(render.anchors || []);
      return;
    }

    field("driver").textContent = data.driver.name;

    if (data.driver.lat === null || data.driver.lng === null) {
      field("note").textContent = "Entregador designado. O mapa liga quando o aparelho dele enviar a primeira posição.";
      frame(render.anchors || []);
      return;
    }

    const position = [data.driver.lat, data.driver.lng];
    if (driverMarker) {
      driverMarker.setLatLng(position);
    } else {
      driverMarker = L.marker(position, { icon: pin("#13231e"), title: data.driver.name })
        .addTo(map)
        .bindTooltip(`${data.driver.name}<br>${data.driver.vehicle || "veículo não informado"}`);
    }
    trail.setLatLngs(data.trail.length ? data.trail : [position]);

    const moment = data.driver.updated_at ? new Date(data.driver.updated_at) : null;
    field("updated").textContent = moment ? moment.toLocaleTimeString("pt-BR") : "aguardando sinal";
    field("note").textContent = data.driver.stale
      ? "Sinal fraco: a última posição tem mais de alguns minutos. A central já acompanha."
      : "Posição ao vivo do entregador.";

    frame([...(render.anchors || []), L.latLng(position)]);
  }

  async function refresh() {
    try {
      const response = await fetch(config.dataUrl, { headers: { "X-Requested-With": "fetch" } });
      if (!response.ok) return;
      render(await response.json());
    } catch (error) {
      field("note").textContent = "Sem conexão com o servidor. Tentando novamente.";
    }
  }

  refresh();
  setInterval(refresh, Math.max(config.refreshSeconds, 5) * 1000);
})();
