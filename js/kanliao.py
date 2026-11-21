# -*- coding: utf-8 -*-
"""今日看料（kanliao13.org）自建源 v5。

2026-11-21 实测结构：
  列表 / 或 /category/{slug}/    卡片 div#post-card-{id}
       封面 <div class="blog-background"> 服务端 style 是空的，
       真图在紧随其后的 loadBannerDirect('/usr/uploads/...') 参数里（相对路径）
  详情 /archives/{id}/            播放地址在 div.dplayer 的 data-config JSON：
       {"video":{"url":"https:\/\/...\/index.m3u8"}}，注意 JSON 内的 \/ 转义
  播放 m3u8 与分片都校验 Referer（裸连 302 回文章页），分片是相对路径
       indexN.ts，必须按 m3u8 自身目录 urljoin 后再逐片走本地代理
"""

import html as html_lib
import json
import re
import ssl
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

HOST = "https://kanliao13.org"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

DEF_CATS = [
    {"type_id": "rdgz", "type_name": "热点关注"},
    {"type_id": "dy", "type_name": "抖音"},
    {"type_id": "ks", "type_name": "快手"},
    {"type_id": "douyu", "type_name": "斗鱼"},
    {"type_id": "hy", "type_name": "虎牙"},
    {"type_id": "hj", "type_name": "花椒"},
]

TAG_NOISE = ("看料", "合集", "集锦", "热门", "推荐", "视频", "在线观看", "免费", "今日")

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        def __init__(self):
            pass


