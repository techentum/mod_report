const autosaveForms = document.querySelectorAll(".autosave-form");

autosaveForms.forEach((form) => {
  let timeoutId = null;

  const scheduleSave = () => {
    if (!form.dataset.saveUrl) {
      return;
    }
    if (timeoutId) {
      window.clearTimeout(timeoutId);
    }
    timeoutId = window.setTimeout(() => {
      const payload = new FormData(form);
      fetch(form.dataset.saveUrl, {
        method: "POST",
        headers: { "X-Requested-With": "fetch" },
        body: payload,
      }).catch(() => {});
    }, 800);
  };

  form.addEventListener("input", scheduleSave);
  form.addEventListener("change", scheduleSave);
});
