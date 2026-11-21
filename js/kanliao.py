# -*- coding: utf-8 -*-
# 今日看料 kanliao13.org 自建源 v5
# 列表封面在 loadBannerDirect() 参数里；详情播放地址在 dplayer 的 data-config JSON；
# m3u8 与分片都校验 Referer，分片是相对路径，需按 m3u8 目录 urljoin 后逐片走本地代理。

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
    {"type_id": "all", "type_name": "推荐"},
    {"type_id": "rdgz", "type_name": "热点关注"},
    {"type_id": "dy", "type_name": "抖音"},
    {"type_id": "ks", "type_name": "快手"},
    {"type_id": "douyu", "type_name": "斗鱼"},
    {"type_id": "hy", "type_name": "虎牙"},
    {"type_id": "hj", "type_name": "花椒"},
]

TAG_NOISE = ("看料", "合集", "集锦", "热门", "推荐", "视频", "在线观看", "免费")

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
        cfg = {}
        if extend:
            try:
                cfg = json.loads(extend)
            except Exception:
                cfg = {}
        if isinstance(cfg, dict):
            hh = cfg.get("host")
            if hh:
                self.host = str(hh).rstrip("/")

    def _ctxfeed(self):
        if self._ctx is None:
            try:
                c = ssl.create_default_context()
                c.check_hostname = False
                c.verify_mode = ssl.CERT_NONE
                self._ctx = c
            except Exception:
                self._ctx = False
        return self._ctx

    def _open(self, url, timeout=25):
        headers = {"User-Agent": UA, "Referer": self.host + "/", "Accept": "*/*"}
        try:
            req = Request(url, headers=headers)
            ctx = self._ctxfeed()
            if ctx:
                resp = urlopen(req, timeout=timeout, context=ctx)
            else:
                resp = urlopen(req, timeout=timeout)
            body = resp.read()
            ctype = resp.headers.get("Content-Type") or ""
            try:
                resp.close()
            except Exception:
                pass
            return body, ctype
        except Exception:
            return None, ""

    def _get(self, path):
        url = path if path.startswith("http") else self.host + path
        body, ctype = self._open(url)
        if not body:
            return ""
        try:
            return body.decode("utf-8", "ignore")
        except Exception:
            return ""

    def _clean(self, txt):
        t = re.sub(r'<[^>]+>', '', str(txt or ''))
        t = html_lib.unescape(t)
        return re.sub(r'\s+', ' ', t).strip()

    def _abs(self, u):
        u = html_lib.unescape(str(u or '')).strip().strip('"').strip("'")
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

    def _cards(self, h):
        out = []
        seen = set()
        pos = []
        for m in re.finditer(r'id="post-card-(\d+)"', h or ''):
            pos.append((m.start(), m.group(1)))
        total = len(pos)
        for idx in range(total):
            start = pos[idx][0]
            vid = pos[idx][1]
            if idx + 1 < total:
                nxt = pos[idx + 1][0]
            else:
                nxt = start + 6000
            seg = h[start:min(nxt, start + 6000)]
            name = ""
            tm = re.search(r'post-card-title[^>]*>([\s\S]{0,600}?)</h2>', seg)
            if tm:
                raw = re.sub(r'<div class="wrap">[\s\S]*?</div>', '', tm.group(1))
                name = self._clean(raw)
            name = re.sub(r'^(热搜\s*HOT|HOT|置顶|推荐)\s*', '', name).strip()
            if not name or re.match(r'^\d+$', name) or vid in seen:
                continue
            if "视频无法播放" in name or "DNS" in name.upper():
                continue
            seen.add(vid)
            pic = ""
            pm = re.search(r"loadBannerDirect\('([^']+)'", seg)
            if pm is None:
                pm = re.search("background-image:\\s*url\\(([^)]*)\\)", seg)
            if pm is None:
                pm = re.search("(?:data-src|src)=\"([^\"]+)\"", seg)
            if pm:
                pic = self._abs(pm.group(1))
            out.append({"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": ""})
        return out

    def _classes(self, h):
        cls = []
        seen = set()
        for m in re.finditer(r'<a[^>]*href="[^"]*/category/([a-z0-9_-]+)/"[^>]*>([^<]{1,20})</a>', h or ''):
            slug = m.group(1)
            nm = self._clean(m.group(2))
            if not slug or not nm or slug in seen:
                continue
            seen.add(slug)
            cls.append({"type_id": slug, "type_name": nm})
            if len(cls) >= 10:
                break
        if cls:
            return [{"type_id": "all", "type_name": "推荐"}] + cls
        return list(DEF_CATS)

    def homeContent(self, filter=None):
        h = self._get("/")
        return {"class": self._classes(h), "filters": {}, "list": self._cards(h)}

    def homeVideoContent(self):
        return {"list": self._cards(self._get("/"))}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        page = 1
        if str(pg).isdigit():
            page = int(pg)
        slug = str(tid or "dy")
        if slug == "all":
            path = "/" if page <= 1 else "/page/" + str(page) + "/"
        elif page > 1:
            path = "/page/" + str(page) + "/"
        else:
            path = "/category/" + slug + "/"
        cards = self._cards(self._get(path))
        return {"list": cards, "page": page, "pagecount": 999, "limit": len(cards), "total": 999999}

    def searchContent(self, key, quick=False, pg="1"):
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        cards = self._cards(self._get("/search/" + quote(kw) + "/"))
        return {"list": cards, "page": 1, "pagecount": 1, "limit": len(cards), "total": len(cards)}

    def detailContent(self, ids):
        vid = ""
        if ids:
            vid = str(ids[0])
        if not vid:
            return {"list": []}
        h = self._get("/archives/" + vid + "/")

        title = ""
        m = re.search(r'<meta itemprop="headline"[^>]*content="([^"]+)"', h)
        if m:
            title = self._clean(m.group(1))
        if not title:
            m = re.search(r'<meta property="og:title"[^>]*content="([^"]+)"', h)
            if m:
                title = self._clean(m.group(1))
        if not title:
            m = re.search(r'<title>([^<]+)</title>', h)
            if m:
                title = self._clean(m.group(1)).split(" - ")[0]
        if not title:
            title = vid

        pic = ""
        m = re.search(r'<meta property="og:image"[^>]*content="([^"]+)"', h)
        if m:
            pic = self._abs(m.group(1))
        if not pic:
            m = re.search(r"loadBannerDirect\('([^']+)'", h)
            if m:
                pic = self._abs(m.group(1))

        desc = ""
        m = re.search(r'<meta name="description"[^>]*content="([^"]*)"', h)
        if m:
            desc = self._clean(m.group(1))
        if desc == title:
            desc = ""

        tags = []
        m = re.search(r'<meta name="keywords"[^>]*content="([^"]*)"', h)
        if m:
            for t in re.split(r'[,，]', self._clean(m.group(1))):
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
        for cm in re.finditer("data-config=(?:'([^']*)'|\"([^\"]*)\")", h):
            cfg = cm.group(1)
            if not cfg:
                cfg = cm.group(2)
            u = ""
            if cfg:
                try:
                    obj = json.loads(html_lib.unescape(cfg))
                    if isinstance(obj, dict):
                        vv = obj.get("video")
                        if isinstance(vv, dict):
                            u = str(vv.get("url") or "").strip()
                except Exception:
                    u = ""
                if not u:
                    um = re.search("[\"']url[\"']\\s*:\\s*[\"']([^\"']+)[\"']", cfg)
                    if um:
                        u = um.group(1)
            u = u.replace("\\/", "/").strip()
            if u.startswith("http") and u not in plays:
                plays.append(u)
        if not plays:
            for u in re.findall("https?://[^\"'\\s<>]+?\\.m3u8[^\"'\\s<>]*", h.replace("\\/", "/")):
                if u not in plays:
                    plays.append(u)

        eps = []
        for k in range(len(plays)):
            nm = "正片"
            if len(plays) > 1:
                nm = "第" + str(k + 1) + "集"
            eps.append(nm + "$" + self._proxy(plays[k]))
        play = "#".join(eps)

        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
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
        header = {"User-Agent": UA, "Referer": self.host + "/"}
        if u.startswith("http"):
            return {"parse": 0, "jx": 0, "playUrl": "", "url": u, "header": header}
        return {"parse": 1, "jx": 0, "playUrl": "", "url": u, "header": header}

    def proxy(self, param):
        return self.localProxy(param)

    def localProxy(self, param):
        import urllib.parse as up
        if isinstance(param, str):
            text = param.strip()
            if text.startswith("http"):
                param = dict(up.parse_qsl(up.urlsplit(text).query))
            elif text.startswith("{"):
                try:
                    param = json.loads(text)
                except Exception:
                    param = {}
            else:
                param = dict(up.parse_qsl(text))
        if not isinstance(param, dict):
            param = {}
        target = str(param.get("url") or "").strip()
        if not target:
            return [404, "text/plain", b"Not Found", {}]
        body, ctype = self._open(target, 30)
        if body is None:
            return [502, "text/plain", b"upstream failed", {}]
        low = body[:16].lower()
        if b"#extm3u" in low:
            text = body.decode("utf-8", "ignore")
            lines = []
            for ln in text.splitlines():
                s = ln.strip()
                if not s:
                    lines.append(ln)
                    continue
                if s.startswith("#"):
                    lines.append(re.sub("URI=\"([^\"]+)\"", lambda mm: 'URI="' + self._proxy(urljoin(target, mm.group(1))) + '"', ln))
                else:
                    lines.append(self._proxy(urljoin(target, s)))
            data = "\n".join(lines).encode("utf-8")
            return [200, "application/vnd.apple.mpegurl", data, {"Access-Control-Allow-Origin": "*"}]
        if body[:1] == b"G":
            return [200, "video/mp2t", body, {"Access-Control-Allow-Origin": "*"}]
        return [200, ctype or "application/octet-stream", body, {"Access-Control-Allow-Origin": "*"}]

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return ".m3u8" in u or ".mp4" in u

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return []

    def destroy(self):
        pass
