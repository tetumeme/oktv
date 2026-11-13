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
import xml.etree.ElementTree as ET
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

    def _xml_item(self, v):
        def g(tag):
            return (v.findtext(tag) or "").strip()
        vid = g("id")
        if not vid:
            return None
        froms = []
        urls = []
        for dd in v.findall("dl/dd"):
            flag = dd.get("flag") or "xml"
            txt = (dd.text or "").strip()
            if not txt:
                continue
            froms.append(flag)
            urls.append(txt)
        return {
            "vod_id": vid,
            "vod_name": g("name") or vid,
            "vod_pic": g("pic"),
            "vod_remarks": g("note"),
            "vod_content": g("des"),
            "vod_play_from": "$$".join(froms),
            "vod_play_url": "$$".join(urls),
        }

    def _xml(self, query):
        if not self.api:
            return {}
        sep = "&" if "?" in self.api else "?"
        txt = self._get(self.api + sep + query)
        i = txt.find("<rss")
        if i < 0:
            return {}
        try:
            root = ET.fromstring(txt[i:])
        except Exception:
            return {}
        out = {"class": [], "list": []}
        clas = root.find("class")
        if clas is not None:
            for ty in clas.findall("ty"):
                tid = ty.get("id") or ""
                if tid:
                    out["class"].append({"type_id": tid, "type_name": (ty.text or tid).strip()})
        lst = root.find("list")
        if lst is not None:
            pc = lst.get("pagecount") or ""
            rc = lst.get("recordcount") or ""
            if pc.isdigit():
                out["pagecount"] = pc
            if rc.isdigit():
                out["total"] = rc
            for node in lst.findall("video"):
                item = self._xml_item(node)
                if item:
                    out["list"].append(item)
        return out

    def _data(self, query):
        j = self._api(query)
        if isinstance(j, dict) and isinstance(j.get("list"), list) and j.get("list"):
            return j
        if isinstance(j, dict) and isinstance(j.get("class"), list) and j.get("class"):
            return j
        return self._xml(query)

    def homeContent(self, filter=None):
        base = self._data("ac=list&pg=1")
        j = self._data("ac=detail&pg=1&pagesize=40")
        if not j.get("list"):
            j = self._data("ac=list&pg=1")
        cls = self._classes(base) or self._classes(j)
        return {"class": cls, "filters": {}, "list": self._items(j.get("list"))}

    def homeVideoContent(self):
        j = self._data("ac=detail&pg=1&pagesize=40")
        if not j.get("list"):
            j = self._data("ac=list&pg=1")
        return {"list": self._items(j.get("list"))}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        page = int(pg) if str(pg).isdigit() else 1
        t = str(tid or "")
        j = self._data("ac=detail&t=%s&pg=%d&pagesize=20" % (t, page))
        if not j.get("list"):
            j = self._data("ac=list&t=%s&pg=%d&pagesize=20" % (t, page))
        pc = j.get("pagecount")
        total = j.get("total")
        cards = self._items(j.get("list"))
        pcv = int(pc) if str(pc).isdigit() and int(pc) > 1 else 999
        tv = int(total) if str(total).isdigit() and int(total) > 0 else 999999
        return {
            "list": cards,
            "page": page,
            "pagecount": pcv,
            "limit": len(cards),
            "total": tv,
        }

    def searchContent(self, key, quick=False, pg="1"):
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        page = int(pg) if str(pg).isdigit() else 1
        j = self._data("ac=detail&wd=%s&pg=%d&pagesize=20" % (quote(kw), page))
        if not j.get("list"):
            j = self._data("ac=list&wd=%s&pg=%d&pagesize=20" % (quote(kw), page))
        return {"list": self._items(j.get("list")), "page": page,
                "pagecount": 999, "limit": 20, "total": 0}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        if not vid:
            return {"list": []}
        j = self._data("ac=detail&ids=%s" % quote(vid))
        arr = j.get("list") or []
        if not arr:
            return {"list": []}
        v = arr[0]
        name = str(v.get("vod_name") or vid)
        content = self._clean(v.get("vod_content") or v.get("vod_blurb") or "")
        # 采集站常把标题原样塞进 vod_content，与标题雷同时不重复显示
        if content:
            a = re.sub(r"\W", "", content)
            b = re.sub(r"\W", "", name)
            if a and (a == b or b.startswith(a) or a.startswith(b)):
                content = ""
        meta = []
        if v.get("vod_year"):
            meta.append(str(v.get("vod_year")))
        if v.get("vod_area"):
            meta.append(str(v.get("vod_area")))
        if v.get("vod_actor"):
            meta.append(str(v.get("vod_actor")))
        if v.get("vod_remarks"):
            meta.append(str(v.get("vod_remarks")))
        body = content
        if meta:
            body = (content + "\n" if content else "") + " · ".join(meta)
        return {"list": [{
            "vod_id": vid,
            "vod_name": str(v.get("vod_name") or vid),
            "vod_pic": str(v.get("vod_pic") or ""),
            "vod_remarks": str(v.get("vod_remarks") or ""),
            "vod_year": str(v.get("vod_year") or ""),
            "vod_area": str(v.get("vod_area") or ""),
            "vod_actor": str(v.get("vod_actor") or ""),
            "vod_director": str(v.get("vod_director") or ""),
            "vod_content": body,
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
