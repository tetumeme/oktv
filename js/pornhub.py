# -*- coding: utf-8 -*-
"""Pornhub（cn.pornhub.com）自建源 — 纯标准库实现。

上游 py/Phb.py 依赖 pyquery + requests.Session，Chaquopy 里两个都没有且无 try 兜底，
导入即崩，所以重写。现站结构（2026-11 实测）：
  列表：/video?page=N（分类用 path+query，如 /video?o=mv）
  搜索：/video/search?search=关键词&page=N
  详情：/view_video.php?viewkey={vkey}
        - 列表卡片：<li ... data-video-vkey="{vkey}">，标题在 img 的 alt，封面 data-poster
        - 详情标题：<h1>…</h1>，封面 og:image
        - 播放：页面 flashvars 的 mediaDefinitions，每项
          {"height":1080,"format":"hls","videoUrl":"https:\/\/em-h.phncdn.com\/...\/master.m3u8?..."}
          （JSON 里是 \/ 转义，需还原），按 height 从高到低输出，直连播放。
"""

import html as html_lib
import json
import re
import ssl
from urllib.parse import quote

HOST = "https://cn.pornhub.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

CATEGORIES = [
    {"type_id": "video", "type_name": "最新视频"},
    {"type_id": "video?o=mv", "type_name": "最多观看"},
    {"type_id": "video?o=tr", "type_name": "最高评分"},
    {"type_id": "video?o=ht", "type_name": "最热"},
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
        return "Pornhub"

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

    def _get(self, path):
        import urllib.request
        url = path if path.startswith("http") else self.host + path
        hd = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        try:
            req = urllib.request.Request(url, headers=hd)
            ctx = self._ssl_ctx()
            if ctx is not None:
                resp = urllib.request.urlopen(req, timeout=25, context=ctx)
            else:
                resp = urllib.request.urlopen(req, timeout=25)
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
        for m in re.finditer(r'data-video-vkey="([A-Za-z0-9]+)"', h or ""):
            vk = m.group(1)
            if vk in seen:
                continue
            seg = h[m.start():m.start() + 5200]
            alt = re.search(r'alt="([^"]{3,160})"', seg)
            name = self._clean(alt.group(1)) if alt else ""
            if not name:
                continue
            poster = re.search(r'data-poster="([^"]+)"', seg)
            seen.add(vk)
            out.append({
                "vod_id": vk,
                "vod_name": name,
                "vod_pic": poster.group(1) if poster else "",
                "vod_remarks": "",
            })
        return out

    def homeContent(self, filter=None):
        return {"class": list(CATEGORIES), "filters": {},
                "list": self._cards(self._get("/video"))}

    def homeVideoContent(self):
        return {"list": self._cards(self._get("/video"))}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        page = int(pg) if str(pg).isdigit() else 1
        t = str(tid or "video")
        sep = "&" if "?" in t else "?"
        path = "/%s%spage=%d" % (t, sep, page)
        cards = self._cards(self._get(path))
        return {"list": cards, "page": page, "pagecount": 999,
                "limit": len(cards), "total": len(cards)}

    def searchContent(self, key, quick=False, pg="1"):
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        page = int(pg) if str(pg).isdigit() else 1
        path = "/video/search?search=%s&page=%d" % (quote(kw), page)
        cards = self._cards(self._get(path))
        return {"list": cards, "page": page, "pagecount": 999,
                "limit": len(cards), "total": len(cards)}

    def detailContent(self, ids):
        vk = str(ids[0]) if ids else ""
        if not vk:
            return {"list": []}
        h = self._get("/view_video.php?viewkey=%s" % quote(vk))
        if not h:
            return {"list": []}
        title = ""
        m = re.search(r"<h1[^>]*>([\s\S]{0,200}?)</h1>", h)
        if m:
            title = self._clean(m.group(1))
        if not title:
            m = re.search(r'property="og:title" content="([^"]+)"', h)
            title = self._clean(m.group(1)) if m else vk
        pic = ""
        m = re.search(r'property="og:image" content="([^"]+)"', h)
        if m:
            pic = m.group(1)
        eps = []
        for m in re.finditer(r'"height":(\d+)\s*,\s*"width":\d+[\s\S]{0,120}?"videoUrl":"([^"]+)"', h):
            try:
                ht = int(m.group(1))
            except Exception:
                continue
            u = m.group(2).replace("\\/", "/").replace("\\u0026", "&")
            if not u.startswith("http") or "#" in u:
                continue
            eps.append((ht, u))
        uniq = []
        seen = set()
        for ht, u in sorted(eps, key=lambda x: -x[0]):
            if u in seen:
                continue
            seen.add(u)
            uniq.append((ht, u))
        play = "#".join(["%dP$%s" % (ht, u) for ht, u in uniq])
        return {"list": [{
            "vod_id": vk,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": ("%d 条线路" % len(uniq)) if uniq else "",
            "vod_content": "",
            "vod_play_from": "Pornhub",
            "vod_play_url": play,
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        u = str(id or "")
        if "$" in u:
            u = u.split("$")[-1]
        u = u.replace("\\/", "/")
        if u.startswith("http"):
            return {"parse": 0, "jx": 0, "playUrl": "", "url": u,
                    "header": {"User-Agent": UA, "Referer": self.host + "/"}}
        return {"parse": 1, "jx": 0, "playUrl": "", "url": u,
                "header": {"Referer": self.host + "/"}}

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
