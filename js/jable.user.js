// ==UserScript==
// @name         Jable
// @namespace    gmspider
// @version      2026.11.12
// @description  Jable 自建维护版（适配 2026-11 站点结构）
// @author       lcs
// @match        https://jable.tv/*
// @require      https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.slim.min.js
// @grant        unsafeWindow
// ==/UserScript==
(function () {
    const GMSpiderArgs = {};
    if (typeof GmSpiderInject !== 'undefined') {
        let args = JSON.parse(GmSpiderInject.GetSpiderArgs());
        GMSpiderArgs.fName = args.shift();
        GMSpiderArgs.fArgs = args;
    } else {
        GMSpiderArgs.fName = "homeContent";
        GMSpiderArgs.fArgs = [true];
    }
    Object.freeze(GMSpiderArgs);

    function vidOf(href) {
        try {
            const parts = new URL(href).pathname.split('/').filter(Boolean);
            return (parts[1] || '').toUpperCase();
        } catch (e) {
            return '';
        }
    }

    const GmSpider = (function () {
        function listVideos(result) {
            result.list = result.list || [];
            result.pagecount = parseInt($(".pagination .page-item:last").text()) || 1;
            $(".video-img-box").each(function () {
                const a = $(this).find(".img-box a").attr("href");
                if (!a) {
                    return;
                }
                const name = $(this).find(".title").text().trim();
                if (!name) {
                    return;
                }
                const img = $(this).find("img");
                result.list.push({
                    vod_id: vidOf(a),
                    vod_name: name,
                    vod_pic: img.data("src") || img.attr("src") || "",
                    vod_remarks: $(this).find(".absolute-bottom-right").text().trim()
                });
            });
            return result;
        }

        function pageTitle() {
            let t = ($(".video-info h4").first().text() || "").trim();
            if (!t) {
                t = ($("h1").first().text() || "").trim();
            }
            if (!t) {
                t = (document.title || "").split("|")[0].split(" - Jable")[0].trim();
            }
            return t;
        }

        return {
            homeContent: function (filter) {
                const r = listVideos({
                    class: [
                        { type_id: "latest-updates", type_name: "最近更新" },
                        { type_id: "hot", type_name: "热门影片" },
                        { type_id: "categories/chinese-subtitle", type_name: "中文字幕" },
                        { type_id: "new-release", type_name: "全新上市" }
                    ],
                    filters: {}
                });
                if (!r.list.length) {
                    r.list.push({
                        vod_id: "diag",
                        vod_name: "诊断 box=" + document.querySelectorAll(".video-img-box").length
                            + " t=" + document.querySelectorAll(".title").length
                            + " jq=" + (typeof $ === "function" ? "y" : "n")
                            + " p=" + location.pathname,
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
                let hls = "";
                if (typeof unsafeWindow !== "undefined" && unsafeWindow.hlsUrl) {
                    hls = unsafeWindow.hlsUrl;
                }
                if (!hls && typeof window.hlsUrl !== "undefined" && window.hlsUrl) {
                    hls = window.hlsUrl;
                }
                if (!hls) {
                    const mm = (document.documentElement.innerHTML || "").match(/https?:\/\/[^"'\s]+\.m3u8[^"'\s]*/);
                    if (mm) {
                        hls = mm[0];
                    }
                }
                const pic = $("#player").attr("poster") || $(".video-info img").first().attr("src") || "";
                return {
                    list: [{
                        vod_id: id,
                        vod_name: pageTitle() || id,
                        vod_pic: pic,
                        vod_remarks: "",
                        vod_content: ($(".video-info h4").first().text() || "").trim(),
                        vod_play_from: "Jable",
                        vod_play_url: hls ? ("正片$" + hls) : ""
                    }]
                };
            }
        };
    })();

    $(document).ready(function () {
        let result = { list: [] };
        if ($("#cf-wrapper").length > 0) {
            if (typeof GM_toastLong === "function") {
                GM_toastLong("源站不可用:" + $("title").text());
            }
        } else {
            try {
                result = GmSpider[GMSpiderArgs.fName].apply(null, GMSpiderArgs.fArgs);
            } catch (e) {
                console.log("spider error", e);
                result = { list: [] };
            }
        }
        if (typeof GmSpiderInject !== "undefined") {
            GmSpiderInject.SetSpiderResult(JSON.stringify(result));
        }
    });
})();
