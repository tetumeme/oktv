# -*- coding: utf-8 -*-
# Manko 自建源 v1
# 列表/详情走 alpharomeo.shop/swx 接口，返回 {"data":"<base91>"}，解码后是 JSON 数组/对象
# 播放地址 wasabi_url_1 是 m3u8，直连被 Cloudflare 拦，必须走 9978 本地代理补 Referer

import json
import re
import ssl
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

HOST = "https://manko.fun"
API = "https://alpharomeo.shop/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

CLASSES = [
    {"type_id": "pop", "type_name": "最热"},
    {"type_id": "top", "type_name": "最高分"},
    {"type_id": "new", "type_name": "最新"},
    {"type_id": "sub", "type_name": "中文字幕"},
    {"type_id": "Censored", "type_name": "有码"},
    {"type_id": "Uncensored", "type_name": "无码"},
    {"type_id": "FC2", "type_name": "FC2"},
    {"type_id": "Leaked", "type_name": "流出"},
    {"type_id": "No Mosaic", "type_name": "无修正"},
]

B91 = ('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
       '!#$%&()*+,./:;<=>?@[]^_'
       '\x60'
       '{|}~"')


def b91decode(s):
    v = -1
    b = 0
    n = 0
    out = bytearray()
    for ch in s:
        c = B91.find(ch)
        if c < 0:
            continue
        if v < 0:
            v = c
        else:
            v += c * 91
            b |= v << n
            if (v & 8191) > 88:
                n += 13
            else:
                n += 14
            while n > 7:
                out.append(b & 255)
                b >>= 8
                n -= 8
            v = -1
    if v + 1:
        out.append((b | v << n) & 255)
    return bytes(out)


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
        cfg = {}
        if extend:
            try:
                cfg = json.loads(extend)
            except Exception:
                cfg = {}
        if isinstance(cfg, dict):
            hh = cfg.get("host")
            if hh:
                self.host = str(hh).rstrip("/")

    def _ctxfeed(self):
        if self._ctx is None:
            try:
                c = ssl.create_default_context()
                c.check_hostname = False
                c.verify_mode = ssl.CERT_NONE
                self._ctx = c
            except Exception:
                self._ctx = False
        return self._ctx

    def _open(self, url, timeout=25, api=False):
        headers = {
            "User-Agent": UA,
            "Referer": self.host + "/",
        }
        if api:
            headers["Origin"] = self.host
            headers["Accept"] = "application/json, text/plain, */*"
        else:
            headers["Accept"] = "*/*"
        try:
            req = Request(url, headers=headers)
            ctx = self._ctxfeed()
            if ctx:
                resp = urlopen(req, timeout=timeout, context=ctx)
            else:
                resp = urlopen(req, timeout=timeout)
            body = resp.read()
            ctype = resp.headers.get("Content-Type") or ""
            try:
                resp.close()
            except Exception:
                pass
            return body, ctype
        except Exception:
            return None, ""

    def _api(self, path):
        url = path if path.startswith("http") else API + path
        body, ctype = self._open(url, True)
        if not body:
            return None
        try:
            obj = json.loads(body.decode("utf-8", "ignore"))
        except Exception:
            return None
        if not isinstance(obj, dict):
            return obj
        data = obj.get("data")
        if not data:
            return obj
        try:
            raw = b91decode(str(data)).decode("utf-8", "ignore")
            return json.loads(raw)
        except Exception:
            return None

    def _proxy(self, url):
        return "http://127.0.0.1:9978/proxy?do=py&url=" + quote(url, safe="")

    def _media(self, url):
        hd = {"User-Agent": UA, "Referer": self.host + "/"}
        err = ""
        try:
            net = getattr(self, "net", None)
            if net is None:
                err = "no net"
            else:
                r = net.req(url, {"headers": hd, "buffer": 3})
                if isinstance(r, dict):
                    code = int(r.get("code") or 0)
                    if code == 200:
                        cv = r.get("content")
                        if isinstance(cv, bytearray):
                            cv = bytes(cv)
                        if isinstance(cv, bytes):
                            return cv, "", 200
                    err = "net " + str(code)
                else:
                    err = "net bad"
        except Exception as e:
            err = "net err " + str(e)[:60]
        body, ctype = self._open(url)
        if body is None:
            return None, err, 0
        return body, ctype, 200

    def _title(self, it):
        names = it.get("title_display_name")
        if isinstance(names, list):
            for n in names:
                if isinstance(n, dict):
                    if n.get("language") in ("zh", "zh-CN", "tw", "zh-TW"):
                        t = str(n.get("title") or "").strip()
                        if t:
                            return t
        return str(it.get("title") or "")

    def _item(self, it):
        vid = str(it.get("_id") or "")
        title = self._title(it)
        pic = str(it.get("wide_thumbnail") or it.get("thumbnail_image") or "")
        remark = str(it.get("share_date") or "")
        score = it.get("imdb_score")
        if score:
            if remark:
                remark = remark + " · " + str(score)
            else:
                remark = str(score)
        return {"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": remark}

    def _list(self, tid, page):
        q = "page=" + str(page) + "&size=24&can_manko=true"
        if tid == "pop":
            path = "swx/movie/search?" + q + "&most_popular=true"
        elif tid == "top":
            path = "swx/movie/search?" + q + "&top_rated=true"
        elif tid == "sub":
            path = "swx/movie/search?" + q + "&subtitle_link=true"
        elif tid == "new":
            path = "swx/movie/search?" + q
        else:
            path = "swx/movie/search?category=" + quote(tid) + "&" + q
        arr = self._api(path)
        if not isinstance(arr, list):
            return []
        return arr

    def homeContent(self, filter=None):
        items = self._list("pop", 1)
        return {"class": list(CLASSES), "filters": {}, "list": [self._item(x) for x in items]}

    def homeVideoContent(self):
        items = self._list("pop", 1)
        return {"list": [self._item(x) for x in items]}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        page = 1
        if str(pg).isdigit():
            page = int(pg)
        items = self._list(str(tid or "pop"), page)
        cards = [self._item(x) for x in items]
        return {"list": cards, "page": page, "pagecount": 999,
                "limit": len(cards), "total": 999999}

    def searchContent(self, key, quick=False, pg="1"):
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        page = 1
        if str(pg).isdigit():
            page = int(pg)
        arr = self._api("swx/searchBy?keyword=" + quote(kw) + "&by=title&page=" + str(page) + "&size=24")
        if not isinstance(arr, list):
            arr = []
        cards = [self._item(x) for x in arr]
        return {"list": cards, "page": page, "pagecount": 999,
                "limit": len(cards), "total": len(cards)}

    def detailContent(self, ids):
        vid = ""
        if ids:
            vid = str(ids[0])
        if not vid:
            return {"list": []}
        d = self._api("swx/movie/detail/" + vid)
        if not isinstance(d, dict):
            return {"list": [{"vod_id": vid, "vod_name": vid, "vod_pic": "",
                              "vod_remarks": "无数据", "vod_content": "",
                              "vod_play_from": "Manko", "vod_play_url": ""}]}

        title = self._title(d)
        if not title:
            title = vid
        pic = str(d.get("cover_image") or "")
        if not pic:
            backs = d.get("backdrop_images")
            if isinstance(backs, list) and backs:
                pic = str(backs[0])

        desc = str(d.get("discription") or "").strip()
        meta = []
        if d.get("video_duration"):
            meta.append("时长 " + str(d.get("video_duration")))
        if d.get("file_size_1"):
            meta.append("大小 " + str(d.get("file_size_1")))
        elif d.get("file_size_2"):
            meta.append("大小 " + str(d.get("file_size_2")))
        if d.get("share_date"):
            meta.append(str(d.get("share_date")))
        parts = []
        if desc:
            parts.append(desc)
        if meta:
            parts.append(" / ".join(meta))
        content = "\n".join(parts)

        play = ""
        u = str(d.get("wasabi_url_1") or "")
        if u.startswith("http"):
            play = "正片$" + self._proxy(u)

        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "" if play else "无线路",
            "vod_content": content if content else title,
            "vod_play_from": "Manko",
            "vod_play_url": play,
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        u = str(id or "")
        if "$" in u:
            u = u.split("$")[-1]
        header = {"User-Agent": UA, "Referer": self.host + "/"}
        if u.startswith("http"):
            return {"parse": 0, "jx": 0, "playUrl": "", "url": u, "header": header}
        return {"parse": 1, "jx": 0, "playUrl": "", "url": u, "header": header}

    def proxy(self, param):
        return self.localProxy(param)

    def localProxy(self, param):
        import urllib.parse as up
        if isinstance(param, str):
            text = param.strip()
            if text.startswith("http"):
                param = dict(up.parse_qsl(up.urlsplit(text).query))
            elif text.startswith("{"):
                try:
                    param = json.loads(text)
                except Exception:
                    param = {}
            else:
                param = dict(up.parse_qsl(text))
        if not isinstance(param, dict):
            param = {}
        target = str(param.get("url") or "").strip()
        if not target:
            return [404, "text/plain", b"Not Found", {}]

        body, ctype, perr = self._media(target)
        if body is None:
            return [502, "text/plain", ("upstream failed: " + str(perr)).encode("utf-8"), {}]

        low = body[:16].lower()
        if b"#extm3u" in low:
            text = body.decode("utf-8", "ignore")
            lines = []
            for ln in text.splitlines():
                s = ln.strip()
                if not s:
                    lines.append(ln)
                    continue
                if s.startswith("#"):
                    lines.append(re.sub("URI=\"([^\"]+)\"",
                                        lambda mm: 'URI="' + self._proxy(urljoin(target, mm.group(1))) + '"',
                                        ln))
                else:
                    lines.append(self._proxy(urljoin(target, s)))
            data = "\n".join(lines).encode("utf-8")
            return [200, "application/vnd.apple.mpegurl", data, {"Access-Control-Allow-Origin": "*"}]

        if body[:1] == b"G":
            return [200, "video/mp2t", body, {"Access-Control-Allow-Origin": "*"}]

        return [200, ctype or "application/octet-stream", body, {"Access-Control-Allow-Origin": "*"}]

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return ".m3u8" in u or ".mp4" in u

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return []

    def destroy(self):
        pass
