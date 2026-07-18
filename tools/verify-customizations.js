const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');
const files = {
  index: read('index.html'),
  data: read('js/00-data.js'),
  drops: read('js/01-drops-config.js'),
  stats: read('js/02-stats-recompute.js'),
  items: read('js/08-items-equip.js'),
  skills: read('js/07-skills-cast.js'),
  world: read('js/11-world-map.js'),
  save: read('js/13-shop-save.js'),
  dex: read('js/25-afk-dex.js'),
  wiki: read('js/26-afk-wiki.js')
};

const failures = [];
function expect(label, ok) {
  if (!ok) failures.push(label);
}
function has(file, fragment, label) {
  expect(label, files[file].includes(fragment));
}
function lacks(file, fragment, label) {
  expect(label, !files[file].includes(fragment));
}

const version = '20260719-custom-restore1';
const assetVersions = [...files.index.matchAll(/(?:href|src)="(?:css|js)\/[^"]+\?v=([^"]+)"/g)].map((m) => m[1]);
expect('網頁資源必須全部使用本次快取版本', assetVersions.length >= 30 && assetVersions.every((v) => v === version));

has('data', 'DEFAULT_WEB_REWARD_RATES = Object.freeze({ exp: 10, gold: 10, drop: 5 })', '網頁倍率必須是經驗10／金幣10／掉落5');
expect('三種古代藥水都必須無喝水延遲', (files.data.match(/potion_ancient_[\s\S]{0,360}?noPotionDelay: true/g) || []).length === 3);
has('skills', "{ id: 'set-magicbarrier', pot: 'scroll_magicbarrier', b: 'sk_magic_shield', buyThreshold: 1, buyQty: 5 }", '魔法屏障卷軸必須在剩1張時自購5張');
has('skills', '(!buyChk || buyChk.checked)', '合併後自動化介面不可因舊購買勾選框不存在而失效');
expect('新角色與舊存檔重置清單必須包含三個補回的自動化選項', (files.save.match(/set-elfcookie[^\n]+set-magicbarrier[^\n]+set-teleport/g) || []).length === 2);

has('world', "wpn: { result: 'new_item_bless_wpn', rate: 30, req: [{ id: 'scroll_weapon', cnt: 500 }, { id: 'sherine_crystal', cnt: 5 }, { id: 'gold', cnt: 5000000 }] }", '碧恩武器祝福卷軸配方不可被上游覆蓋');
has('world', "arm: { result: 'new_item_bless_arm', rate: 30, req: [{ id: 'scroll_armor', cnt: 500 }, { id: 'sherine_crystal', cnt: 5 }, { id: 'gold', cnt: 5000000 }] }", '碧恩盔甲祝福卷軸配方不可被上游覆蓋');
has('world', "acc: { result: 'new_item_bless_acc', rate: 40, req: [{ id: 'scroll_acc', cnt: 20 }, { id: 'sherine_crystal', cnt: 10 }, { id: 'gold', cnt: 10000000 }] }", '碧恩飾品祝福卷軸配方不可被上游覆蓋');
has('items', "if (slot === 'wpn') { d.extraDmg += sg*2; d.extraHit += sg*2; d.extraMp += sg*3; }", '祝福武器加成必須保留');
has('items', "else if (slot === 'arm') { d.ac -= sg*1; d.dr += sg*1; if (p) p.mhp += sg*10; }", '祝福防具加成必須保留');
has('items', "else { d.ac -= sg*1; d.mr += sg*2; if (p) { p.mhp += sg*5; p.mmp += sg*3; } }", '祝福飾品加成必須保留');

const reaperLine = files.drops.split(/\r?\n/).find((line) => line.includes("'邪惡的鐮刀死神'")) || '';
['wpn_xbow_abyss', 'wpn_qigu_killing_intent', 'wpn_chain_exterminator'].forEach((id) => {
  expect(`邪惡的鐮刀死神 ${id} 掉落率必須是0.1%`, reaperLine.includes(`['${id}',0.1]`));
});

has('data', '"heart_halphas": { n: "哈爾巴斯之心"', '哈爾巴斯之心資料必須存在');
has('data', '融合四大龍心與兩千萬金幣而成', '哈爾巴斯之心金幣設定必須是兩千萬');
[
  'god_royal_flash', 'god_knight_judgment', 'god_elf_obsession', 'god_mage_eva',
  'god_dark_dantes', 'god_illusion_theia', 'god_dragon_aurakia', 'god_warrior_fear'
].forEach((id) => has('data', `"${id}"`, `神話武器 ${id} 必須存在`));
has('data', '"npc_halphas_smith", n: "赫爾"', '席琳神殿神話武器NPC赫爾必須存在');

['月亮騎士絲莉安', '影子騎士格立特', '鋼鐵騎士阿頓', '天鵝的騎士依詩蒂', '幸運的魔法師宙斯'].forEach((name) => {
  has('stats', `n:"${name}", lv:90`, `90等變身 ${name} 必須存在`);
});

has('wiki', '賦予祝福卷軸</b>由象牙塔「碧恩」製作', '百科必須顯示目前碧恩配方');
has('wiki', '舊「傳統模式」已取消', '百科必須說明傳統模式已取消');
has('wiki', "var COLL_MODES = [['', '一般'], ['_classic', '經典']]", '收藏模式只可顯示一般與經典');
lacks('wiki', '象牙塔「克里斯特」用 100 萬金幣', '百科不可殘留舊克里斯特配方');
lacks('dex', '等級 40 以上頭目', '掉落搜尋不可誤報祝福卷軸由40等頭目掉落');

if (failures.length) {
  console.error('客製化回歸檢查失敗：');
  failures.forEach((failure) => console.error(`- ${failure}`));
  process.exit(1);
}

console.log(`客製化回歸檢查通過（${assetVersions.length} 個網頁資源已套用 ${version}）。`);
