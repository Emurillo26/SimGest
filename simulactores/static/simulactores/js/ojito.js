function alternarPassword(idCampo, boton) {
  const campo = document.getElementById(idCampo);
  const mostrando = campo.type === 'text';
  campo.type = mostrando ? 'password' : 'text';
  boton.textContent = mostrando ? '👁' : '🙈';
}
