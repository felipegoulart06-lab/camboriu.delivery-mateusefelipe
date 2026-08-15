(() => {
  const toggle = document.querySelector(".menu-toggle");
  const backdrop = document.querySelector("[data-close-menu]");
  if (!toggle) return;

  const setOpen = (open) => {
    document.body.classList.toggle("nav-open", open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu");
    if (backdrop) backdrop.hidden = !open;
  };

  toggle.addEventListener("click", () => setOpen(!document.body.classList.contains("nav-open")));
  backdrop?.addEventListener("click", () => setOpen(false));
  document.querySelectorAll(".top nav a, .sidebar nav a").forEach((link) => {
    link.addEventListener("click", () => setOpen(false));
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setOpen(false);
  });
  window.addEventListener("resize", () => {
    if (window.matchMedia("(min-width: 900px)").matches) setOpen(false);
  });
})();
