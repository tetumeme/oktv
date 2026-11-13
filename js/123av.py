# -*- coding: utf-8 -*-
"""123AV（123av.com）自建源 — 纯标准库。

站点结构（2026-11-14 实测）：
  列表  /cn/{tid}?page=N     卡片 div.card > a.card__cover[href=/cn/v/{id}]
  详情  /cn/v/{id}           播放 iframe 指向 https://sadie-shop.site/e/{code}?poster=...
  真流  GET https://sadie-shop.site/stream?id={code}
        -> {"status":"ok","media":{"stream":"https://.../video.m3u8","vtt":"..."}}

注意：站点把播放地址换成了 sadie-shop.site 的中转页，原 userScript 直接把
      iframe URL 当播放地址，所以一直没有线路；这里改成取 code 再问 stream 接口。
"""

import html as html_lib
import json
import re
import ssl
from urllib.parse import quote
from urllib.request import Request, urlopen

HOST = "https://123av.com"
EMBED = "https://sadie-shop.site"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

CATS = [
    {"type_id": "new", "type_name": "最近更新"},
    {"type_id": "hot", "type_name": "热门"},
    {"type_id": "recent", "type_name": "最新添加"},
    {"type_id": "censored", "type_name": "有码"},
    {"type_id": "uncensored", "type_name": "无码"},
    {"type_id": "uncensored-leaked", "type_name": "无码泄露"},
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

    def getName(self):
        return "123AV"

    def init(self, extend=""):
        self.host = HOST
        if isinstance(extend, str) and extend.strip().startswith("http"):
            self.host = extend.strip().rstrip("/")
        elif isinstance(extend, dict):
            h = str(extend.get("host") or "")
            if h.startswith("http"):
                self.host = h.rstrip("/")
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

    def _fetch(self, url, referer=None, origin=None):
        hd = {
            "User-Agent": UA,
            "Accept": "text/html,application/json,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        if referer:
            hd["Referer"] = referer
        if origin:
            hd["Origin"] = origin
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

    def _get(self, path):
        url = path if path.startswith("http") else self.host + path
        return self._fetch(url, referer=self.host + "/")

    @staticmethod
    def _clean(t):
        t = re.sub(r"<[^>]+>", "", str(t or ""))
        t = html_lib.unescape(t)
        return re.sub(r"\s+", " ", t).strip()

    def _cards(self, h):
        out = []
        seen = set()
        for m in re.finditer(r'<div class="card"', h or ""):
            seg = h[m.start():m.start() + 3200]
            hm = re.search(r'class="card__cover"[^>]*href="([^"]+)"', seg)
            if not hm:
                continue
            vm = re.search(r'/v/([^"?#/]+)', hm.group(1))
            if not vm:
                continue
            vid = vm.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            im = re.search(r'class="card__img"[^>]*src="([^"]+)"', seg)
            tm = re.search(r'class="card__title"[^>]*>([\s\S]{0,400}?)</', seg)
            dm = re.search(r'class="card__dur">([^<]*)<', seg)
            out.append({
                "vod_id": vid,
                "vod_name": self._clean(tm.group(1)) if tm else vid,
                "vod_pic": im.group(1) if im else "",
                "vod_remarks": self._clean(dm.group(1)) if dm else "",
            })
        return out

    def homeContent(self, filter=None):
        return {"class": list(CATS), "filters": {}, "list": self._cards(self._get("/cn/new"))}

    def homeVideoContent(self):
        return {"list": self._cards(self._get("/cn/new"))}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        page = int(pg) if str(pg).isdigit() else 1
        t = str(tid or "new")
        cards = self._cards(self._get("/cn/" + t + "?page=" + str(page)))
        return {"list": cards, "page": page, "pagecount": 999,
                "limit": len(cards), "total": len(cards)}

    def searchContent(self, key, quick=False, pg="1"):
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        page = int(pg) if str(pg).isdigit() else 1
        cards = self._cards(self._get("/cn/search?q=" + quote(kw) + "&page=" + str(page)))
        return {"list": cards, "page": page, "pagecount": 999,
                "limit": len(cards), "total": len(cards)}

    def _stream(self, code):
        txt = self._fetch(EMBED + "/stream?id=" + code,
                          referer=EMBED + "/e/" + code, origin=EMBED)
        try:
            j = json.loads(txt)
        except Exception:
            return ""
        media = j.get("media") or {}
        return str(media.get("stream") or "")

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        if not vid:
            return {"list": []}
        h = self._get("/cn/v/" + quote(vid))
        title = ""
        m = re.search(r"<h1[^>]*>([\s\S]{0,300}?)</h1>", h)
        if m:
            title = self._clean(m.group(1))
        if not title:
            m = re.search(r'property="og:title" content="([^"]+)"', h)
            title = self._clean(m.group(1)) if m else vid
        title = re.sub(r"\s*—\s*123AV.*$", "", title).strip()
        pic = ""
        m = re.search(r'property="og:image" content="([^"]+)"', h)
        if m:
            pic = m.group(1)
        stream = ""
        resp = ""
        codes = re.findall(r"sadie-shop\.site/e/([A-Za-z0-9_]+)", h)
        for code in codes:
            resp = self._fetch(EMBED + "/stream?id=" + code,
                               referer=EMBED + "/e/" + code, origin=EMBED)
            try:
                j = json.loads(resp)
                stream = str((j.get("media") or {}).get("stream") or "")
            except Exception:
                stream = ""
            if stream:
                break
        diag = "h=%d code=%d" % (len(h), len(codes))
        if not stream:
            diag = diag + " resp=" + self._clean(resp)[:90]
        return {"list": [{
            "vod_id": vid,
            "vod_name": title or vid,
            "vod_pic": pic,
            "vod_remarks": "" if stream else diag,
            "vod_content": "",
            "vod_play_from": "123AV",
            "vod_play_url": ("正片$" + stream) if stream else "",
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        u = str(id or "")
        if "$" in u:
            u = u.split("$")[-1]
        if u.startswith("http"):
            return {"parse": 0, "jx": 0, "playUrl": "", "url": u,
                    "header": {"User-Agent": UA, "Referer": EMBED + "/"}}
        return {"parse": 1, "jx": 0, "playUrl": "", "url": u,
                "header": {"Referer": EMBED + "/"}}

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return ".m3u8" in u or ".mp4" in u

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def getDependence(self):
        return []

    def destroy(self):
        pass
