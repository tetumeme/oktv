# -*- coding: utf-8 -*-
"""乱伦仓库（rolizxwnoble 站群 → aissdxi.buzz）Python 点播源 — 自建维护版。

站点变迁（2026-11 实测）：
- 原 api（clun.top/js/ss/rolizxwnoble.py）对应的 host pnd27y1jh1.rolizxwnoble.buzz
  已整体解析失败；主域 rolizxwnoble.buzz 的 /vod/ 会 302 跳到随机子域
  <random>.aissdxi.buzz，站点改名「AI绅士短剧」，模板目录 template/aissdj。
- 列表：<div class="col-xs-6 col-md-2-4 video-element"> 卡片，a.video-cover 指向
  /detail/{id}/，封面 img.video-cover-img，标题 h4.video-title > a，浏览数 .video-view
- 分类：/aidj/AIchengrenduanju|AIchengrenmanju|AIhuanlian|AImogai/，分页 /page/{n}/
- 搜索：/index.php/ajax/suggest?mid=1&wd=关键词 -> {"list":[{"id":"3226","name":"..."}]}
- 详情：/detail/{id}/，标题 h1 > a，封面 og:image，简介 meta description，
  集数取「更新至N集 / 共N集」
- 播放：/play/{id}-1-{n}/ 页面内 var player_data={"url":"2751|1",...}；再请求
  /huangguo.php?ac=play&id=2751&ep=1（必须带 X-Requested-With: XMLHttpRequest）
  得到 {"code":1,"url":"/huangguo.php?ac=media&t=..."}；该 media 返回
  application/vnd.apple.mpegurl，内含 AES-128 EXT-X-KEY 与逐片 token，KEY 和分片
  同样走 /huangguo.php?ac=media&t= 且同样要 X-Requested-With，所以整条链必须经
  本地代理转发并改写 URL。

注意：站点子域是随机的，必须每次 init 时从 rolizxwnoble.buzz 的 302 Location 里取
当前 host，不能写死。
"""

import json
import re
import ssl
from urllib.parse import parse_qsl, quote, urljoin, urlsplit

try:
    from base.spider import Spider as BaseSpider
except Exception:
    BaseSpider = object

BOOT_URLS = [
    "https://rolizxwnoble.buzz/vod/",
    "https://rolizxwnoble.buzz/",
]
DEFAULT_HOST = "https://lactaskactand.aissdxi.buzz"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
CHROME_TLS12_CIPHERS = (
    "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:"
    "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:"
    "ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:"
    "ECDHE-RSA-AES128-SHA:ECDHE-RSA-AES256-SHA:AES128-SHA:AES256-SHA"
)

CATEGORIES = [
    {"type_id": "AIchengrenduanju", "type_name": "AI成人短剧"},
    {"type_id": "AIchengrenmanju", "type_name": "AI成人漫剧"},
    {"type_id": "AIhuanlian", "type_name": "AI换脸"},
    {"type_id": "AImogai", "type_name": "AI魔改"},
]

FILTERS = {}

CARD_KEY = '<div class="col-xs-6 col-md-2-4 video-element'
DETAIL_RE = re.compile(r'href="/detail/(\d+)/"')
PIC_RE = re.compile(r'<img[^>]+class="video-cover-img"[^>]*src="([^"]+)"')
TITLE_RE = re.compile(r'<h4 class="video-title">[\s\S]*?<a[^>]*>([\s\S]*?)</a>')
VIEW_RE = re.compile(r'class="video-view">\s*([^<]*)<')
OGIMG_RE = re.compile(r'property="og:image" content="([^"]*)"')
DESC_RE = re.compile(r'<meta name="description" content="([^"]*)"')
EPNUM_RE = re.compile(r'(?:更新至|共|全)\s*(\d+)\s*集')
PLAYDATA_RE = re.compile(r'var\s+player_data\s*=\s*(\{[\s\S]*?\})\s*</script>')

