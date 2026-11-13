# -*- coding: utf-8 -*-
"""Stripchat 直播源（py 实现）。

为什么不做成 TVBox 的 lives：
  lives 是静态 m3u/txt，流地址写死几分钟就失效。Stripchat 的流是
  edge-hls.doppiocdn.com/hls/{streamName}_auto/master/{streamName}_auto.m3u8
  其中 streamName 每个主播固定、重开播会变，所以每次从列表现取。

站点接口（2026-11 实测）：
  列表  /api/front/v2/models?primaryTag={girls|boys|couples|trans}&limit=N&offset=M
        返回 blocks[].models[]，字段 username / streamName / isOnline / previewUrlThumbSmall
  播放  见上面的 CDN 规则，直连带站点 Referer
"""

import json
import re
import ssl
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen

HOST = "https://zh.stripchat.com"
CDN = "https://edge-hls.doppiocdn.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

CATS = [
    {"type_id": "girls", "type_name": "女主播"},
    {"type_id": "boys", "type_name": "男主播"},
    {"type_id": "couples", "type_name": "情侣"},
    {"type_id": "trans", "type_name": "跨性别"},
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
        return "Stripchat"

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

    def _get(self, url):
        hd = {
            "User-Agent": UA,
            "Accept": "application/json,text/html,*/*;q=0.8",
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

    def _models(self, tag, offset, limit):
        url = "%s/api/front/v2/models?primaryTag=%s&limit=%d&offset=%d" % (
            self.host, quote(str(tag)), limit, offset)
        txt = self._get(url)
        try:
            j = json.loads(txt)
        except Exception:
            return []
        out = []
        for bl in (j.get("blocks") or []):
            for m in (bl.get("models") or []):
                if isinstance(m, dict):
                    out.append(m)
        return out

    def _cards(self, ms):
        out = []
        seen = set()
        for m in ms:
            u = str(m.get("username") or "").strip()
            s = str(m.get("streamName") or "").strip()
            if not u or not s or u in seen:
                continue
            seen.add(u)
            th = str(m.get("previewUrlThumbSmall") or "")
            if th.startswith("/"):
                th = self.host + th
            out.append({
                "vod_id": u + "|" + s,
                "vod_name": u,
                "vod_pic": th,
                "vod_remarks": "在线" if m.get("isOnline") else "离线",
            })
        return out

    def homeContent(self, filter=None):
        return {"class": list(CATS), "filters": {},
                "list": self._cards(self._models("girls", 0, 30))}

    def homeVideoContent(self):
        return {"list": self._cards(self._models("girls", 0, 30))}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        page = int(pg) if str(pg).isdigit() else 1
        off = (page - 1) * 30
        cards = self._cards(self._models(str(tid or "girls"), off, 30))
        return {"list": cards, "page": page, "pagecount": 999,
                "limit": len(cards), "total": 999999}

    def searchContent(self, key, quick=False, pg="1"):
        return {"list": [], "page": 1, "pagecount": 1}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        vid = unquote(vid)
        if "|" not in vid:
            return {"list": []}
        u, s = vid.split("|", 1)
        play = "%s/hls/%s_auto/master/%s_auto.m3u8" % (CDN, s, s)
        return {"list": [{
            "vod_id": vid,
            "vod_name": u,
            "vod_pic": "",
            "vod_remarks": "直播" if s else "离线",
            "vod_content": "主播：%s\n流：%s" % (u, play),
            "vod_play_from": "Stripchat",
            "vod_play_url": ("直播$" + play) if s else "",
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
        return ".m3u8" in str(url or "").lower()

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def getDependence(self):
        return []

    def destroy(self):
        pass
