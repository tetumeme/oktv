# -*- coding: utf-8 -*-
"""51短剧（blue.xdrgcewe.cc）Python 点播源 — 自建维护版。

上游 clun.top/js/ss/51短剧.py 已 404；GitHub 上游那份按旧 Nuxt 结构解析
（/play/{id}/{n}/ + __NUXT_DATA__ + data-xpch 卡片），现站换成 hg-51 皮肤
（与黄果剧场同源体系），旧正则全部失配。现站结构（2026-11 实测）：
  分类：/ai-duanju/ /ai-manju/ /ai-huanlian/ /ai-mogai/，分页 /{page}/
  搜索：/search/video/{关键词}/
  详情：/video/{id}/ ，h1 标题、og:image 封面、播放数据在
        <article class="hg-play__slide" data-play-id="{id}" data-play-src="{m3u8}">
卡片：<div class="hg-drama-card"> 内 a.hg-drama-card__cover-link[href=/video/{id}/]、
      img 的 data-src 才是真图（src 是占位 svg）、span.hg-drama-card__episode（全N集）
播放：data-play-src 直接是带 auth_key 的 m3u8 直链（HTML 里是 &amp;，需 unescape），
      playerContent 直连返回。
"""

import html as html_lib
import re
import ssl
from urllib.parse import quote

HOST = "https://blue.xdrgcewe.cc"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

CATEGORIES = [
    {"type_id": "ai-duanju", "type_name": "AI成人短剧"},
    {"type_id": "ai-manju", "type_name": "AI成人漫剧"},
    {"type_id": "ai-huanlian", "type_name": "AI换脸"},
    {"type_id": "ai-mogai", "type_name": "AI魔改"},
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
        return "51短剧"

    def init(self, extend=""):
        self.host = HOST
        if isinstance(extend, str) and extend.strip().startswith("http"):
            self.host = extend.strip().rstrip("/")
        self._ctx = None

    def _ctx_obj(self):
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
        import urllib.request
        url = path if path.startswith("http") else self.host + path
        hd = {"User-Agent": UA,
              "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
              "Accept-Language": "zh-CN,zh;q=0.9",
              "Referer": self.host + "/"}
        try:
            req = urllib.request.Request(url, headers=hd)
            ctx = self._ctx_obj()
            if ctx is not None:
                resp = urllib.request.urlopen(req, timeout=20, context=ctx)
            else:
                resp = urllib.request.urlopen(req, timeout=20)
            data = resp.read()
            try:
                resp.close()
            except Exception:
                pass
            return data.decode("utf-8", "ignore")
        except Exception:
            return ""

    def _abs(self, u):
        u = str(u or "").strip()
        if not u:
            return ""
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        return u

    @staticmethod
    def _clean(t):
        t = re.sub(r"<[^>]+>", "", str(t or ""))
        t = html_lib.unescape(t)
        return re.sub(r"\s+", " ", t).strip()

    def _cards(self, h):
        out = []
        seen = set()
        for blk in re.split(r'<div class="hg-drama-card"', h or "")[1:]:
            m = re.search(r'href="/video/(\d+)/"', blk)
            if not m:
                continue
            vid = m.group(1)
            if vid in seen:
                continue
            t = re.search(r'<img[^>]+alt="([^"]*)"', blk)
            name = self._clean(t.group(1)) if t else ""
            if not name:
                t2 = re.search(r'__title">\s*<a[^>]*>([\s\S]*?)</a>', blk)
                name = self._clean(t2.group(1)) if t2 else ""
            if not name:
                continue
            p = re.search(r'data-src="([^"]+)"', blk)
            if not p:
                p = re.search(r'<img[^>]+src="([^"]+)"', blk)
            e = re.search(r'__episode">([^<]*)<', blk)
            seen.add(vid)
            out.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": self._abs(p.group(1)) if p else "",
                "vod_remarks": self._clean(e.group(1)) if e else "",
            })
        return out

    def homeContent(self, filter=None):
        return {"class": list(CATEGORIES), "filters": {},
                "list": self._cards(self._get("/"))}

    def homeVideoContent(self):
        return {"list": self._cards(self._get("/"))}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        page = int(pg) if str(pg).isdigit() else 1
        path = "/%s/" % tid
        if page > 1:
            path += "%d/" % page
        cards = self._cards(self._get(path))
        return {"list": cards, "page": page, "pagecount": 999,
                "limit": len(cards), "total": len(cards)}

    def searchContent(self, key, quick=False, pg="1"):
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        cards = self._cards(self._get("/search/video/%s/" % quote(kw)))
        return {"list": cards, "page": 1, "pagecount": 1,
                "limit": len(cards), "total": len(cards)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        if not vid:
            return {"list": []}
        h = self._get("/video/%s/" % vid)
        if not h:
            return {"list": []}
        m = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", h)
        name = self._clean(m.group(1)) if m else vid
        pic = ""
        pm = re.search(r'property="og:image" content="([^"]*)"', h)
        if pm:
            pic = self._abs(pm.group(1))
        if not pic:
            pm = re.search(r'<img[^>]+data-src="([^"]+)"', h)
            if pm:
                pic = self._abs(pm.group(1))
        eps = []
        seen = set()
        for sm in re.finditer(r'data-play-id="(\d+)"[^>]*?data-play-src="([^"]+)"', h):
            src = html_lib.unescape(sm.group(2))
            if not src.startswith("http") or src in seen:
                continue
            seen.add(src)
            eps.append(("第%d集" % (len(eps) + 1), src))
        if not eps:
            return {"list": []}
        return {"list": [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": ("共%d集" % len(eps)) if len(eps) > 1 else "",
            "vod_content": "",
            "vod_play_from": "51短剧",
            "vod_play_url": "#".join(["%s$%s" % (lb, u) for lb, u in eps]),
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        u = html_lib.unescape(str(id or ""))
        if "$" in u:
            u = u.split("$")[-1]
        if u.startswith("http"):
            return {"parse": 0, "jx": 0, "playUrl": "", "url": u,
                    "header": {"User-Agent": UA, "Referer": self.host + "/"}}
        return {"parse": 1, "jx": 0, "playUrl": "", "url": u,
                "header": {"Referer": self.host + "/"}}

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return ".m3u8" in u or ".mp4" in u or ".ts" in u

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def getDependence(self):
        return []

    def destroy(self):
        pass
