(function () {
  const form = document.getElementById("checklist-form");
  if (!form) return;

  const inputs = Array.from(form.querySelectorAll('.photo-slots input[type="file"]'));
  const counter = document.querySelector('[data-photos="counter"]');

  function refresh() {
    const filled = inputs.filter((input) => input.files && input.files.length > 0);
    counter.textContent = `${filled.length}/${inputs.length}`;
    counter.classList.toggle("complete", filled.length === inputs.length);
  }

  function preview(input) {
    const slot = input.closest(".slot");
    const file = input.files && input.files[0];
    slot.querySelector("img")?.remove();
    if (!file) return;
    const image = document.createElement("img");
    image.alt = "";
    image.src = URL.createObjectURL(file);
    image.addEventListener("load", () => URL.revokeObjectURL(image.src), { once: true });
    slot.appendChild(image);
  }

  inputs.forEach((input) =>
    input.addEventListener("change", () => {
      preview(input);
      refresh();
    })
  );
  refresh();

  if ("geolocation" in navigator) {
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const set = (id, value) => {
          const field = document.getElementById(id);
          if (field) field.value = value;
        };
        set("id_lat", coords.latitude);
        set("id_lng", coords.longitude);
        set("id_accuracy", coords.accuracy);
      },
      () => {},
      { enableHighAccuracy: true, timeout: 15000 }
    );
  }

  form.addEventListener("submit", (event) => {
    const missing = inputs.filter((input) => !input.files || input.files.length === 0);
    if (missing.length === 0) return;
    event.preventDefault();
    missing[0].closest(".slot").scrollIntoView({ behavior: "smooth", block: "center" });
    missing.forEach((input) => input.closest(".slot").classList.add("has-error"));
    counter.classList.add("missing");
  });
})();