class Spider(BaseSpider):
    def __init__(self):
        try:
            BaseSpider.__init__(self)
        except Exception:
            pass
        self.host = HOST
        self._ctx = None

    def init(self, extend=""):
        self.host = HOST
        self._ctx = None
        try:
            cfg = json.loads(extend) if extend else {}
            if isinstance(cfg, dict) and cfg.get("host"):
                self.host = str(cfg["host"]).rstrip("/")
        except Exception:
            pass

    # ---------- 网络 ----------
    def _ssl_ctx(self):
        if self._ctx is None:
            try:
                c = ssl.create_default_context()
                c.check_hostname = False
                c.verify_mode = ssl.CERT_NONE
                self._ctx = c
            except Exception:
                self._ctx = False
        return self._ctx or None

    def _open(self, url, timeout=25):
        hd = {
            "User-Agent": UA,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        try:
            req = Request(url, headers=hd)
            ctx = self._ssl_ctx()
            if ctx is not None:
                resp = urlopen(req, timeout=timeout, context=ctx)
            else:
                resp = urlopen(req, timeout=timeout)
            data = resp.read()
            ctype = resp.headers.get("Content-Type") or ""
            try:
                resp.close()
            except Exception:
                pass
            return data, ctype
        except Exception:
            return None, ""

    def _get(self, path):
        url = path if path.startswith("http") else self.host + path
        data, _ = self._open(url)
        return data.decode("utf-8", "ignore") if data else ""

    # ---------- 工具 ----------
    @staticmethod
    def _clean(t):
        t = re.sub(r"<[^>]+>", "", str(t or ""))
        t = html_lib.unescape(t)
        return re.sub(r"\s+", " ", t).strip()

    def _abs(self, u):
        u = html_lib.unescape(str(u or "")).strip().strip("'\"")
        if not u:
            return ""
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http"):
            return u
        if u.startswith("/"):
            return self.host + u
        return self.host + "/" + u

    def _proxy(self, url):
        return "http://127.0.0.1:9978/proxy?do=py&url=" + quote(url, safe="")

    # ---------- 列表 ----------
    def _cards(self, h):
        out = []
        seen = set()
        pos = [(m.start(), m.group(1)) for m in re.finditer(r'id="post-card-(\d+)"', h or "")]
        for i, item in enumerate(pos):
            start, vid = item[0], item[1]
            nxt = pos[i + 1][0] if i + 1 < len(pos) else start + 6000
            seg = h[start:min(nxt, start + 6000)]
            tm = re.search(r"post-card-title[^>]*>([\s\S]{0,600}?)</h2>", seg)
            name = ""
            if tm:
                raw = re.sub(r'<div class="wrap">[\s\S]*?</div>', "", tm.group(1))
                name = self._clean(raw)
            name = re.sub(r"^(热搜\s*HOT|HOT|置顶|推荐)\s*", "", name).strip()
            if not name or re.fullmatch(r"\d+", name) or vid in seen:
                continue
            seen.add(vid)
            pic = ""
            pm = (re.search(r"loadBannerDirect\('([^']+)'", seg)
                  or re.search(r"background-image:\s*url\(([^)]*)\)", seg)
                  or re.search(r'<img[^>]+(?:data-src|src)="([^"]+)"', seg))
            if pm:
                pic = self._abs(pm.group(1))
            out.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": "",
            })
        return out

    def _classes(self, h):
        cls = []
        seen = set()
        for m in re.finditer(r'<a[^>]*href="[^"]*/category/([a-z0-9_-]+)/"[^>]*>([^<]{1,20})</a>', h or ""):
            slug = m.group(1)
            nm = self._clean(m.group(2))
            if not slug or not nm or slug in seen:
                continue
            seen.add(slug)
            cls.append({"type_id": slug, "type_name": nm})
            if len(cls) >= 10:
                break
        return cls or list(DEF_CATS)

    def homeContent(self, filter=None):
        h = self._get("/")
        return {"class": self._classes(h), "filters": {}, "list": self._cards(h)}

    def homeVideoContent(self):
        return {"list": self._cards(self._get("/"))}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        page = int(pg) if str(pg).isdigit() else 1
        slug = str(tid or "dy")
        path = "/category/%s/" % slug
        if page > 1:
            path = "/category/%s/page/%d/" % (slug, page)
        cards = self._cards(self._get(path))
        return {"list": cards, "page": page, "pagecount": 999,
                "limit": len(cards), "total": 999999}

    def searchContent(self, key, quick=False, pg="1"):
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        cards = self._cards(self._get("/search/" + quote(kw) + "/"))
        return {"list": cards, "page": 1, "pagecount": 1,
                "limit": len(cards), "total": len(cards)}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        if not vid:
            return {"list": []}
        h = self._get("/archives/%s/" % vid)

        title = ""
        for pat in (r'<meta itemprop="headline"[^>]*content="([^"]+)"',
                    r'<meta property="og:title"[^>]*content="([^"]+)"'):
            m = re.search(pat, h)
            if m:
                title = self._clean(m.group(1))
                break
        if not title:
            m = re.search(r"<title>([^<]+)</title>", h)
            title = self._clean(m.group(1)).split(" - ")[0] if m else vid

        pic = ""
        m = re.search(r'<meta property="og:image"[^>]*content="([^"]+)"', h)
        if m:
            pic = self._abs(m.group(1))
        if not pic:
            m = re.search(r"loadBannerDirect\('([^']+)'", h)
            if m:
                pic = self._abs(m.group(1))

        # 简介：站点把剧情写在 meta description（没写剧情的文章这里就等于标题）
        desc = ""
        m = re.search(r'<meta name="description"[^>]*content="([^"]*)"', h)
        if m:
            desc = self._clean(m.group(1))
        if desc == title:
            desc = ""
        tags = []
        m = re.search(r'<meta name="keywords"[^>]*content="([^"]*)"', h)
        if m:
            for t in re.split(r"[,，]", self._clean(m.group(1))):
                t = t.strip()
                if t and t != title and t not in TAG_NOISE and t not in tags:
                    tags.append(t)
        parts = []
        if desc:
            parts.append(desc)
        if tags:
            parts.append("标签：" + " · ".join(tags[:8]))
        m = re.search(r'itemprop="datePublished"[^>]*content="([^"]+)"', h)
        if m:
            parts.append("发布：" + self._clean(m.group(1))[:10])
        content = "\n".join(parts)

        plays = []
        for cm in re.finditer(r"""data-config=(?:'([^']*)'|"([^"]*)")"", h):
            cfg = cm.group(1) or cm.group(2) or ""
            u = ""
            try:
                obj = json.loads(html_lib.unescape(cfg))
                if isinstance(obj, dict):
                    v = obj.get("video") or {}
                    if isinstance(v, dict):
                        u = str(v.get("url") or "").strip()
            except Exception:
                u = ""
            if not u:
                um = re.search(r"""["']url["']\s*:\s*["']([^"']+)["']""", cfg)
                u = um.group(1) if um else ""
            u = u.replace("\\/", "/").strip()
            if u.startswith("http") and u not in plays:
                plays.append(u)
        if not plays:
            for u in re.findall(r"""https?://[^"'\s<>]+?\.m3u8[^"'\s<>]*""", h.replace("\\/", "/")):
                if u not in plays:
                    plays.append(u)

        eps = []
        for i, u in enumerate(plays):
            nm = "正片" if len(plays) == 1 else ("第%d集" % (i + 1))
            eps.append(nm + "$" + self._proxy(u))
        play = "#".join(eps)

        return {"list": [{
            "vod_id": vid,
            "vod_name": title or vid,
            "vod_pic": pic,
            "vod_remarks": "" if play else "无线路",
            "vod_content": content or title,
            "vod_play_from": "今日看料",
            "vod_play_url": play,
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        u = str(id or "")
        if "$" in u:
            u = u.split("$")[-1]
        hd = {"User-Agent": UA, "Referer": self.host + "/"}
        if u.startswith("http"):
            return {"parse": 0, "jx": 0, "playUrl": "", "url": u, "header": hd}
        return {"parse": 1, "jx": 0, "playUrl": "", "url": u, "header": hd}

    # ---------- 本地代理 ----------
    def localProxy(self, param):
        import urllib.parse as _up
        if isinstance(param, str):
            text = param.strip()
            if text.startswith("http"):
                param = dict(_up.parse_qsl(_up.urlsplit(text).query))
            elif text.startswith("{"):
                try:
                    param = json.loads(text)
                except Exception:
                    param = {}
            else:
                param = dict(_up.parse_qsl(text))
        if not isinstance(param, dict):
            param = {}
        target = str(param.get("url") or "").strip()
        if not target:
            return [404, "text/plain", b"Not Found", {}]

        data, ctype = self._open(target, timeout=30)
        if data is None:
            return [502, "text/plain", b"upstream failed", {}]

        head = data[:16].lower()
        if b"#extm3u" in head:
            text = data.decode("utf-8", "ignore")
            out = []
            for ln in text.splitlines():
                s = ln.strip()
                if not s:
                    out.append(ln)
                    continue
                if s.startswith("#"):
                    out.append(re.sub(r'URI="([^"]+)"',
                                      lambda mm: 'URI="%s"' % self._proxy(urljoin(target, mm.group(1))),
                                      ln))
                else:
                    out.append(self._proxy(urljoin(target, s)))
            return [200, "application/vnd.apple.mpegurl", "\n".join(out).encode("utf-8"),
                    {"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache"}]

        if data[:1] == b"G":
            return [200, "video/mp2t", data,
                    {"Access-Control-Allow-Origin": "*", "Cache-Control": "max-age=86400"}]

        return [200, ctype or "application/octet-stream", data,
                {"Access-Control-Allow-Origin": "*"}]

    proxy = localProxy

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return ".m3u8" in u or ".mp4" in u

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return []

    def destroy(self):
        pass
