# -*- coding: utf-8 -*-
"""通用苹果CMS采集源 — 纯标准库。

fun.json 里 ext 传采集站基址（例：https://xxx.com/api.php/provide/vod/），
所有 JSON 采集站共用这一份脚本。好处：
  1. UA / Referer 完全可控，绕开 App 内置通道对成人站的处理差异；
  2. 列表优先 ac=detail（带 vod_pic / vod_content），失败回落 ac=list；
  3. class 数组原样透传，分类不会丢；
  4. 详情直接取 vod_content，简介不再是空。
"""

import html as html_lib
import json
import re
import ssl
from urllib.parse import quote
from urllib.request import Request, urlopen

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
        self.api = ""
        self.host = ""
        self._ctx = None

    def getName(self):
        return "采集"

    def init(self, extend=""):
        api = ""
        if isinstance(extend, str):
            api = extend.strip()
        elif isinstance(extend, dict):
            api = str(extend.get("api") or "").strip()
        self.api = api
        self.host = ""
        m = re.match(r"(https?://[^/]+)", api)
        if m:
            self.host = m.group(1)
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
            "Accept": "application/json,text/xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        if self.host:
            hd["Referer"] = self.host + "/"
        try:
            req = Request(url, headers=hd)
            ctx = self._ssl_ctx()
            if ctx is not None:
                resp = urlopen(req, timeout=20, context=ctx)
            else:
                resp = urlopen(req, timeout=20)
            data = resp.read()
            try:
                resp.close()
            except Exception:
                pass
            return data.decode("utf-8", "ignore")
        except Exception:
            return ""

    def _api(self, query):
        if not self.api:
            return {}
        sep = "&" if "?" in self.api else "?"
        txt = self._get(self.api + sep + query)
        try:
            return json.loads(txt)
        except Exception:
            return {}

    @staticmethod
    def _clean(t):
        t = re.sub(r"<[^>]+>", "", str(t or ""))
        t = html_lib.unescape(t)
        return re.sub(r"\s+", " ", t).strip()

    def _items(self, arr):
        out = []
        for v in (arr or []):
            if not isinstance(v, dict):
                continue
            vid = str(v.get("vod_id") or "")
            if not vid:
                continue
            out.append({
                "vod_id": vid,
                "vod_name": str(v.get("vod_name") or vid),
                "vod_pic": str(v.get("vod_pic") or ""),
                "vod_remarks": str(v.get("vod_remarks") or ""),
            })
        return out

    def _classes(self, j):
        out = []
        for c in (j.get("class") or []):
            if not isinstance(c, dict):
                continue
            tid = str(c.get("type_id") or "")
            if not tid:
                continue
            out.append({"type_id": tid, "type_name": str(c.get("type_name") or tid)})
        return out

    def homeContent(self, filter=None):
        j = self._api("ac=detail&pg=1")
        if not j.get("list"):
            j = self._api("ac=list&pg=1")
        return {"class": self._classes(j), "filters": {}, "list": self._items(j.get("list"))}

    def homeVideoContent(self):
        j = self._api("ac=detail&pg=1")
        if not j.get("list"):
            j = self._api("ac=list&pg=1")
        return {"list": self._items(j.get("list"))}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        page = int(pg) if str(pg).isdigit() else 1
        t = str(tid or "")
        j = self._api("ac=detail&t=%s&pg=%d" % (t, page))
        if not j.get("list"):
            j = self._api("ac=list&t=%s&pg=%d" % (t, page))
        pc = j.get("pagecount")
        total = j.get("total")
        cards = self._items(j.get("list"))
        return {
            "list": cards,
            "page": page,
            "pagecount": int(pc) if str(pc).isdigit() else 999,
            "limit": len(cards),
            "total": int(total) if str(total).isdigit() else 0,
        }

    def searchContent(self, key, quick=False, pg="1"):
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        page = int(pg) if str(pg).isdigit() else 1
        j = self._api("ac=detail&wd=%s&pg=%d" % (quote(kw), page))
        if not j.get("list"):
            j = self._api("ac=list&wd=%s&pg=%d" % (quote(kw), page))
        return {"list": self._items(j.get("list")), "page": page,
                "pagecount": 999, "limit": 20, "total": 0}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        if not vid:
            return {"list": []}
        j = self._api("ac=detail&ids=%s" % quote(vid))
        arr = j.get("list") or []
        if not arr:
            return {"list": []}
        v = arr[0]
        content = v.get("vod_content") or v.get("vod_blurb") or ""
        return {"list": [{
            "vod_id": vid,
            "vod_name": str(v.get("vod_name") or vid),
            "vod_pic": str(v.get("vod_pic") or ""),
            "vod_remarks": str(v.get("vod_remarks") or ""),
            "vod_year": str(v.get("vod_year") or ""),
            "vod_area": str(v.get("vod_area") or ""),
            "vod_actor": str(v.get("vod_actor") or ""),
            "vod_director": str(v.get("vod_director") or ""),
            "vod_content": self._clean(content),
            "vod_play_from": str(v.get("vod_play_from") or ""),
            "vod_play_url": str(v.get("vod_play_url") or ""),
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        u = str(id or "")
        if "$" in u:
            u = u.split("$")[-1]
        hd = {"User-Agent": UA}
        if self.host:
            hd["Referer"] = self.host + "/"
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
