# -*- coding: utf-8 -*-
"""Youavhub（youavhub.com）Python 点播源 — 自建维护版（走官方采集接口）。

上游 clun.top/js/ss/youav.py 依赖 requests + bs4，Chaquopy 里两个都没有，源直接加载失败；
且它按旧模板 DOM（.vodlist_item / #bofy）解析，与现站 wntheme51 已对不上。
现站仍保留 MacCMS 采集接口，直接用它，零 HTML 解析：
  /api.php/provide/vod/?ac=list                      -> class 分类表 + 首页列表
  /api.php/provide/vod/?ac=videolist&t={tid}&pg={n}   -> 分类分页
  /api.php/provide/vod/?ac=detail&wd={kw}             -> 搜索
  /api.php/provide/vod/?ac=detail&ids={id}            -> 详情，vod_play_url 即 m3u8 直链
实测：分类 20/21/22/23/24/25…，日本AV(t=22) pagecount 944，搜索/详情均正常，
vod_play_url 形如「在线播放$https://.../index.m3u8」，playerContent 直接输出。
"""

import json
import ssl
from urllib.parse import urlencode

HOST = "https://youavhub.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

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
        self._classes = []

    def getName(self):
        return "Youavhub"

    def init(self, extend=""):
        self.host = HOST
        if isinstance(extend, str) and extend.strip().startswith("http"):
            self.host = extend.strip().rstrip("/")
        self._ctx = None

    def _ssl_ctx(self):
        if self._ctx is not None:
            return self._ctx
        ctx = None
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        except Exception:
            ctx = None
        self._ctx = ctx
        return ctx

    def _api(self, params):
        import urllib.request
        url = "%s/api.php/provide/vod/?%s" % (self.host, urlencode(params))
        hd = {"User-Agent": UA, "Accept": "application/json, */*",
              "Referer": self.host + "/"}
        try:
            req = urllib.request.Request(url, headers=hd)
            ctx = self._ssl_ctx()
            if ctx is not None:
                resp = urllib.request.urlopen(req, timeout=15, context=ctx)
            else:
                resp = urllib.request.urlopen(req, timeout=15)
            data = resp.read()
            try:
                resp.close()
            except Exception:
                pass
            return json.loads(data.decode("utf-8", "ignore"))
        except Exception:
            return {}

    @staticmethod
    def _item(it):
        return {
            "vod_id": str(it.get("vod_id") or ""),
            "vod_name": str(it.get("vod_name") or ""),
            "vod_pic": str(it.get("vod_pic") or ""),
            "vod_remarks": str(it.get("vod_remarks") or ""),
            "vod_year": str(it.get("vod_year") or ""),
            "vod_area": str(it.get("vod_area") or ""),
        }

    @staticmethod
    def _classes_of(j):
        out = []
        for c in (j.get("class") or []):
            tid = str(c.get("type_id") or "")
            nm = str(c.get("type_name") or "")
            if tid and nm:
                out.append({"type_id": tid, "type_name": nm})
        return out

    def homeContent(self, filter=None):
        j = self._api({"ac": "list"})
        cls = self._classes_of(j)
        self._classes = cls
        if not cls:
            cls = [{"type_id": "22", "type_name": "日本AV"}]
        cards = []
        j2 = self._api({"ac": "detail", "t": cls[0]["type_id"], "pg": 1})
        cards = [self._item(it) for it in (j2.get("list") or [])]
        if not cards:
            cards = [self._item(it) for it in (j.get("list") or [])]
        return {"class": cls, "filters": {}, "list": cards}

    def homeVideoContent(self):
        return {"list": self.homeContent().get("list") or []}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        page = int(pg) if str(pg).isdigit() else 1
        j = self._api({"ac": "detail", "t": str(tid), "pg": page})
        cards = [self._item(it) for it in (j.get("list") or [])]
        pc = int(j.get("pagecount") or 1)
        return {"list": cards, "page": page, "pagecount": pc,
                "limit": len(cards), "total": pc * max(len(cards), 1)}

    def searchContent(self, key, quick=False, pg="1"):
        j = self._api({"ac": "detail", "wd": str(key or "").strip()})
        cards = [self._item(it) for it in (j.get("list") or [])]
        return {"list": cards, "page": 1, "pagecount": 1,
                "limit": len(cards), "total": len(cards)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        if not vid:
            return {"list": []}
        j = self._api({"ac": "detail", "ids": vid})
        arr = j.get("list") or []
        if not arr:
            return {"list": []}
        it = arr[0]
        play_url = str(it.get("vod_play_url") or "")
        play_from = str(it.get("vod_play_from") or "youavhub")
        content = str(it.get("vod_content") or it.get("vod_blurb") or "").strip()
        lines = []
        if it.get("vod_remarks"):
            lines.append("【状态】%s" % it.get("vod_remarks"))
        if it.get("vod_year"):
            lines.append("【年份】%s" % it.get("vod_year"))
        if it.get("vod_area"):
            lines.append("【地区】%s" % it.get("vod_area"))
        if content:
            lines.append(content)
        return {"list": [{
            "vod_id": vid,
            "vod_name": str(it.get("vod_name") or vid),
            "vod_pic": str(it.get("vod_pic") or ""),
            "vod_year": str(it.get("vod_year") or ""),
            "vod_area": str(it.get("vod_area") or ""),
            "vod_remarks": str(it.get("vod_remarks") or ""),
            "vod_content": "\n".join(lines),
            "vod_play_from": play_from,
            "vod_play_url": play_url,
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        u = str(id or "")
        if "$" in u:
            u = u.split("$")[-1]
        if u.startswith("http"):
            return {"parse": 0, "jx": 0, "playUrl": "", "url": u,
                    "header": {"User-Agent": UA, "Referer": self.host + "/"}}
        j = self._api({"ac": "detail", "ids": u})
        arr = j.get("list") or []
        if arr:
            pu = str(arr[0].get("vod_play_url") or "")
            if "$" in pu:
                pu = pu.split("$")[-1]
            if pu.startswith("http"):
                return {"parse": 0, "jx": 0, "playUrl": "", "url": pu,
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
