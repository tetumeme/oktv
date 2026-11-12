// ==UserScript==
// @name         Jable
// @namespace    gmspider
// @version      2026.11.13
// @description  Jable 自建维护版（原生 DOM，不依赖 jQuery）
// @author       lcs
// @match        https://jable.tv/*
// @grant        unsafeWindow
// ==/UserScript==
(function () {
    const GMSpiderArgs = { fName: "homeContent", fArgs: [true] };
    try {
        if (typeof GmSpiderInject !== "undefined") {
            const args = JSON.parse(GmSpiderInject.GetSpiderArgs());
            GMSpiderArgs.fName = args.shift();
            GMSpiderArgs.fArgs = args;
        }
    } catch (e) {
    }

    function q(sel, root) {
        try {
            return (root || document).querySelector(sel);
        } catch (e) {
            return null;
        }
    }

    function qa(sel, root) {
        try {
            return Array.prototype.slice.call((root || document).querySelectorAll(sel));
        } catch (e) {
            return [];
        }
    }

    function txt(el) {
        return el ? (el.textContent || "").trim() : "";
    }

    function isCf() {
        if (q("#cf-wrapper")) {
            return true;
        }
        return /Just a moment|请稍候|Attention Required|Checking your browser/i.test(document.title || "");
    }

    function cards() {
        let boxes = qa(".video-img-box");
        if (!boxes.length) {
            boxes = qa("[class*='video-img-box']");
        }
        return boxes;
    }

    function nameOf(box) {
        let n = txt(q(".title", box));
        if (!n) {
            n = txt(q("h6", box));
        }
        if (!n) {
            const img = q("img", box);
            if (img) {
                n = (img.getAttribute("alt") || "").trim();
            }
        }
        if (!n) {
            const a = q("a[href*='/videos/']", box);
            if (a) {
                n = (a.getAttribute("title") || "").trim();
            }
        }
        return n;
    }

    function picOf(box) {
        const img = q("img", box);
        if (!img) {
            return "";
        }
        return img.getAttribute("data-src") || img.getAttribute("src") || "";
    }

    function idOf(href) {
        const parts = String(href || "").split("/").filter(Boolean);
        const last = parts.length ? parts[parts.length - 1] : "";
        return last.toUpperCase();
    }

    function listVideos(result) {
        result.list = result.list || [];
        cards().forEach(function (box) {
            const a = q("a[href*='/videos/']", box);
            if (!a) {
                return;
            }
            const id = idOf(a.getAttribute("href"));
            const name = nameOf(box);
            if (!id || !name) {
                return;
            }
            result.list.push({
                vod_id: id,
                vod_name: name,
                vod_pic: picOf(box),
                vod_remarks: ""
            });
        });
        const last = q(".pagination .page-item:last-child");
        result.pagecount = parseInt(txt(last), 10) || 1;
        return result;
    }

    function pageTitle() {
        let t = txt(q(".video-info h4"));
        if (!t) {
            t = txt(q("h1"));
        }
        if (!t) {
            t = (document.title || "").split("|")[0].split(" - Jable")[0].trim();
        }
        return t;
    }

    function findHls() {
        let u = "";
        try {
            if (typeof unsafeWindow !== "undefined" && unsafeWindow.hlsUrl) {
                u = unsafeWindow.hlsUrl;
            }
        } catch (e) {
        }
        if (!u) {
            try {
                if (typeof window !== "undefined" && window.hlsUrl) {
                    u = window.hlsUrl;
                }
            } catch (e) {
            }
        }
        if (!u) {
            const m = (document.documentElement.innerHTML || "").match(/https?:\/\/[^"'\s]+\.m3u8[^"'\s]*/);
            if (m) {
                u = m[0];
            }
        }
        return u;
    }

    const GmSpider = {
        homeContent: function () {
            const r = listVideos({
                class: [
                    { type_id: "latest-updates", type_name: "最近更新" },
                    { type_id: "hot", type_name: "热门影片" },
                    { type_id: "categories/chinese-subtitle", type_name: "中文字幕" },
                    { type_id: "new-release", type_name: "全新上市" }
                ],
                filters: {},
                list: []
            });
            if (!r.list.length) {
                r.list.push({
                    vod_id: "diag",
                    vod_name: "诊断 cf=" + (isCf() ? "1" : "0")
                        + " box=" + cards().length
                        + " p=" + location.pathname
                        + " t=" + String(document.title || "").slice(0, 24),
                    vod_pic: ""
                });
            }
            return r;
        },
        categoryContent: function (tid, pg, filter, extend) {
            return listVideos({ list: [], pagecount: 1 });
        },
        searchContent: function (key, quick, pg) {
            return listVideos({ list: [], pagecount: 1 });
        },
        detailContent: function (ids) {
            const id = (ids && ids[0]) ? String(ids[0]) : "";
            const hls = findHls();
            const player = q("#player");
            const poster = player ? (player.getAttribute("poster") || "") : "";
            return {
                list: [{
                    vod_id: id,
                    vod_name: pageTitle() || id,
                    vod_pic: poster,
                    vod_remarks: "",
                    vod_content: txt(q(".video-info h4")),
                    vod_play_from: "Jable",
                    vod_play_url: hls ? ("正片$" + hls) : ""
                }]
            };
        }
    };

    function push(result) {
        try {
            if (typeof GmSpiderInject !== "undefined") {
                GmSpiderInject.SetSpiderResult(JSON.stringify(result));
            }
        } catch (e) {
        }
    }

    function run() {
        if (run.done) {
            return;
        }
        run.done = true;
        let result = { list: [] };
        try {
            if (isCf()) {
                result = {
                    list: [{
                        vod_id: "diag",
                        vod_name: "诊断 CF挑战 t=" + String(document.title || "").slice(0, 30),
                        vod_pic: ""
                    }]
                };
            } else {
                const fn = GmSpider[GMSpiderArgs.fName];
                result = fn ? fn.apply(null, GMSpiderArgs.fArgs) : { list: [] };
            }
        } catch (e) {
            result = {
                list: [{
                    vod_id: "diag",
                    vod_name: "诊断 err=" + String(e && e.message ? e.message : e).slice(0, 50),
                    vod_pic: ""
                }]
            };
        }
        push(result);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", run);
        setTimeout(run, 2500);
    } else {
        run();
    }
})();
