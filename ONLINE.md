# 線上網頁版

本專案可透過 GitHub Pages 直接執行，不需要 Electron 或本機伺服器。

- 網頁入口：`index.html`
- 線上存檔：瀏覽器 `localStorage`
- 自動部署：推送到 `online-web` 後由 `.github/workflows/pages.yml` 發佈
- 部署內容：`index.html`、`js/`、`css/`、`assets/`、`public/`
- 不部署：`desktop/`、`dist/`、`node_modules/`、`backups/`

同一個瀏覽器與同一個網址會保留存檔。清除網站資料、使用無痕模式或更換瀏覽器不會自動帶入舊存檔，請使用遊戲內的匯出功能備份。
