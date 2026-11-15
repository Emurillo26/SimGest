/*
 * Modo oscuro: cambia entre tema claro y oscuro y recuerda la elección.
 * El tema inicial ya lo aplica el script de _tema.html antes de pintar la
 * página (así no parpadea); este archivo solo maneja el botón.
 */
(function () {
  var CLAVE = 'simgest-tema';
  var raiz = document.documentElement;

  function aplicar(tema) {
    raiz.setAttribute('data-tema', tema);
    raiz.setAttribute('data-bs-theme', tema === 'oscuro' ? 'dark' : 'light');
    document.querySelectorAll('.boton-tema').forEach(function (boton) {
      var oscuro = tema === 'oscuro';
      boton.setAttribute('aria-pressed', String(oscuro));
      boton.setAttribute('aria-label', oscuro ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro');
      var texto = boton.querySelector('.texto-tema');
      if (texto) texto.textContent = oscuro ? 'Modo claro' : 'Modo oscuro';
    });
  }

  function alternar() {
    var nuevo = raiz.getAttribute('data-tema') === 'oscuro' ? 'claro' : 'oscuro';
    try { localStorage.setItem(CLAVE, nuevo); } catch (e) { /* sin almacenamiento: dura solo esta página */ }
    aplicar(nuevo);
  }

  var ICONOS =
    '<svg class="icono-luna" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>' +
    '<svg class="icono-sol" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';

  document.addEventListener('DOMContentLoaded', function () {
    // Pantallas sin barra lateral (inicio de sesión, registro…): botón flotante.
    if (!document.querySelector('.boton-tema')) {
      var flotante = document.createElement('button');
      flotante.type = 'button';
      flotante.className = 'boton-tema flotante';
      flotante.innerHTML = ICONOS + '<span class="texto-tema"></span>';
      document.body.appendChild(flotante);
    }
    document.querySelectorAll('.boton-tema').forEach(function (boton) {
      boton.addEventListener('click', alternar);
    });
    aplicar(raiz.getAttribute('data-tema') || 'claro');
  });
})();
