# -*- coding: utf-8 -*-
"""今日看料（kanliao13.org）自建源。

站点结构（2026-11 实测）：
  列表  /category/{slug}/            卡片 article，链接 /archives/{id}/
  详情  /archives/{id}/              正文 video 标签，页面内直接有 m3u8
  分类  rdgz / dy / ks / douyu / hy（首页 nav 动态解析）
注意：站点有 CF，封面多为懒加载，列表取不到就用详情页 og:image。
"""

import html as html_lib
import re
import ssl
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

    def _ssl_ctx(self):
        if self._ctx is not None:
            return self._ctx
        c = None
        try:
            c = ssl.create_default_context()
            c.check_hostname = False
            c.verify_mode = ssl.CERT_NONE
        except Exception:
            c = None
        self._ctx = c
        return c

    def _get(self, path):
        url = path if path.startswith("http") else self.host + path
        hd = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        try:
            req = Request(url, headers=hd)
            ctx = self._ssl_ctx()
            if ctx is not None:
                resp = urlopen(req, timeout=25, context=ctx)
            else:
                resp = urlopen(req, timeout=25)
            data = resp.read()
            try:
                resp.close()
            except Exception:
                pass
            return data.decode("utf-8", "ignore")
        except Exception:
            return ""

    @staticmethod
    def _clean(t):
        t = re.sub(r"<[^>]+>", "", str(t or ""))
        t = html_lib.unescape(t)
        return re.sub(r"\s+", " ", t).strip()

    @staticmethod
    def _proxy(url):
        from urllib.parse import quote
        return "http://127.0.0.1:9978/proxy?do=py&url=" + quote(url, safe="")

    def _cards(self, h):
        out = []
        seen = set()
        for m in re.finditer(r'id="post-card-(\d+)"', h or ""):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            seg = h[m.start():m.start() + 3000]
            tm = re.search(r'post-card-title[^>]*>([\s\S]{0,400}?)</h2>', seg)
            name = self._clean(tm.group(1)) if tm else vid
            name = re.sub(r"^(热搜\s*HOT|HOT|置顶|推荐)\s*", "", name).strip()
            # 取不到标题（回落成 id）或标题就是纯数字的，是站点里的推广位，直接跳过
            if not name or re.fullmatch(r"\d+", name):
                continue
            pm = re.search(r"background-image:\s*url\(['\"]?([^'\")]+)", seg)
            if not pm:
                pm = re.search(r'<img[^>]+(?:data-src|src)="(https?://[^"]+)"', seg)
            out.append({
                "vod_id": vid,
                "vod_name": name or vid,
                "vod_pic": pm.group(1) if pm else "",
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
        from urllib.parse import quote
        cards = self._cards(self._get("/search/" + quote(kw) + "/"))
        return {"list": cards, "page": 1, "pagecount": 1,
                "limit": len(cards), "total": len(cards)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        if not vid:
            return {"list": []}
        h = self._get("/archives/%s/" % vid)
        title = ""
        m = re.search(r'<meta property="og:title" content="([^"]+)"', h)
        if m:
            title = self._clean(m.group(1))
        if not title:
            m = re.search(r"<title>([^<]+)</title>", h)
            title = self._clean(m.group(1)).split(" - ")[0] if m else vid
        pic = ""
        m = re.search(r'<meta property="og:image" content="([^"]+)"', h)
        if m:
            pic = m.group(1)
        urls = re.findall(r'https?://[^"\'\s<>\\]+\.m3u8[^"\'\s<>\\]*', h)
        play = ""
        if urls:
            play = "正片$" + self._proxy(html_lib.unescape(urls[0]))
        desc = ""
        m = re.search(r'<meta name="description" content="([^"]+)"', h)
        if m:
            desc = self._clean(m.group(1))
        return {"list": [{
            "vod_id": vid,
            "vod_name": title or vid,
            "vod_pic": pic,
            "vod_remarks": "" if play else "无线路",
            "vod_content": desc,
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

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return ".m3u8" in u or ".mp4" in u

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        import urllib.parse as _up
        if isinstance(param, str):
            text = param.strip()
            if text.startswith("http"):
                param = dict(_up.parse_qsl(_up.urlsplit(text).query))
            elif text.startswith("{"):
                import json as _json
                try:
                    param = _json.loads(text)
                except Exception:
                    param = {}
            else:
                param = dict(_up.parse_qsl(text))
        if not isinstance(param, dict):
            param = {}
        target = str(param.get("url") or "")
        if not target:
            return [404, "text/plain", b"Not Found", {}]
        hd = {"User-Agent": UA, "Referer": self.host + "/"}
        try:
            req = Request(target, headers=hd)
            ctx = self._ssl_ctx()
            if ctx is not None:
                resp = urlopen(req, timeout=30, context=ctx)
            else:
                resp = urlopen(req, timeout=30)
            data = resp.read()
            ct = (resp.headers.get("Content-Type") or "").lower()
            try:
                resp.close()
            except Exception:
                pass
        except Exception as e:
            return [500, "text/plain", ("proxy err: " + str(e)).encode("utf-8", "ignore"), {}]
        if ".m3u8" in target or "mpegurl" in ct:
            text2 = data.decode("utf-8", "ignore")
            out = []
            for ln in text2.splitlines():
                s = ln.strip()
                if s and not s.startswith("#"):
                    out.append(self._proxy(s if s.startswith("http") else ("%s%s" % (self.host, s if s.startswith("/") else "/" + s))))
                else:
                    out.append(ln)
            return [200, "application/vnd.apple.mpegurl", "\n".join(out).encode("utf-8"), {}]
        return [200, ct or "application/octet-stream", data, {}]

    def getDependence(self):
        return []

    def destroy(self):
        pass
