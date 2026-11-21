# -*- coding: utf-8 -*-
# 51吃瓜（51cg1）FongMi 源 v6
# 域名从 cg51.com 发布页解析；列表用 post-card，详情播放地址在 dplayer 的 data-config JSON。
import gzip
import html as html_lib
import json
import re
import ssl
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

PUB = "https://cg51.com/"
SITE = "https://avoid.sbazviql.cc"
UA = ("Mozilla/5.0 (Linux; Android 16; PKM110 Build/BP2A.250605.015) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.179 Mobile Safari/537.36")

DEF_CATS = [
    {"type_id": "mrds", "type_name": "每日大赛"},
    {"type_id": "whhj", "type_name": "网黄合集"},
    {"type_id": "mrdg", "type_name": "吃瓜榜单"},
    {"type_id": "qghj", "type_name": "瓜友点播"},
    {"type_id": "rdsj", "type_name": "热门大瓜"},
    {"type_id": "bkdg", "type_name": "必看大瓜"},
    {"type_id": "ysyl", "type_name": "成人视频"},
    {"type_id": "lldd", "type_name": "伦理道德"},
    {"type_id": "gcjq", "type_name": "国产视频"},
    {"type_id": "thjx", "type_name": "探花精选"},
    {"type_id": "xsxy", "type_name": "学生校园"},
    {"type_id": "whhl", "type_name": "网红黑料"},
    {"type_id": "snsn", "type_name": "骚男骚女"},
    {"type_id": "whmx", "type_name": "明星爆料"},
    {"type_id": "hwcg", "type_name": "海外吃瓜"},
    {"type_id": "rrcg", "type_name": "人人吃瓜"},
    {"type_id": "ldcg", "type_name": "领导干部"},
    {"type_id": "jpll", "type_name": "软萌甜妹"},
    {"type_id": "sjb", "type_name": "竞技吃瓜"},
    {"type_id": "qubk", "type_name": "吃瓜看戏"},
    {"type_id": "dcbq", "type_name": "擦边撩骚"},
    {"type_id": "zzs", "type_name": "性爱技巧"},
    {"type_id": "cgxw", "type_name": "吃瓜新闻"},
    {"type_id": "51djc", "type_name": "51原创短剧"},
    {"type_id": "yczq", "type_name": "原创博主"},
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
        self.host = SITE
        self._last = ""
        self._ctx = None
        self._resolved = False

    def init(self, extend=""):
        cfg = {}
        if extend:
            try:
                cfg = json.loads(extend)
            except Exception:
                cfg = {}
        host = ""
        if isinstance(cfg, dict):
            host = str(cfg.get("host") or "").strip()
        self._ctx = None
        self._resolved = False
        if host:
            self.host = host.rstrip("/")
            self._resolved = True
        else:
            self.host = SITE

    # ---------- 网络 ----------
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

    def _open(self, url, timeout=20, referer=None):
        headers = {
            "User-Agent": UA,
            "Referer": referer or (self.host + "/"),
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        try:
            req = Request(url, headers=headers)
            ctx = self._ctxfeed()
            if ctx:
                resp = urlopen(req, timeout=timeout, context=ctx)
            else:
                resp = urlopen(req, timeout=timeout)
            try:
                self._last = resp.geturl()
            except Exception:
                self._last = url
            body = resp.read()
            if (resp.headers.get("Content-Encoding") or "").lower() == "gzip":
                try:
                    body = gzip.decompress(body)
                except Exception:
                    pass
            ctype = resp.headers.get("Content-Type") or ""
            try:
                resp.close()
            except Exception:
                pass
            return body, ctype
        except Exception:
            return None, ""

    def _get(self, url, timeout=20):
        body, _ = self._open(url, timeout)
        if body is None:
            return ""
        return body.decode("utf-8", "ignore")

    # ---------- 域名 ----------
    def _resolve(self):
        if self._resolved:
            return self.host
        self._resolved = True
        page = self._get(PUB, 10)
        hosts = []
        for m in re.findall(r"https?://([a-z0-9][a-z0-9\-.]*\.(?:sbazviql\.cc|51cg1\.com))", page or ""):
            if m not in hosts:
                hosts.append(m)
        for h in hosts[:3]:
            base = "https://" + h
            if "post-card" in self._get(base + "/", 8):
                return self._origin(base)
        return self.host

    def _origin(self, fallback):
        m = re.match(r"(https?://[^/]+)", self._last or "")
        return m.group(1) if m else fallback

    # ---------- 解析 ----------
    def _pic(self, url):
        if not url:
            return ""
        try:
            return self.getProxyUrl({"url": url})
        except Exception:
            return url

    def _txt(self, s):
        s = re.sub(r"<[^>]+>", "", s or "")
        s = html_lib.unescape(s)
        return re.sub(r"\s+", " ", s).strip()

    def _cards(self, h):
        out = []
        for seg in re.split(r'<div class="post-card" id="post-card-', h or "")[1:]:
            m = re.match(r"(\d+)", seg)
            if not m:
                continue
            vid = m.group(1)
            t = re.search(r'<h2 class="post-card-title"[^>]*>(.*?)</h2>', seg, re.S)
            name = self._txt(t.group(1)) if t else vid
            b = re.search(r'x-bg-loader-url="([^"]+)"', seg)
            pic = self._pic(html_lib.unescape(b.group(1))) if b else ""
            out.append({"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": ""})
        return out

    # ---------- 入口 ----------
    def homeContent(self, filter=None):
        self.host = self._resolve()
        return {"class": DEF_CATS}

    def homeVideoContent(self):
        self.host = self._resolve()
        return {"list": self._cards(self._get(self.host + "/"))}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        self.host = self._resolve()
        p = int(pg) if str(pg).isdigit() else 1
        url = "%s/category/%s/" % (self.host, tid)
        if p > 1:
            url = "%s/category/%s/%d/" % (self.host, tid, p)
        vl = self._cards(self._get(url))
        return {"list": vl, "page": p, "pagecount": 999 if vl else p,
                "limit": len(vl) or 25, "total": 999}

    def searchContent(self, key, quick=False, pg="1"):
        self.host = self._resolve()
        p = int(pg) if str(pg).isdigit() else 1
        kw = quote(str(key or ""))
        url = "%s/search/%s/" % (self.host, kw)
        if p > 1:
            url = "%s/search/%s/%d/" % (self.host, kw, p)
        vl = self._cards(self._get(url))
        return {"list": vl, "page": p, "pagecount": 999 if vl else p,
                "limit": len(vl) or 25, "total": 999}

    def detailContent(self, ids):
        self.host = self._resolve()
        vid = str(ids[0]) if ids else ""
        h = self._get("%s/archives/%s/" % (self.host, vid))
        name = ""
        m = re.search(r'<meta property="og:title" content="([^"]*)"', h)
        if m:
            name = html_lib.unescape(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", h, re.S)
            if m:
                name = re.split(r"\s*\|\s*", html_lib.unescape(m.group(1)))[0]
        name = (name or "").replace("$", " ").replace("#", " ").strip()

        pic = ""
        for pat in (r'<meta property="og:image" content="([^"]*)"', r'x-bg-loader-url="([^"]+)"'):
            m = re.search(pat, h)
            if m:
                pic = self._pic(html_lib.unescape(m.group(1)))
                break

        desc = ""
        m = re.search(r'<meta name="description" content="([^"]*)"', h)
        if m:
            desc = html_lib.unescape(m.group(1))

        urls = []
        cfgs = re.findall(r'data-config="([^"]*)"', h) + re.findall(r"data-config='([^']*)'", h)
        for c in cfgs:
            try:
                j = json.loads(html_lib.unescape(c))
            except Exception:
                continue
            vv = j.get("video") if isinstance(j.get("video"), dict) else {}
            u = str(j.get("url") or vv.get("url") or "").strip()
            if u and u not in urls:
                urls.append(u)
        if not urls:
            return {"list": [], "msg": "无播放地址 len=%d cfg=%d" % (len(h), len(re.findall("data-config", h)))}

        play = "#".join(["线路%d$%s" % (i + 1, u) for i, u in enumerate(urls)])
        return {"list": [{
            "vod_id": vid,
            "vod_name": name or vid,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": "51吃瓜",
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

    # ---------- 代理（备用） ----------
    def proxy(self, param):
        return self.localProxy(param)

    def localProxy(self, param):
        if not isinstance(param, dict):
            param = {}
        target = str(param.get("url") or "").strip()
        if not target:
            return [404, "text/plain", b"Not Found", {}]
        body, ctype = self._open(target, 30)
        if body is None:
            return [502, "text/plain", b"upstream failed", {}]
        if b"#EXTM3U" in body[:16].upper():
            text = body.decode("utf-8", "ignore")
            base = target.rsplit("/", 1)[0] + "/"
            out = []
            for line in text.splitlines():
                s = line.strip()
                if s and not s.startswith("#"):
                    out.append(urljoin(base, s))
                else:
                    out.append(line)
            return [200, "application/vnd.apple.mpegurl", "\n".join(out).encode("utf-8"), {}]
        return [200, ctype or "application/octet-stream", body, {}]
