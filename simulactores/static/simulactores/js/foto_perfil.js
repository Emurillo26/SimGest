/*
 * Foto de perfil, al estilo de las apps de mensajería:
 *  - Al tocar la foto se abre un menú: Ver foto, Tomar foto, Subir foto y Quitar foto.
 *  - Antes de subirla, la foto se acomoda dentro de un círculo: se arrastra y se hace
 *    zoom con la rueda del mouse, pellizcando con los dedos o con los botones + y −.
 *  - "Tomar foto" usa la cámara de la computadora; en el celular abre su cámara.
 * Usa Cropper.js. Si no carga, la foto se sube tal cual y el servidor la recorta al centro.
 */
(function () {
  var boton = document.getElementById('boton-foto');
  var menu = document.getElementById('menu-foto');
  var entrada = document.getElementById('id_foto');
  var entradaCamara = document.getElementById('id_foto_camara');
  var dialogo = document.getElementById('dialogo-foto');
  var dialogoCamara = document.getElementById('dialogo-camara');
  var dialogoVer = document.getElementById('dialogo-ver-foto');
  var dialogoQuitar = document.getElementById('dialogo-quitar-foto');
  if (!boton || !menu || !entrada || !dialogo) return;

  var imagen = document.getElementById('imagen-recorte');
  var guardar = document.getElementById('guardar-recorte');
  var video = document.getElementById('video-camara');
  var cropper = null;
  var urlTemporal = null;
  var flujo = null;
  var zoomMinimo = 1;
  var ZOOM_MAXIMO = 4; // veces el tamaño en que la imagen llena el círculo

  var puedeRecortar = typeof Cropper !== 'undefined' && typeof dialogo.showModal === 'function';

  /* ---------- Menú ---------- */
  function abrirMenu() {
    menu.hidden = false;
    boton.setAttribute('aria-expanded', 'true');
    var primero = menu.querySelector('[role="menuitem"]');
    if (primero) primero.focus();
  }
  function cerrarMenu(devolverFoco) {
    if (menu.hidden) return;
    menu.hidden = true;
    boton.setAttribute('aria-expanded', 'false');
    if (devolverFoco) boton.focus();
  }
  boton.addEventListener('click', function (e) {
    e.stopPropagation();
    menu.hidden ? abrirMenu() : cerrarMenu(false);
  });
  document.addEventListener('click', function (e) {
    if (!menu.contains(e.target)) cerrarMenu(false);
  });
  menu.addEventListener('keydown', function (e) {
    var opciones = Array.prototype.slice.call(menu.querySelectorAll('[role="menuitem"]'));
    var i = opciones.indexOf(document.activeElement);
    if (e.key === 'Escape') { e.preventDefault(); cerrarMenu(true); }
    if (e.key === 'ArrowDown') { e.preventDefault(); opciones[(i + 1) % opciones.length].focus(); }
    if (e.key === 'ArrowUp') { e.preventDefault(); opciones[(i - 1 + opciones.length) % opciones.length].focus(); }
  });

  menu.addEventListener('click', function (e) {
    var opcion = e.target.closest('[data-accion]');
    if (!opcion) return;
    var accion = opcion.dataset.accion;
    cerrarMenu(false);
    if (accion === 'quitar' && dialogoQuitar) dialogoQuitar.showModal();
    if (accion === 'ver' && dialogoVer) dialogoVer.showModal();
    if (accion === 'subir') entrada.click();
    if (accion === 'tomar') tomarFoto();
  });

  /* ---------- Quitar foto: confirmación con el estilo del sistema ---------- */
  if (dialogoQuitar) {
    document.getElementById('cancelar-quitar-foto').addEventListener('click', function () { dialogoQuitar.close(); boton.focus(); });
    dialogoQuitar.addEventListener('click', function (e) { if (e.target === dialogoQuitar) dialogoQuitar.close(); });
  }

  /* ---------- Ver foto ---------- */
  if (dialogoVer) {
    document.getElementById('cerrar-ver-foto').addEventListener('click', function () { dialogoVer.close(); });
    dialogoVer.addEventListener('click', function (e) { if (e.target === dialogoVer) dialogoVer.close(); });
  }

  /* ---------- Recortar ---------- */
  function abrirRecorte(archivo) {
    if (!puedeRecortar) { subir(archivo); return; }
    if (urlTemporal) URL.revokeObjectURL(urlTemporal);
    if (cropper) { cropper.destroy(); cropper = null; }
    urlTemporal = URL.createObjectURL(archivo);
    imagen.src = urlTemporal;
    if (!dialogo.open) dialogo.showModal();

    cropper = new Cropper(imagen, {
      aspectRatio: 1,
      viewMode: 1,              // la imagen siempre cubre el círculo
      dragMode: 'move',         // se arrastra la foto, no el círculo
      autoCropArea: 0.9,
      cropBoxMovable: false,
      cropBoxResizable: false,
      toggleDragModeOnDblclick: false,
      zoomOnWheel: true,        // rueda del mouse
      zoomOnTouch: true,        // pellizcar con los dedos
      wheelZoomRatio: 0.08,
      guides: false,
      center: false,
      highlight: false,
      background: false,
      ready: function () {
        // Centra el círculo y guarda el zoom con que la imagen lo llena justo.
        var contenedor = cropper.getContainerData();
        var lado = Math.min(contenedor.width, contenedor.height) * 0.9;
        cropper.setCropBoxData({ left: (contenedor.width - lado) / 2, top: (contenedor.height - lado) / 2, width: lado, height: lado });
        var datos = cropper.getImageData();
        zoomMinimo = datos.width / datos.naturalWidth;
      },
      zoom: function (e) {
        if (e.detail.ratio > zoomMinimo * ZOOM_MAXIMO) e.preventDefault();
      }
    });
  }

  function cerrarRecorte() {
    if (cropper) { cropper.destroy(); cropper = null; }
    if (urlTemporal) { URL.revokeObjectURL(urlTemporal); urlTemporal = null; }
    entrada.value = '';
    if (entradaCamara) entradaCamara.value = '';
    guardar.disabled = false;
    if (dialogo.open) dialogo.close();
  }

  function subir(archivo) {
    var lista = new DataTransfer();
    lista.items.add(archivo);
    entrada.files = lista.files;
    entrada.form.submit();
  }

  entrada.addEventListener('change', function () {
    var archivo = entrada.files[0];
    if (!archivo) return;
    // Un archivo que no es imagen lo rechaza el servidor con su mensaje.
    if (!/^image\//.test(archivo.type)) { entrada.form.submit(); return; }
    abrirRecorte(archivo);
  });
  if (entradaCamara) {
    entradaCamara.addEventListener('change', function () {
      if (entradaCamara.files[0]) abrirRecorte(entradaCamara.files[0]);
    });
  }

  document.getElementById('zoom-mas').addEventListener('click', function () { if (cropper) cropper.zoom(0.15); });
  document.getElementById('zoom-menos').addEventListener('click', function () { if (cropper) cropper.zoom(-0.15); });
  document.getElementById('otra-foto').addEventListener('click', function () { entrada.click(); });
  document.getElementById('cancelar-recorte').addEventListener('click', cerrarRecorte);
  dialogo.addEventListener('cancel', function (e) { e.preventDefault(); cerrarRecorte(); }); // tecla Escape

  guardar.addEventListener('click', function () {
    if (!cropper) return;
    guardar.disabled = true;
    cropper.getCroppedCanvas({ width: 600, height: 600, imageSmoothingQuality: 'high', fillColor: '#fff' })
      .toBlob(function (blob) {
        subir(new File([blob], 'foto.jpg', { type: 'image/jpeg' }));
      }, 'image/jpeg', 0.9);
  });

  /* ---------- Tomar foto ---------- */
  function apagarCamara() {
    if (flujo) { flujo.getTracks().forEach(function (pista) { pista.stop(); }); flujo = null; }
    if (dialogoCamara && dialogoCamara.open) dialogoCamara.close();
  }

  function avisar(texto) {
    var aviso = document.getElementById('aviso-foto');
    if (!aviso) return;
    aviso.textContent = texto;
    aviso.hidden = false;
    clearTimeout(avisar.temporizador);
    avisar.temporizador = setTimeout(function () { aviso.hidden = true; }, 7000);
  }

  function tomarFoto() {
    // En el celular, su propia app de cámara es lo más confiable.
    var esCelular = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
    if (esCelular && entradaCamara) { entradaCamara.click(); return; }

    var hayCamaraWeb = navigator.mediaDevices && navigator.mediaDevices.getUserMedia && dialogoCamara && puedeRecortar;
    if (!hayCamaraWeb) {
      avisar('Este navegador no permite usar la cámara. Prueba con Chrome, Edge o Firefox, o usa «Subir foto».');
      return;
    }
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 1280 } }, audio: false })
      .then(function (s) {
        flujo = s;
        video.srcObject = s;
        dialogoCamara.showModal();
      })
      .catch(function (error) {
        var sinPermiso = error && (error.name === 'NotAllowedError' || error.name === 'SecurityError');
        avisar(sinPermiso
          ? 'No se pudo acceder a la cámara. Revisa que el navegador tenga permiso para usarla.'
          : 'No se encontró una cámara disponible. Puedes usar «Subir foto».');
      });
  }

  if (dialogoCamara) {
    document.getElementById('cancelar-camara').addEventListener('click', apagarCamara);
    dialogoCamara.addEventListener('cancel', function (e) { e.preventDefault(); apagarCamara(); });
    document.getElementById('capturar-camara').addEventListener('click', function () {
      var lienzo = document.createElement('canvas');
      lienzo.width = video.videoWidth;
      lienzo.height = video.videoHeight;
      var ctx = lienzo.getContext('2d');
      ctx.translate(lienzo.width, 0); // como espejo, igual que se ve en pantalla
      ctx.scale(-1, 1);
      ctx.drawImage(video, 0, 0);
      apagarCamara();
      lienzo.toBlob(function (blob) {
        abrirRecorte(new File([blob], 'camara.jpg', { type: 'image/jpeg' }));
      }, 'image/jpeg', 0.92);
    });
  }
})();
