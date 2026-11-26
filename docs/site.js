'use strict';
const samples = {
  review: '按严重程度列出问题，附上文件位置和触发条件。等我确认后再改。',
  verify: '列出跑过的检查、结果，以及还没验证的部分。',
  discuss: '先梳理使用场景和需要我决定的问题，确认后再讨论界面。'
};
const draft = document.querySelector('#draft');
const status = document.querySelector('#demo-state');
const original = draft.value;
const markers = document.querySelectorAll('.append');
function clearMarkers() {
  for (const marker of markers) marker.textContent = '↵';
}
for (const button of document.querySelectorAll('[data-sample]')) {
  button.addEventListener('click', () => {
    clearMarkers();
    button.querySelector('.append').textContent = '已追加 ✓';
    draft.value += (draft.value ? '\n\n' : '') + samples[button.dataset.sample];
    draft.scrollTop = draft.scrollHeight;
    status.textContent = '已追加到演示草稿';
  });
}
document.querySelector('#reset').onclick = () => {
  clearMarkers();
  draft.value = original;
  draft.scrollTop = 0;
  status.textContent = '演示草稿已重置';
};
const copy = document.querySelector('#copy');
let timer;
copy.onclick = async () => {
  const code = document.querySelector('#commands');
  try {
    await navigator.clipboard.writeText(code.textContent);
    copy.textContent = '已复制';
  } catch {
    const range = document.createRange();
    range.selectNodeContents(code);
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    copy.textContent = '已选中，请手动复制';
  }
  clearTimeout(timer);
  timer = setTimeout(() => { copy.textContent = '复制命令'; }, 2500);
};
