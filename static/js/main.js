// Menu mobile du site public + confirmation des actions sensibles.
document.addEventListener("DOMContentLoaded", function () {
  var bouton = document.querySelector("[data-menu]");
  var nav = document.querySelector("[data-nav]");
  if (bouton && nav) {
    bouton.addEventListener("click", function () {
      var ouvert = nav.classList.toggle("ouvert");
      bouton.setAttribute("aria-expanded", ouvert ? "true" : "false");
    });
  }
  document.querySelectorAll("[data-confirmer]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.dataset.confirmer)) {
        e.preventDefault();
      }
    });
  });
});
