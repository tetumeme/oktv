# -*- coding: utf-8 -*-
"""XP天堂（qarnuvo.cc）自建源 — 纯标准库。

站点结构（2026-11 实测）：
  列表  /videos/?page=N   卡片 div.video-img-box > a[href=/videos/{slug}/]
        img.zximg[alt=标题][z-image-loader-url=封面]
  分类  首页 .app-nav 里的 a.tjtagmanager -> /theme/{id}/{sort}/
  详情  /videos/{slug}/   页面内 var hlsUrl = "/api.php/m3u8/fzdecode?path=...&videoId=..."
  播放  该接口直接返回标准 m3u8，分片是绝对地址（fangz-pic1.bedfpk.cn）

注意：封面与 51短剧 同源，都是图床密文，只能靠页面 worker 解密后转 blob，
      TVBox 拿不到解密结果，这里封面留空。
"""

import html as html_lib
import re
import ssl
from urllib.request import Request, urlopen

HOST = "https://qarnuvo.cc"
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

    def getName(self):
        return "XP天堂"

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

    def _abs(self, u):
        u = str(u or "").strip()
        if not u:
            return ""
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        return u

    def _cards(self, h):
        out = []
        seen = set()
        for m in re.finditer(r'<div class="video-img-box"', h or ""):
            seg = h[m.start():m.start() + 1800]
            hm = re.search(r'href="(/videos/[^"]+/)"', seg)
            if not hm:
                continue
            vid = hm.group(1).strip("/").split("/")[-1]
            if not vid or vid in seen:
                continue
            seen.add(vid)
            am = re.search(r'alt="([^"]*)"', seg)
            pm = re.search(r'<img[^>]+src="([^"]+)"', seg)
            out.append({
                "vod_id": vid,
                "vod_name": self._clean(am.group(1)) if am else vid,
                "vod_pic": self._abs(pm.group(1)) if pm else "",
                "vod_remarks": "",
            })
        return out

    def _classes(self, h):
        cls = [{"type_id": "/videos/", "type_name": "最新"}]
        seen = {"/videos/"}
        for m in re.finditer(r'<a[^>]*href="(/theme/\d+/[^"]*)"[^>]*>([\s\S]{0,60}?)</a>', h or ""):
            tid = m.group(1)
            name = self._clean(m.group(2))
            if not name or tid in seen:
                continue
            seen.add(tid)
            cls.append({"type_id": tid, "type_name": name})
            if len(cls) >= 10:
                break
        return cls

    def homeContent(self, filter=None):
        h = self._get("/")
        cards = self._cards(h)
        if not cards:
            cards = [{
                "vod_id": "diag",
                "vod_name": "诊断 h=%d %s" % (len(h), h[:80].replace("\n", " ")),
                "vod_pic": "",
                "vod_remarks": "",
            }]
        return {"class": self._classes(h), "filters": {}, "list": cards}

    def homeVideoContent(self):
        return {"list": self._cards(self._get("/"))}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        page = int(pg) if str(pg).isdigit() else 1
        path = str(tid or "/videos/")
        if page > 1:
            sep = "&" if "?" in path else "?"
            path = path + sep + "page=%d" % page
        cards = self._cards(self._get(path))
        return {"list": cards, "page": page, "pagecount": 999,
                "limit": len(cards), "total": len(cards)}

    def searchContent(self, key, quick=False, pg="1"):
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        cards = self._cards(self._get("/search/?q=" + quote(kw)))
        return {"list": cards, "page": 1, "pagecount": 1,
                "limit": len(cards), "total": len(cards)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        if not vid:
            return {"list": []}
        h = self._get("/videos/" + quote(vid) + "/")
        title = ""
        m = re.search(r"<h1[^>]*>([\s\S]{0,200}?)</h1>", h)
        if m:
            title = self._clean(m.group(1))
        if not title:
            m = re.search(r'<meta property="og:title" content="([^"]+)"', h)
            title = self._clean(m.group(1)) if m else vid
        play = ""
        m = re.search(r"""hlsUrl\s*=\s*["']([^"']+)["']""", h)
        if m:
            play = self._abs(m.group(1).replace("\\/", "/"))
        diag = ""
        if not play:
            diag = "未取到播放地址｜h=%d｜含m3u8=%s｜头=%s" % (
                len(h), ("m3u8" in h), self._clean(h[:100]))
        return {"list": [{
            "vod_id": vid,
            "vod_name": title or vid,
            "vod_pic": "",
            "vod_remarks": "" if play else "无线路",
            "vod_content": diag,
            "vod_play_from": "XP天堂",
            "vod_play_url": ("正片$" + play) if play else "",
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