class Spider(BaseSpider):
    def __init__(self):
        try:
            BaseSpider.__init__(self)
        except Exception:
            pass
        self.host = DEFAULT_HOST
        self._booted = False
        self._ctx = None
        self._err = ""

    def getName(self):
        return "乱伦仓库"

    def init(self, extend=""):
        cfg = {}
        if isinstance(extend, dict):
            cfg = dict(extend)
        elif isinstance(extend, str) and extend.strip():
            t = extend.strip()
            if t.startswith("{"):
                try:
                    p = json.loads(t)
                    if isinstance(p, dict):
                        cfg = p
                except Exception:
                    cfg = {}
            elif t.startswith("http"):
                cfg = {"site": t}
        site = str(cfg.get("site", "") or "").strip().rstrip("/")
        if site.startswith("http"):
            self.host = site
            self._booted = True
        self._ctx = None
        self._boot()

    # ---------------- 网络 ----------------
    def _ssl_ctx(self):
        if self._ctx is not None:
            return self._ctx
        ctx = None
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            try:
                ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            except Exception:
                pass
            try:
                ctx.set_ciphers(CHROME_TLS12_CIPHERS)
            except Exception:
                pass
            try:
                ctx.set_ecdh_curve("X25519")
            except Exception:
                pass
        except Exception:
            ctx = None
        self._ctx = ctx
        return ctx

    def _boot(self):
        if self._booted:
            return self.host
        import urllib.request
        for u in BOOT_URLS:
            try:
                req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "*/*"})
                resp = urllib.request.urlopen(req, timeout=12, context=self._ssl_ctx())
                final = resp.geturl() or u
                try:
                    resp.read(256)
                except Exception:
                    pass
                try:
                    resp.close()
                except Exception:
                    pass
                p = urlsplit(final)
                if p.scheme and p.netloc:
                    self.host = "%s://%s" % (p.scheme, p.netloc)
                    self._booted = True
                    self._err = ""
                    return self.host
            except Exception as e:
                self._err = type(e).__name__
        self._booted = True
        return self.host

    def _open(self, url, referer=None, ajax=False, binary=False, timeout=12):
        import urllib.request
        hd = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "zh-CN,zh;q=0.9"}
        if referer:
            hd["Referer"] = referer
        if ajax:
            hd["X-Requested-With"] = "XMLHttpRequest"
        try:
            req = urllib.request.Request(url, headers=hd)
            resp = urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx())
            data = resp.read()
            try:
                resp.close()
            except Exception:
                pass
            if data:
                self._err = ""
                if binary:
                    return data
                try:
                    return data.decode("utf-8")
                except Exception:
                    return data.decode("gbk", "ignore")
        except Exception as e:
            self._err = type(e).__name__
        return b"" if binary else ""

    def _html(self, path, ajax=False):
        url = path if path.startswith("http") else self.host + path
        return self._open(url, referer=self.host + "/", ajax=ajax)

    def _abs(self, u):
        u = str(u or "").strip()
        if not u:
            return ""
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        return u

    @staticmethod
    def _clean(t):
        t = str(t or "")
        t = re.sub(r"<[^>]+>", "", t)
        t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        t = t.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
        return t.replace("$", "＄").replace("#", "＃").strip()

    # ---------------- 列表 ----------------
    def homeContent(self, filter=None):
        return {
            "class": list(CATEGORIES),
            "filters": dict(FILTERS),
            "list": self._list(CATEGORIES[0]["type_id"], 1)["list"],
        }

    def homeVideoContent(self):
        return {"list": self._list(CATEGORIES[0]["type_id"], 1)["list"]}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        ret = self._list(str(tid), pg)
        if not ret.get("list"):
            ret["msg"] = ("加载失败：" + self._err) if self._err else "暂无数据"
        return ret

    def searchContent(self, key, quick=False, pg="1"):
        kw = str(key or "").strip()
        if not kw:
            return {"list": [], "msg": "关键词为空"}
        out = []
        txt = self._html("/index.php/ajax/suggest?mid=1&wd=" + quote(kw), ajax=True)
        try:
            j = json.loads(txt or "{}")
            for it in (j.get("list") or []):
                vid = str(it.get("id") or "").strip()
                nm = self._clean(it.get("name") or "")
                if not vid or not nm:
                    continue
                if not vid.isdigit():
                    continue
                out.append({
                    "vod_id": "detail/%s" % vid,
                    "vod_name": nm,
                    "vod_pic": "",
                    "vod_remarks": "",
                    "style": {"type": "rect", "ratio": 0.56},
                })
        except Exception:
            pass
        if not out and self._err:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 0,
                    "total": 0, "msg": "搜索失败：" + self._err}
        return {"list": out, "page": 1, "pagecount": 1, "limit": len(out), "total": len(out)}

    def _list(self, tid, pg):
        page = int(pg) if str(pg).isdigit() else 1
        path = "/aidj/%s/" % quote(str(tid))
        if page > 1:
            path += "page/%d/" % page
        self._boot()
        html = self._html(path)
        if not html:
            self._booted = False
            self._boot()
            html = self._html(path)
        cards = self._cards(html or "")
        return {"list": cards, "page": page, "pagecount": 1,
                "limit": len(cards), "total": len(cards)}

    def _cards(self, html):
        out = []
        src = html or ""
        pos = [m.start() for m in re.finditer(re.escape(CARD_KEY), src)]
        for i, p in enumerate(pos):
            end = pos[i + 1] if i + 1 < len(pos) else min(len(src), p + 2000)
            item = self._card(src[p:end])
            if item:
                out.append(item)
        return out

    def _card(self, blk):
        m = DETAIL_RE.search(blk)
        if not m:
            return None
        vid = m.group(1)
        tm = TITLE_RE.search(blk)
        title = self._clean(tm.group(1)) if tm else ""
        if not title:
            return None
        pm = PIC_RE.search(blk)
        if not pm:
            pm = re.search(r'<img[^>]+src="([^"]+)"', blk)
        vm = VIEW_RE.search(blk)
        remark = self._clean(vm.group(1)) if vm else ""
        return {
            "vod_id": "detail/%s" % vid,
            "vod_name": title,
            "vod_pic": self._abs(pm.group(1)) if pm else "",
            "vod_remarks": remark,
            "style": {"type": "rect", "ratio": 0.56},
        }

    # ---------------- 详情 ----------------
    def detailContent(self, ids):
        out = []
        for ident in (ids or []):
            try:
                item = self._detail(str(ident))
            except Exception:
                item = None
            if item:
                out.append(item)
        if not out:
            return {"list": [], "msg": "详情加载失败"}
        return {"list": out}

    def _detail(self, ident):
        s = str(ident or "").strip()
        if s.startswith("detail/"):
            s = s.split("/", 1)[1]
        vid = s.strip("/")
        html = self._html("/detail/%s/" % quote(vid))
        if not html:
            return None
        name = ""
        m = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            name = vid
        pic = ""
        pm = OGIMG_RE.search(html)
        if pm:
            pic = self._abs(pm.group(1))
        desc = ""
        dm = DESC_RE.search(html)
        if dm:
            desc = self._clean(dm.group(1))
        total = 0
        em = EPNUM_RE.search(html)
        if em:
            total = int(em.group(1))
        eps = []
        if total > 1:
            i = 1
            while i <= total:
                eps.append(("第%d集" % i, "ep|%s|%d" % (vid, i)))
                i += 1
        else:
            eps.append(("正片", "ep|%s|1" % vid))
        lines = []
        if total:
            lines.append("【共】%d 集" % total)
        if desc:
            lines.append(desc)
        return {
            "vod_id": "detail/%s" % vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": "\n".join(lines),
            "vod_remarks": ("全%d集" % total) if total else "",
            "vod_play_from": "乱伦仓库",
            "vod_play_url": "#".join(["%s$%s" % (lb, pid) for lb, pid in eps]),
        }

    # ---------------- 播放与本地代理 ----------------
    def getProxyUrl(self, local=True):
        return "http://127.0.0.1:9978/proxy?do=py"

    def _proxy(self, url):
        import urllib.parse as up
        try:
            base = self.getProxyUrl(True) or "http://127.0.0.1:9978/proxy?do=py"
        except Exception:
            base = "http://127.0.0.1:9978/proxy?do=py"
        sep = "&" if "?" in base else "?"
        return "%s%stype=ll&url=%s" % (base, sep, up.quote(str(url or ""), safe=""))

    @staticmethod
    def _split_play(play_id):
        parts = str(play_id or "").split("|")
        if len(parts) >= 3 and parts[0] == "ep":
            return parts[1], parts[2]
        return "", ""

    def playerContent(self, flag, id, vipFlags=None):
        import time
        try:
            cur = str(id or "").split("$$$")[0].split("#")[0]
            sep = cur.rfind("$")
            pid = (cur[sep + 1:] if sep >= 0 else cur).strip()
            vid, ep = self._split_play(pid)
            if not vid:
                return {"parse": 1, "jx": 0, "playUrl": "", "url": "",
                        "header": {"Referer": self.host + "/"}}
            path = "/play/%s-1-%s/" % (vid, ep)
            html = self._html(path)
            if not html:
                return {"parse": 1, "jx": 0, "playUrl": "", "url": "",
                        "header": {"Referer": self.host + "/"}, "msg": "播放页获取失败"}
            media_id = ""
            media_ep = ""
            m = PLAYDATA_RE.search(html)
            if m:
                try:
                    j = json.loads(m.group(1))
                    u = str(j.get("url") or "")
                    if "|" in u:
                        a, b = u.split("|", 1)
                        media_id = a.strip()
                        media_ep = b.strip()
                except Exception:
                    media_id = ""
            if not media_id:
                media_id = vid
                media_ep = ep
            api_url = "%s/huangguo.php?ac=play&id=%s&ep=%s&_=%d" % (
                self.host, quote(str(media_id)), quote(str(media_ep)),
                int(time.time() * 1000))
            txt = self._open(api_url, referer=self.host + path, ajax=True)
            media = ""
            try:
                j = json.loads(txt or "{}")
                media = str(j.get("url") or "")
            except Exception:
                media = ""
            if not media:
                return {"parse": 1, "jx": 0, "playUrl": "", "url": "",
                        "msg": "取播放地址失败：" + (self._err or "empty")}
            if not media.startswith("http"):
                media = self.host + media
            return {
                "parse": 0, "jx": 0, "playUrl": "",
                "url": self._proxy(media),
                "header": {"Referer": self.host + "/", "User-Agent": UA},
                "format": "application/x-mpegURL",
            }
        except Exception as e:
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "",
                    "msg": "播放失败：" + type(e).__name__}

    def _rw(self, text, base):
        out = []
        for line in text.splitlines():
            s = line.strip()
            if not s:
                out.append(line)
                continue
            if s.startswith("#"):
                if "EXT-X-KEY" in s:
                    m = re.search(r'URI="([^"]+)"', s)
                    if m:
                        s = s.replace(m.group(1), self._proxy(urljoin(base, m.group(1))))
                out.append(s)
                continue
            out.append(self._proxy(urljoin(base, s)))
        return "\n".join(out)

    def _fetch_media(self, url):
        ref = self.host + "/static/player/huangguo.html"
        data = self._open(url, referer=ref, ajax=True, binary=True)
        if not data:
            data = self._open(url, referer=self.host + "/", ajax=True, binary=True)
        if not data:
            return b"", ""
        if data[:7] == b"#EXTM3U":
            return data, "m3u8"
        low = data[:512].lower()
        if b"<html" in low or b"<!doctype" in low:
            return data, "html"
        if len(data) <= 64:
            return data, "key"
        return data, "ts"

    def localProxy(self, param):
        try:
            if isinstance(param, str):
                t = param.strip()
                if t.startswith("http"):
                    d = dict(parse_qsl(urlsplit(t).query))
                elif t.startswith("{"):
                    d = json.loads(t)
                else:
                    d = dict(parse_qsl(t))
            elif isinstance(param, dict):
                d = dict(param)
            else:
                d = {}
            url = str(d.get("url", "") or "")
            if not url:
                return [404, "text/plain", b"Not Found", {}]
            parts = urlsplit(url)
            inner = dict(parse_qsl(parts.query, keep_blank_values=True))
            if inner.get("url") and ("127.0.0.1" in parts.netloc or "/proxy" in parts.path):
                url = inner["url"]
            if url.startswith("//"):
                url = "https:" + url
            if url.startswith("/"):
                url = self.host + url
            data, kind = self._fetch_media(url)
            if not data:
                return [404, "text/plain", b"Not Found", {}]
            if kind == "m3u8":
                body = self._rw(data.decode("utf-8", "ignore"), url).encode("utf-8")
                return [200, "application/vnd.apple.mpegurl", body,
                        {"Access-Control-Allow-Origin": "*"}]
            if kind == "key":
                return [200, "application/octet-stream", data,
                        {"Access-Control-Allow-Origin": "*"}]
            if kind == "html":
                return [502, "text/plain", b"upstream html", {}]
            return [200, "video/mp2t", data, {"Access-Control-Allow-Origin": "*"}]
        except Exception:
            pass
        return [404, "text/plain", b"Not Found", {}]

    def proxy(self, param=None):
        return self.localProxy(param)

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return ".m3u8" in u or ".mp4" in u or ".ts" in u or "type=ll" in u

    def liveContent(self, url=""):
        return {"list": []}

    def action(self, action=""):
        return {}

    def destroy(self):
        pass
