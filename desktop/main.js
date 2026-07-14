const { app, BrowserWindow, ipcMain, shell } = require('electron');
const fs = require('fs');
const path = require('path');

app.setName('放置天堂-蛇神降世');
app.setAppUserModelId('tw.cheng.idle-lineage.snake-god');

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) app.quit();

let storeDir;
function storePath(key) {
  const safe = Buffer.from(String(key), 'utf8').toString('base64url');
  return path.join(storeDir, `${safe}.dat`);
}

function registerFileStore() {
  storeDir = path.join(app.getPath('userData'), 'filestore');
  fs.mkdirSync(storeDir, { recursive: true });
  ipcMain.on('fable-store', (event, request = {}) => {
    try {
      const file = storePath(request.key);
      if (request.action === 'get') {
        event.returnValue = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : null;
      } else if (request.action === 'has') {
        event.returnValue = fs.existsSync(file);
      } else if (request.action === 'set') {
        const temp = `${file}.${process.pid}.${Date.now()}.tmp`;
        fs.writeFileSync(temp, String(request.value), 'utf8');
        fs.renameSync(temp, file);
        event.returnValue = true;
      } else if (request.action === 'remove') {
        fs.rmSync(file, { force: true });
        event.returnValue = true;
      } else {
        event.returnValue = null;
      }
    } catch (error) {
      console.error('File store error:', error);
      event.returnValue = request.action === 'get' ? null : false;
    }
  });
}

function createWindow() {
  const win = new BrowserWindow({
    title: '放置天堂 - 蛇神降世',
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    icon: path.join(__dirname, '..', 'assets', 'app-icon.png'),
    backgroundColor: '#090b10',
    autoHideMenuBar: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });

  // 將頁面端錯誤同步到啟動終端，方便診斷 index.html 載入後介面中斷。
  win.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    if (level >= 2) console.error(`[renderer] ${message} (${sourceId}:${line})`);
  });
  win.webContents.on('render-process-gone', (_event, details) => console.error('[renderer-gone]', details));

  win.once('ready-to-show', () => win.show());
  win.loadFile(path.join(__dirname, '..', 'index.html'));
}

app.whenReady().then(() => {
  registerFileStore();
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('second-instance', () => {
  createWindow();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
