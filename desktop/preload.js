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
