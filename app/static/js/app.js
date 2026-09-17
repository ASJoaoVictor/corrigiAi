'use strict';
const photo = document.querySelector('#photo');
let objectURL;
photo?.addEventListener('change', () => {
  const preview = document.querySelector('#local-preview');
  if (objectURL) URL.revokeObjectURL(objectURL);
  const file = photo.files[0];
  preview.hidden = !file;
  if (file) { objectURL = URL.createObjectURL(file); preview.src = objectURL; }
});
document.querySelectorAll('form[data-processing]').forEach(form => form.addEventListener('submit', () => {
  form.querySelector('button').disabled = true;
  document.querySelector('#loading').hidden = false;
}));
window.addEventListener('pageshow', () => {
  document.querySelector('#loading').hidden = true;
  document.querySelectorAll('form[data-processing] button').forEach(b => b.disabled = false);
});
const review = document.querySelector('#review-form');
function updateScore() {
  let score = 0;
  document.querySelectorAll('.answer').forEach(row => {
    const value = row.querySelector('input:checked')?.value || 'keep';
    const correct = value === row.dataset.key;
    if (correct) score++;
    row.querySelector('.verdict').textContent = correct ? '✓ Acerto' : '✗ Erro';
    const status = value === 'blank' ? 'blank' : 'detected';
    const manual = value !== 'keep' && ((value === 'blank' ? '' : value) !== row.dataset.original || status !== row.dataset.originalStatus);
    row.querySelector('.manual').textContent = manual ? '· Correção manual' : '';
  });
  document.querySelector('#score').textContent = `${score} / 30 acertos`;
}
review?.addEventListener('change', updateScore);
function validCPF(cpf) {
  if (!/^[0-9]{11}$/.test(cpf) || new Set(cpf).size === 1) return false;
  return [9,10].every(size => {
    let total = 0;
    for (let i=0;i<size;i++) total += Number(cpf[i])*(size+1-i);
    const digit = (total*10)%11;
    return (digit===10 ? 0 : digit) === Number(cpf[size]);
  });
}
document.querySelector('#cpf')?.addEventListener('input', event => {
  const cpf = event.target.value.replace(/[^0-9]/g,'');
  document.querySelector('#cpf-status').textContent = validCPF(cpf) ? 'CPF válido' : 'CPF inválido — confira os dígitos';
});
