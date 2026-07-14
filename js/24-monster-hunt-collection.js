// ===== 狩獵怪物收藏（草案模組）=====
// 目前刻意不在 index.html 載入，也未接到 killMob／存檔／收藏面板。
// 等規則、顯示方式與獎勵確認後，再由正式整合提交啟用。
(function (global) {
    'use strict';

    const VERSION = 1;
    const ENABLED = false;

    function emptyProgress() {
        return { version: VERSION, kills: {}, firstKills: {} };
    }

    function normalizeProgress(raw) {
        const src = raw && typeof raw === 'object' ? raw : {};
        const out = emptyProgress();
        const kills = src.kills && typeof src.kills === 'object' ? src.kills : {};
        const firstKills = src.firstKills && typeof src.firstKills === 'object' ? src.firstKills : {};

        Object.keys(kills).forEach(id => {
            const count = Math.max(0, Math.floor(Number(kills[id]) || 0));
            if (count > 0) out.kills[id] = count;
        });
        Object.keys(firstKills).forEach(id => {
            const at = Math.max(0, Math.floor(Number(firstKills[id]) || 0));
            if (at > 0) out.firstKills[id] = at;
        });
        return out;
    }

    function buildMonsterIndex(db) {
        const source = db && typeof db === 'object' ? db : {};
        const monsters = source.mobs && typeof source.mobs === 'object' ? source.mobs : {};
        const maps = source.maps && typeof source.maps === 'object' ? source.maps : {};
        const mapIdsByMonster = {};

        Object.keys(maps).forEach(mapId => {
            const pool = Array.isArray(maps[mapId]) ? maps[mapId] : [];
            pool.forEach(monsterId => {
                if (!mapIdsByMonster[monsterId]) mapIdsByMonster[monsterId] = [];
                if (!mapIdsByMonster[monsterId].includes(mapId)) mapIdsByMonster[monsterId].push(mapId);
            });
        });

        const index = {};
        Object.keys(monsters).forEach(id => {
            const mob = monsters[id];
            if (!mob || typeof mob !== 'object') return;
            index[id] = {
                id,
                name: mob.n || id,
                level: Math.max(1, Math.floor(Number(mob.lv) || 1)),
                boss: !!mob.boss,
                race: mob.race || '',
                element: mob.e || 'none',
                icon: mob.img || '',
                maps: (mapIdsByMonster[id] || []).slice()
            };
        });
        return index;
    }

    function recordKill(progress, monsterId, now) {
        const out = normalizeProgress(progress);
        const id = String(monsterId || '');
        if (!id) return out;
        out.kills[id] = (out.kills[id] || 0) + 1;
        if (!out.firstKills[id]) out.firstKills[id] = Math.max(1, Math.floor(Number(now) || Date.now()));
        return out;
    }

    function mergeProgress(a, b) {
        const left = normalizeProgress(a);
        const right = normalizeProgress(b);
        const out = emptyProgress();
        const ids = new Set([...Object.keys(left.kills), ...Object.keys(right.kills)]);

        ids.forEach(id => {
            out.kills[id] = Math.max(left.kills[id] || 0, right.kills[id] || 0);
            const times = [left.firstKills[id], right.firstKills[id]].filter(Boolean);
            if (times.length) out.firstKills[id] = Math.min(...times);
        });
        return out;
    }

    function entry(index, progress, monsterId) {
        const id = String(monsterId || '');
        const monster = index && index[id];
        if (!monster) return null;
        const p = normalizeProgress(progress);
        const kills = p.kills[id] || 0;
        return Object.assign({}, monster, {
            discovered: kills > 0,
            kills,
            firstKillAt: p.firstKills[id] || 0
        });
    }

    function list(index, progress, options) {
        const opts = options && typeof options === 'object' ? options : {};
        const rows = Object.keys(index || {}).map(id => entry(index, progress, id)).filter(Boolean);
        const query = String(opts.query || '').trim().toLowerCase();
        const filtered = rows.filter(row => {
            if (opts.discoveredOnly && !row.discovered) return false;
            if (opts.undiscoveredOnly && row.discovered) return false;
            if (opts.bossOnly && !row.boss) return false;
            if (opts.mapId && !row.maps.includes(opts.mapId)) return false;
            if (query && !row.name.toLowerCase().includes(query) && !row.id.toLowerCase().includes(query)) return false;
            return true;
        });
        filtered.sort((a, b) => {
            if (a.discovered !== b.discovered) return a.discovered ? -1 : 1;
            if (a.boss !== b.boss) return a.boss ? -1 : 1;
            if (a.level !== b.level) return a.level - b.level;
            return a.name.localeCompare(b.name, 'zh-Hant');
        });
        return filtered;
    }

    function summary(index, progress) {
        const rows = list(index, progress);
        const discovered = rows.filter(row => row.discovered).length;
        return {
            total: rows.length,
            discovered,
            undiscovered: Math.max(0, rows.length - discovered),
            bosses: rows.filter(row => row.boss).length,
            bossesDiscovered: rows.filter(row => row.boss && row.discovered).length,
            totalKills: rows.reduce((sum, row) => sum + row.kills, 0)
        };
    }

    function serialize(progress) {
        return JSON.stringify(normalizeProgress(progress));
    }

    function deserialize(text) {
        try { return normalizeProgress(JSON.parse(String(text || ''))); }
        catch (e) { return emptyProgress(); }
    }

    global.MonsterHuntCollectionDraft = Object.freeze({
        VERSION,
        ENABLED,
        emptyProgress,
        normalizeProgress,
        buildMonsterIndex,
        recordKill,
        mergeProgress,
        entry,
        list,
        summary,
        serialize,
        deserialize
    });
})(typeof window !== 'undefined' ? window : globalThis);
