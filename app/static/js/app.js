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
// Decode with browser EXIF orientation, preserve aspect ratio and keep OCR detail.
async function compressPhoto(file) {
  let source;
  let url;
  try {
    if (typeof createImageBitmap === 'function') {
      source = await createImageBitmap(file, {imageOrientation: 'from-image'});
    } else {
      url = URL.createObjectURL(file);
      source = new Image();
      source.src = url;
      await new Promise((resolve, reject) => {
        source.onload = resolve;
        source.onerror = reject;
      });
    }
    const scale = Math.min(1, 2000 / Math.max(source.width, source.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(source.width * scale));
    canvas.height = Math.max(1, Math.round(source.height * scale));
    const context = canvas.getContext('2d');
    context.fillStyle = '#fff';
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(source, 0, 0, canvas.width, canvas.height);
    for (const quality of [0.92, 0.87, 0.82]) {
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', quality));
      if (blob && blob.size <= 3.5 * 1024 * 1024) {
        return new File([blob], 'cartao.jpg', {type: 'image/jpeg'});
      }
    }
    throw new Error('A foto ainda está grande demais. Tire outra foto com menor resolução, mantendo os números e bolhas nítidos.');
  } finally {
    source?.close?.();
    if (url) URL.revokeObjectURL(url);
  }
}
photo?.form.addEventListener('submit', async event => {
  event.preventDefault();
  const form = photo.form;
  const button = form.querySelector('button');
  if (button.disabled) return;
  const status = document.querySelector('#photo-status');
  button.disabled = true;
  photo.disabled = true;
  status.textContent = 'Preparando foto para envio…';
  try {
    const file = await compressPhoto(photo.files[0]);
    const transfer = new DataTransfer();
    transfer.items.add(file);
    photo.files = transfer.files;
    photo.disabled = false;
    if (objectURL) URL.revokeObjectURL(objectURL);
    objectURL = URL.createObjectURL(file);
    document.querySelector('#local-preview').src = objectURL;
    status.textContent = 'Enviando foto…';
    HTMLFormElement.prototype.submit.call(form);
  } catch (error) {
    status.textContent = error.message?.startsWith('A foto ainda') ? error.message :
      'Não foi possível preparar a foto. Selecione uma imagem JPEG, PNG ou WebP válida e tente novamente.';
    button.disabled = false;
    photo.disabled = false;
  }
});
document.querySelectorAll('form[data-processing]').forEach(form => form.addEventListener('submit', () => {
  form.querySelector('button').disabled = true;
  document.querySelector('#loading').hidden = false;
}));
window.addEventListener('pageshow', () => {
  document.querySelector('#loading').hidden = true;
  if (photo) {
    photo.disabled = false;
    photo.form.querySelector('button').disabled = false;
  }
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
