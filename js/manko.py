# -*- coding: utf-8 -*-
"""Manko（manko.fun）自建源。

站点结构（2026-11 实测）：
  列表  /cate-list?category={分类}&page={n}
        卡片 a[href="/movie-info/{id}?series=false"]，
        标题在 aria-label="View details for {番号}"，
        封面在 style 的 background-image: url(&quot;https://image.healertanker.com/...&quot;)
  详情  /movie-info/{id}?series=false   页面内直接有 mp4 直链（bxcdn.net）
  播放  直连 mp4，带站点 Referer

站点另有 sadie-shop.site 的 iframe 中转（与 123AV 同源），但这里能直接拿到 mp4，走简单路径。
"""

import html as html_lib
import re
import ssl
from urllib.parse import quote
from urllib.request import Request, urlopen

HOST = "https://manko.fun"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

CATS = [
    {"type_id": "Censored", "type_name": "有码"},
    {"type_id": "Uncensored", "type_name": "无码"},
    {"type_id": "No Mosaic", "type_name": "无码破解"},
    {"type_id": "Leaked", "type_name": "流出"},
    {"type_id": "FC2", "type_name": "FC2"},
    {"type_id": "Subtitle", "type_name": "中文字幕"},
    {"type_id": "Most Popular", "type_name": "最热"},
    {"type_id": "Top Rated", "type_name": "最高分"},
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

    def _cards(self, h):
        out = []
        seen = set()
        for m in re.finditer(r'<a[^>]*href="(/movie-info/[0-9a-zA-Z]+\?series=false)"[^>]*>([\s\S]{0,900}?)</a>', h or ""):
            href = m.group(1)
            hm = re.search(r"/movie-info/([0-9a-zA-Z]+)", href)
            if not hm:
                continue
            vid = hm.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            seg = m.group(0)
            al = re.search(r'aria-label="View details for ([^"]*)"', seg)
            name = self._clean(al.group(1)) if al else vid
            bi = re.search(r"background-image:\s*url\(&quot;([^&]+)&quot;", seg)
            if not bi:
                bi = re.search(r'background-image:\s*url\("([^"]+)"', seg)
            if not bi:
                bi = re.search(r"background-image:\s*url\(([^)\s]+)", seg)
            out.append({
                "vod_id": vid,
                "vod_name": name or vid,
                "vod_pic": bi.group(1) if bi else "",
                "vod_remarks": "",
            })
        return out

    def homeContent(self, filter=None):
        h = self._get("/cate-list?category=Most%20Popular&page=1")
        return {"class": list(CATS), "filters": {}, "list": self._cards(h)}

    def homeVideoContent(self):
        return {"list": self._cards(self._get("/cate-list?category=Most%20Popular&page=1"))}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        page = int(pg) if str(pg).isdigit() else 1
        cat = quote(str(tid or "Censored"))
        cards = self._cards(self._get("/cate-list?category=%s&page=%d" % (cat, page)))
        return {"list": cards, "page": page, "pagecount": 999,
                "limit": len(cards), "total": 999999}

    def searchContent(self, key, quick=False, pg="1"):
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        cards = self._cards(self._get("/search?keyword=" + quote(kw)))
        return {"list": cards, "page": 1, "pagecount": 1,
                "limit": len(cards), "total": len(cards)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        if not vid:
            return {"list": []}
        h = self._get("/movie-info/%s?series=false" % vid)
        title = ""
        m = re.search(r"<title>([^<|]+)", h)
        if m:
            title = self._clean(m.group(1))
        if not title:
            m = re.search(r'aria-label="View details for ([^"]*)"', h)
            title = self._clean(m.group(1)) if m else vid
        pic = ""
        m = re.search(r'<meta property="og:image" content="([^"]+)"', h)
        if m:
            pic = m.group(1)
        mp4s = []
        seen_u = set()
        for u in re.findall(r'https?://[^"\'\s<>\\]+\.mp4[^"\'\s<>\\]*', h):
            u = html_lib.unescape(u)
            if u in seen_u:
                continue
            seen_u.add(u)
            mp4s.append(u)
        play = ""
        if mp4s:
            play = "#".join(["正片$" + u for u in mp4s[:3]])
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
            "vod_play_from": "Manko",
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
        return None

    def getDependence(self):
        return []

    def destroy(self):
        pass
