// ==UserScript==
// @name         123av-cn
// @namespace    gmspider
// @version      2026.11.12
// @description  123av GMSpider 中文版适配（/cn 新版布局）
// @author       Luomo / fixed
// @match        https://*.123av.com/*
// @grant        unsafeWindow
// ==/UserScript==
(function () {
    'use strict';

    var A = {};
    if (typeof GmSpiderInject !== 'undefined') {
        var raw = JSON.parse(GmSpiderInject.GetSpiderArgs());
        A.fName = raw.shift();
        A.fArgs = raw;
    } else {
        A.fName = 'homeContent';
        A.fArgs = [];
    }
    Object.freeze(A);

    var BASE = 'https://123av.com';
    var PER_PAGE = 12;

    function q(s, r) { return (r || document).querySelector(s); }
    function qa(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
    function tx(e) { return e ? (e.textContent || '').replace(/\s+/g, ' ').trim() : ''; }
    function num(s) { var m = (s || '').match(/(\d[\d,]*)/); return m ? parseInt(m[1].replace(/,/g, ''), 10) : 0; }
    function abs(u) {
        if (!u) return '';
        if (u.indexOf('//') === 0) return 'https:' + u;
        if (u.charAt(0) === '/') return BASE + u;
        return u;
    }
    function slug(h) { var m = (h || '').match(/\/v\/([^\/?#]+)/); return m ? m[1] : ''; }

    // 按关键词在详情信息里取值，兼容中文/英文标签
    function pick(info, keys) {
        for (var i = 0; i < keys.length; i++) {
            for (var k in info) {
                if (k && k.indexOf(keys[i]) > -1) return info[k];
            }
        }
        return '';
    }

    // 视频卡片列表
    function cards(root) {
        var out = [], seen = {};
        qa('.card', root).forEach(function (c) {
            var a = c.querySelector('a.card__cover[href]') || c.querySelector('a.card__link[href]');
            var id = slug(a && a.getAttribute('href'));
            if (!id || seen[id]) return;
            seen[id] = 1;
            var img = c.querySelector('.card__img');
            out.push({
                vod_id: id,
                vod_name: tx(c.querySelector('.card__title')) || id,
                vod_pic: abs(img ? (img.getAttribute('src') || img.getAttribute('data-src') || '') : ''),
                vod_remarks: tx(c.querySelector('.card__dur')) || tx(c.querySelector('.card__meta'))
            });
        });
        return out;
    }

    // 总页数：优先 .pager__total ("/ 5000")，退回按总数/12 计算
    function pageCount(root) {
        var n = num(tx(q('.pager__total', root)));
        if (n) return n;
        n = num(tx(q('.pagehead__count', root)));
        return n ? Math.ceil(n / PER_PAGE) : 1;
    }

    // 目录页（类别/女演员/制作商/系列）
    function folders(kind, root) {
        var out = [];
        function push(href, name, remark, pic) {
            var rel = (href || '').replace(/^https?:\/\/[^\/]+/, '').replace(/^\/(?:cn|en|tw)\//, '');
            if (!rel) return;
            out.push({
                vod_id: rel,
                vod_name: name || rel,
                vod_tag: 'folder',
                vod_pic: abs(pic || ''),
                vod_remarks: remark || '',
                style: { type: 'rect', ratio: 1 }
            });
        }
        if (kind === 'genres') {
            qa('a.gchip', root).forEach(function (a) {
                push(a.getAttribute('href'), tx(a.querySelector('.gchip__name')), tx(a.querySelector('.gchip__count')));
            });
        } else if (kind === 'makers') {
            qa('a.mcard', root).forEach(function (a) {
                push(a.getAttribute('href'), tx(a.querySelector('.mcard__name')), tx(a.querySelector('.mcard__meta')));
            });
        } else if (kind === 'series') {
            qa('a.srow', root).forEach(function (a) {
                push(a.getAttribute('href'), tx(a.querySelector('.srow__name')), tx(a.querySelector('.srow__meta')));
            });
        } else if (kind === 'actresses') {
            qa('.actress', root).forEach(function (d) {
                var a = d.querySelector('a.actress__name[href]') || d.querySelector('a[href*="/actresses/"]');
                if (!a) return;
                var pic = '', av = d.querySelector('.actress__avatar');
                if (av) { var m = (av.getAttribute('style') || '').match(/url\(['"]?([^'")]+)/); if (m) pic = m[1]; }
                push(a.getAttribute('href'), tx(a), '', pic);
            });
        }
        return out;
    }

    // 播放集数（Alpine x-data 里的 JSON.parse('[{"number":1,...}]')）
    function episodes() {
        var host = q('.watch__main[x-data]') || q('[x-data*="player("]');
        if (!host) return [];
        var m = (host.getAttribute('x-data') || '').match(/JSON\.parse\('([\s\S]*?)'\)/);
        if (!m) return [];
        try {
            var arr = JSON.parse(m[1].replace(/\\u0022/g, '"').replace(/\\\\\//g, '/'));
            return arr.filter(function (e) { return e && e.url; });
        } catch (e) { return []; }
    }

    var Spiders = {
        homeContent: function () {
            var sorts = [
                { n: '默认', v: '' },
                { n: '今日', v: '&sort=today' },
                { n: '本周', v: '&sort=week' },
                { n: '本月', v: '&sort=month' }
            ];
            var f = {};
            ['new', 'hot', 'recent', 'censored', 'uncensored', 'uncensored-leaked'].forEach(function (k) {
                f[k] = [{ key: 'sort', name: '排序', value: sorts }];
            });
            return {
                class: [
                    { type_id: 'new', type_name: '最近更新' },
                    { type_id: 'hot', type_name: '热门' },
                    { type_id: 'recent', type_name: '最新添加' },
                    { type_id: 'censored', type_name: '有码' },
                    { type_id: 'uncensored', type_name: '无码' },
                    { type_id: 'uncensored-leaked', type_name: '无码泄露' },
                    { type_id: 'genres', type_name: '类别' },
                    { type_id: 'actresses', type_name: '女演员' },
                    { type_id: 'makers', type_name: '制作商' },
                    { type_id: 'series', type_name: '系列' }
                ],
                filters: f,
                list: cards()
            };
        },

        categoryContent: function (tid, pg) {
            var kinds = { genres: 1, actresses: 1, makers: 1, series: 1 };
            if (kinds[tid]) {
                return { list: folders(tid), page: 1, pagecount: 1, limit: 9999 };
            }
            return { list: cards(), page: parseInt(pg, 10) || 1, pagecount: pageCount() };
        },

        detailContent: function (ids) {
            var id = ids[0] || '', info = {};
            qa('.watch__info-row').forEach(function (r) {
                var k = tx(r.querySelector('dt'));
                if (k) info[k] = tx(r.querySelector('dd'));
            });

            var pic = '', pl = q('.player');
            if (pl) { var m = (pl.getAttribute('style') || '').match(/url\(['"]?([^'")]+)/); if (m) pic = m[1]; }
            if (!pic) { var og = q('meta[property="og:image"]'); if (og) pic = og.getAttribute('content') || ''; }

            var title = tx(q('.watch__title')) || id;
            var eps = episodes();
            var desc = title;
            if (eps.length > 1) desc += '  [共 ' + eps.length + ' 集，进播放页可切换]';

            return {
                list: [{
                    vod_id: id,
                    vod_name: title,
                    vod_pic: abs(pic),
                    vod_year: pick(info, ['发布日期', 'Release date']),
                    vod_remarks: pick(info, ['时长', 'Duration']),
                    vod_actor: pick(info, ['女演员', 'Actress', 'Actors']),
                    vod_director: pick(info, ['制作商', 'Maker']),
                    vod_content: desc.trim(),
                    vod_play_data: [{
                        from: '123AV',
                        media: [{
                            name: '默认线路',
                            type: 'webview',
                            ext: { replace: { vod_id: id } }
                        }]
                    }]
                }]
            };
        },

        // 返回 match，交给 WebView 嗅探 m3u8
        playerContent: function () {
            return { type: 'match' };
        },

        searchContent: function (key, quick, pg) {
            return { list: cards(), page: parseInt(pg, 10) || 1, pagecount: pageCount() };
        }
    };

    function run() {
        var result;
        if (q('#cf-wrapper')) {
            result = JSON.stringify({ list: [] });
        } else {
            try {
                result = JSON.stringify(Spiders[A.fName].apply(null, A.fArgs));
            } catch (e) {
                result = JSON.stringify({ list: [] });
                console.log('123av spider error: ' + e);
            }
        }
        console.log(result);
        if (typeof GmSpiderInject !== 'undefined') GmSpiderInject.SetSpiderResult(result);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', run);
    } else {
        run();
    }
})();
