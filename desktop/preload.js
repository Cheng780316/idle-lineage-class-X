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

// EXE 專用獎勵倍率。網頁版不會載入 preload，因此仍維持原本的 1 倍。
contextBridge.exposeInMainWorld('fableDesktopRates', Object.freeze({
  exp: 100,
  gold: 10,
  drop: 5
}));
