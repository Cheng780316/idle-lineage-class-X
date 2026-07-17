const { contextBridge, ipcRenderer } = require('electron');

function call(action, key, value) {
  return ipcRenderer.sendSync('fable-store', { action, key, value });
}

contextBridge.exposeInMainWorld('fableStore', Object.freeze({
  get(key) { return call('get', key); },
  has(key) { return call('has', key); },
  set(key, value) { return call('set', key, value); },
  remove(key) { return call('remove', key); }
}));

// EXE 專用獎勵倍率。網頁版不載入 preload，會改用 js/00-data.js 的 DEFAULT_WEB_REWARD_RATES。
contextBridge.exposeInMainWorld('fableDesktopRates', Object.freeze({
  exp: 10,
  gold: 10,
  drop: 5
}));
