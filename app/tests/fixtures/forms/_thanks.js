// Shared by fixtures: validate required fields like a real ATS, then show a confirmation page.
function wireSubmit(formId) {
  document.getElementById(formId).addEventListener("submit", (e) => {
    e.preventDefault();
    const missing = [...document.querySelectorAll("[required]")].filter((el) =>
      el.type === "radio" || el.type === "checkbox"
        ? !document.querySelector(`[name="${el.name}"]:checked`)
        : !el.value
    ).concat([...document.querySelectorAll("[role=combobox][aria-required=true]")].filter((el) => !el.dataset.chosen));
    if (missing.length) { document.getElementById("errors").textContent = "Please complete required fields"; return; }
    window.__submitted = Object.fromEntries(new FormData(e.target).entries());
    document.body.innerHTML = "<h1>Thank you for applying!</h1><p>Your application has been submitted.</p>";
  });
}
