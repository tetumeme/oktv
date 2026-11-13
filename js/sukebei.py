# -*- coding: utf-8 -*-
"""Sukebei（sukebei.nyaa.si）自建源 — 纯标准库。

站点结构（2026-11 实测）：
  列表  /?p=N            表格 tr.default：分类图标 / 标题链接 /view/{id} / magnet
  详情  /view/{id}       magnet 链接、文件列表、大小
  播放  这是磁力站，TVBox 不支持磁力播放，所以磁力链放在简介里方便复制。

原来 fun.json 里是 csp_Sukebei，但 pg.jar 里没有这个类，App 会把它降级成
「订阅管理」显示，所以改成自建 py。
"""

import html as html_lib
import re
import ssl
from urllib.request import Request, urlopen

HOST = "https://sukebei.nyaa.si"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

CATS = [
    {"type_id": "all", "type_name": "全部"},
    {"type_id": "1_1", "type_name": "Art - Anime"},
    {"type_id": "1_2", "type_name": "Art - Doujinshi"},
    {"type_id": "1_3", "type_name": "Art - Games"},
    {"type_id": "1_4", "type_name": "Art - Images"},
    {"type_id": "2_1", "type_name": "Real Life - Pictures"},
    {"type_id": "2_2", "type_name": "Real Life - Videos"},
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
        return "Sukebei"

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

    def _rows(self, h):
        out = []
        seen = set()
        for m in re.finditer(r'<tr class="default">', h or ""):
            seg = h[m.start():m.start() + 4200]
            vm = re.search(r'href="/view/(\d+)"', seg)
            if not vm:
                continue
            vid = vm.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            tm = re.search(r'href="/view/\d+" title="([^"]*)"', seg)
            mm = re.search(r'href="(magnet:[^"]+)"', seg)
            sm = re.search(r'class="text-center">([0-9.]+ [KMGTP]iB)</td>', seg)
            out.append({
                "vod_id": vid,
                "vod_name": self._clean(tm.group(1)) if tm else vid,
                "vod_pic": "",
                "vod_remarks": sm.group(1) if sm else "",
            })
        return out

    @staticmethod
    def _item(rows):
        return [{"vod_id": r["vod_id"], "vod_name": r["vod_name"],
                 "vod_pic": "", "vod_remarks": r["vod_remarks"]} for r in rows]

    def homeContent(self, filter=None):
        h = self._get("/")
        cards = self._item(self._rows(h))
        if not cards:
            cards = [{
                "vod_id": "diag",
                "vod_name": "诊断 首页无行",
                "vod_pic": "",
                "vod_remarks": "h=%d" % len(h),
            }]
        return {"class": list(CATS), "filters": {}, "list": cards}

    def homeVideoContent(self):
        return {"list": self._item(self._rows(self._get("/")))}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        page = int(pg) if str(pg).isdigit() else 1
        t = str(tid or "all")
        path = "/" if t in ("all", "") else "/?c=" + t
        if page > 1:
            path += ("&" if "?" in path else "?") + "p=%d" % page
        h = self._get(path)
        cards = self._item(self._rows(h))
        if not cards:
            cards = [{
                "vod_id": "diag",
                "vod_name": "诊断 tid=" + t,
                "vod_pic": "",
                "vod_remarks": "h=%d" % len(h),
            }]
        return {"list": cards, "page": page, "pagecount": 999,
                "limit": len(cards), "total": len(cards)}

    def searchContent(self, key, quick=False, pg="1"):
        from urllib.parse import quote
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        rows = self._rows(self._get("/?q=" + quote(kw)))
        return {"list": self._item(rows), "page": 1, "pagecount": 1,
                "limit": len(rows), "total": len(rows)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        if not vid:
            return {"list": []}
        h = self._get("/view/" + vid)
        title = ""
        m = re.search(r'<h3 class="panel-title">([\s\S]{0,300}?)</h3>', h)
        if m:
            title = self._clean(m.group(1))
        mm = re.search(r'href="(magnet:[^"]+)"', h)
        mag = html_lib.unescape(mm.group(1)) if mm else ""
        content = ("磁力：" + mag) if mag else "未找到磁力链接"
        return {"list": [{
            "vod_id": vid,
            "vod_name": title or vid,
            "vod_pic": "",
            "vod_remarks": "",
            "vod_content": content,
            "vod_play_from": "Sukebei",
            "vod_play_url": ("磁力$" + mag) if mag else "",
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        u = str(id or "")
        if "$" in u:
            u = u.split("$")[-1]
        return {"parse": 1, "jx": 0, "playUrl": "", "url": u,
                "header": {"User-Agent": UA}}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def getDependence(self):
        return []

    def destroy(self):
        pass
