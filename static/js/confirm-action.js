(function () {
  const dialog = document.getElementById("confirm-dialog");
  if (!dialog) return;

  const text = dialog.querySelector("[data-confirm-text]");
  const ok = dialog.querySelector("[data-confirm-ok]");
  const cancel = dialog.querySelector("[data-confirm-cancel]");
  let pending = null;

  function close() {
    pending = null;
    dialog.close();
  }

  document.addEventListener("submit", function (event) {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    const message = form.getAttribute("data-confirm");
    if (!message || form.dataset.confirmed === "1") return;
    event.preventDefault();
    pending = form;
    text.textContent = message;
    ok.textContent = form.getAttribute("data-confirm-ok") || "Sim, confirmar";
    dialog.showModal();
  });

  cancel.addEventListener("click", close);

  ok.addEventListener("click", function () {
    if (!pending) return;
    const form = pending;
    if (!form.querySelector('input[name="confirm"]')) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "confirm";
      input.value = "1";
      form.appendChild(input);
    } else {
      form.querySelector('input[name="confirm"]').value = "1";
    }
    form.dataset.confirmed = "1";
    dialog.close();
    pending = null;
    form.requestSubmit();
  });

  dialog.addEventListener("cancel", function () {
    pending = null;
  });
})();
