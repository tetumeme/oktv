# -*- coding: utf-8 -*-
"""黄果剧场（huangguo.video）Python 点播源 — 自建维护版。

站点结构（2026-11 实测）：
- 列表：/videos、/videos?category=1|2|3|4；卡片 <article class="video-card group">
  标题 <p class="mt-2.5 font-card-title ...">，封面 <img src=... alt=片名>，
  角标 <span class="... bg-black/55 ...">更新至第N集</span>，
  卡片尾 <p class="mt-2 text-[11px] ... font-mono-meta">连续剧 · 连载中 · N 次下载</p>
- 搜索：/search?q=关键词（/videos?q= 不是真搜索）
- 详情：/video/{code}（data-hls 指向 master.m3u8、data-poster、meta description）
- 系列：/series/{code}（data-episode-list 区域里的 /video/{code} 链接，站点按最新在前）
- 播放：master.m3u8 有 480p/720p 两个 variant（相对路径 + ?n=token），variant 内含
  #EXT-X-KEY:METHOD=AES-128,URI="/api/hls_key/..."，分片在 cdn.huangguo.video 直链
  带 md5/expires 签名。Key 与分片都要站点 Referer，所以统一走本地代理转发。

历史坑：旧版 TITLE_RE 只认 font-display，站点 2026-10 改版后标题类名变成
font-card-title，卡片标题全部为空 -> 列表整页空白。本版两种类名都认，并用封面 alt 兜底。
"""

import json
import re
import ssl
from urllib.parse import parse_qsl, quote, urljoin, urlsplit

try:
    from base.spider import Spider as BaseSpider
except Exception:
    BaseSpider = object

HOSTS = [
    "https://huangguo.video",
    "https://huangguoai.fit",
    "https://huangguoai.com",
]
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
    {"type_id": "latest", "type_name": "最新发布"},
    {"type_id": "1", "type_name": "MV音乐剧"},
    {"type_id": "2", "type_name": "短片"},
    {"type_id": "3", "type_name": "连续剧"},
    {"type_id": "4", "type_name": "片段"},
]

_TAG_SET = [
    ("都市", "1"), ("人妻", "2"), ("同人", "4"), ("校园", "5"),
    ("职场", "6"), ("古风", "7"), ("乱伦", "8"), ("NTR", "9"),
]
_SORT_SET = [("最新发布", "newest"), ("最多播放", "views"), ("最多收藏", "favorites")]

FILTERS = {}
for _cat in CATEGORIES:
    _tid = _cat["type_id"]
    FILTERS[_tid] = [
        {"key": "tags", "name": "情节标签", "value": [{"n": n, "v": v} for n, v in _TAG_SET]},
        {"key": "sort", "name": "排序", "value": [{"n": n, "v": v} for n, v in _SORT_SET]},
    ]
del _cat, _tid

CARD_RE = re.compile(r'<article class="(?:video-card|search-content-card)[\s\S]*?</article>')
TITLE_RE = re.compile(r'<p class="[^"]*(?:font-card-title|font-display)[^"]*"[^>]*>([^<]*)</p>')
ALT_RE = re.compile(r'<img[^>]+alt="([^"]+)"')
PIC_RE = re.compile(r'<img[^>]*src="([^"]*)"')
REMARK_RE = re.compile(r'bg-black/55[^>]*>([^<]*)<')
META_RE = re.compile(r'<p class="mt-2[^"]*font-mono-meta[^"]*"[^>]*>([^<]*)</p>')
HREF_RE = re.compile(r'<a[^>]+href="([^"]*)"')
H1_RE = re.compile(r'<h1[^>]*>([^<]*)</h1>')
DESC_RE = re.compile(r'<meta name="description" content="([^"]*)"')
OGIMG_RE = re.compile(r'<meta property="og:image" content="([^"]*)"')
POSTER_RE = re.compile(r'data-poster="([^"]*)"')
HLS_RE = re.compile(r'data-hls="([^"]*)"')
TOTAL_RE = re.compile(r'(\d+)\s*集')
ANCHOR_RE = re.compile(r'<a[^>]+href="/video/([a-z0-9]+)"[\s\S]*?</a>')

class Spider(BaseSpider):
    def __init__(self):
        try:
            BaseSpider.__init__(self)
        except Exception:
            pass
        self.base = HOSTS[0]
        self._ctx = None
        self._err = ""
        self._mcache = {}

    def getName(self):
        return "黄果剧场"

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
            if site not in HOSTS:
                HOSTS.insert(0, site)
            self.base = site
        self._ctx = None
        self._mcache = {}

    # ---------------- 网络层 ----------------
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

    def _open(self, url, referer=None, binary=False, timeout=12):
        import urllib.request
        hd = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "zh-CN,zh;q=0.9"}
        if referer:
            hd["Referer"] = referer
        ctx = self._ssl_ctx()
        try:
            req = urllib.request.Request(url, headers=hd)
            if ctx is not None:
                resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
            else:
                resp = urllib.request.urlopen(req, timeout=timeout)
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
        try:
            f = getattr(self, "fetch", None)
            if callable(f):
                r = f(url, headers=hd, timeout=timeout)
                if r is not None and getattr(r, "status_code", 0) == 200:
                    self._err = ""
                    if binary:
                        return getattr(r, "content", b"") or b""
                    return getattr(r, "text", "") or ""
        except Exception:
            pass
        return b"" if binary else ""

    def _html(self, path):
        order = [self.base] + [h for h in HOSTS if h != self.base]
        for host in order:
            txt = self._open(host + path, referer=host + "/")
            if txt and len(txt) > 500:
                self.base = host
                return txt
        return ""

    def _abs(self, u):
        u = str(u or "").strip()
        if not u:
            return ""
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.base + u
        return u

    @staticmethod
    def _clean(t):
        t = str(t or "")
        t = re.sub(r"<[^>]+>", "", t)
        t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        t = t.replace("&quot;", '"').replace("&#39;", "'")
        return t.replace("$", "＄").replace("#", "＃").strip()

    @staticmethod
    def _first(rx, text):
        m = rx.search(text or "")
        return m.group(1) if m else ""

    # ---------------- 列表 ----------------
    def homeContent(self, filter=None):
        return {
            "class": list(CATEGORIES),
            "filters": dict(FILTERS),
            "list": self._list("latest", 1, "")["list"],
        }

    def homeVideoContent(self):
        return {"list": self._list("latest", 1, "")["list"]}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        ret = self._list(str(tid), pg, "", extend)
        if not ret.get("list"):
            ret["msg"] = ("加载失败：" + self._err) if self._err else "暂无数据"
        return ret

    def searchContent(self, key, quick=False, pg="1"):
        ret = self._list("latest", 1, str(key or "").strip())
        if not ret.get("list") and self._err:
            ret["msg"] = "搜索失败：" + self._err
        return ret

    def _list(self, tid, pg, keyword="", extend=None):
        extend = extend if isinstance(extend, dict) else {}
        page = int(pg) if str(pg).isdigit() else 1
        if keyword:
            path = "/search?q=" + quote(keyword)
        else:
            path = "/videos"
            if str(tid) not in ("", "latest"):
                path += "?category=" + quote(str(tid))
            if page > 1:
                path += ("&" if "?" in path else "?") + "page=%d" % page
        tags = []
        for k in ("tags", "tags2", "tags3"):
            tv = str(extend.get(k, "") or "").strip()
            if tv:
                tags.append(tv)
        if tags:
            path += ("&" if "?" in path else "?") + "tags=" + quote(",".join(tags))
        sort = str(extend.get("sort", "") or "").strip()
        if sort and sort != "newest":
            path += "&sort=" + quote(sort)
        html = self._html(path)
        cards = []
        for block in CARD_RE.findall(html or ""):
            item = self._card(block)
            if item:
                cards.append(item)
        return {
            "list": cards, "page": page, "pagecount": 1,
            "limit": len(cards), "total": len(cards),
        }

    def _card(self, block):
        m = HREF_RE.search(block)
        if not m:
            return None
        href = m.group(1)
        if "/series/" in href:
            kind = "series"
        elif "/video/" in href:
            kind = "video"
        else:
            return None
        code = href.rstrip("/").split("/")[-1]
        title = self._clean(self._first(TITLE_RE, block))
        if not title:
            title = self._clean(self._first(ALT_RE, block))
        if not title:
            return None
        remark = self._clean(self._first(REMARK_RE, block))
        if not remark:
            remark = self._clean(self._first(META_RE, block))
        return {
            "vod_id": "%s/%s" % (kind, code),
            "vod_name": title,
            "vod_pic": self._abs(self._first(PIC_RE, block)),
            "vod_remarks": remark,
            "vod_type": "连续剧" if kind == "series" else "视频",
            "style": {"type": "rect", "ratio": 0.56},
        }

    # ---------------- 详情 ----------------
    _QUALITIES = [(720, "720P"), (480, "480P")]

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

    def _lines(self, item, eps):
        froms = []
        plays = []
        for q, name in self._QUALITIES:
            froms.append(name)
            plays.append("#".join(["%s$q%d|%s" % (lb, q, tg) for lb, tg in eps]))
        item["vod_play_from"] = "$$$".join(froms)
        item["vod_play_url"] = "$$$".join(plays)

    @staticmethod
    def _sort_eps(eps):
        if not eps:
            return eps

        def num(pair):
            m = re.match(r"第(\d+)", pair[0])
            return int(m.group(1)) if m else 0

        if all(num(p) for p in eps):
            eps.sort(key=num)
        else:
            eps.reverse()
        return eps

    def _detail(self, ident):
        parts = str(ident).split("/")
        kind = parts[0]
        code = parts[1] if len(parts) > 1 else str(ident)
        item = {
            "vod_id": ident, "vod_name": "", "vod_pic": "",
            "vod_play_from": "黄果剧场", "vod_play_url": "",
        }
        if kind == "series":
            html = self._html("/series/%s" % code)
            if not html:
                return None
            item["vod_name"] = self._clean(self._first(H1_RE, html)) or code
            item["vod_pic"] = self._abs(self._first(OGIMG_RE, html) or self._first(POSTER_RE, html))
            desc = self._clean(self._first(DESC_RE, html))
            area = html
            k = html.find("data-episode-list")
            if k >= 0:
                area = html[k:]
            eps = []
            seen = set()
            for m in ANCHOR_RE.finditer(area):
                ec = m.group(1)
                if ec in seen:
                    continue
                seen.add(ec)
                lm = re.search(r"第\s*\d+\s*[集话]|正片|预告", m.group(0))
                if lm:
                    label = self._clean(lm.group(0).replace(" ", ""))
                else:
                    label = "第%d集" % (len(eps) + 1)
                eps.append((label, "/video/" + ec))
            eps = self._sort_eps(eps)
            total = self._first(TOTAL_RE, html)
            lines = []
            if total:
                lines.append("【共】%s 集" % total)
            if desc:
                lines.append(desc)
            item["vod_content"] = "\n".join(lines)
            item["vod_remarks"] = ("全%s集" % total) if total else ("共%d集" % len(eps))
            if eps:
                self._lines(item, eps)
            return item
        html = self._html("/video/%s" % code)
        if not html:
            return None
        item["vod_name"] = self._clean(self._first(H1_RE, html)) or "正片"
        item["vod_pic"] = self._abs(self._first(POSTER_RE, html) or self._first(OGIMG_RE, html))
        item["vod_content"] = self._clean(self._first(DESC_RE, html))
        master = self._abs(self._first(HLS_RE, html))
        if master:
            self._lines(item, [("正片", master)])
        return item

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
        return "%s%stype=hg&url=%s" % (base, sep, up.quote(str(url or ""), safe=""))

    def _pick(self, master, want=0):
        txt = self._open(master, referer=self.base + "/")
        if not txt or "#EXT-X-STREAM-INF" not in txt:
            return master
        lines = txt.splitlines()
        cand = []
        for i, line in enumerate(lines):
            if "#EXT-X-STREAM-INF" not in line:
                continue
            uri = ""
            for j in range(i + 1, len(lines)):
                if lines[j].strip():
                    uri = lines[j].strip()
                    break
            if not uri:
                continue
            rm = re.search(r"RESOLUTION=(\d+)x(\d+)", line)
            h = int(rm.group(2)) if rm else 0
            cand.append((h, urljoin(master, uri)))
        if not cand:
            return master
        if want:
            for h, u in cand:
                if h == want:
                    return u
        cand.sort(key=lambda x: x[0])
        return cand[-1][1]

    def playerContent(self, flag, id, vipFlags=None):
        try:
            cur = str(id or "").split("$$$")[0].split("#")[0]
            sep = cur.rfind("$")
            pid = (cur[sep + 1:] if sep >= 0 else cur).strip()
            want = 0
            m = re.match(r"^q(\d+)\|(.+)$", pid)
            if m:
                want = int(m.group(1))
                pid = m.group(2)
            if "/video/" in pid:
                path = pid if pid.startswith("/") else "/" + pid
                html = self._html(path)
                master = self._abs(self._first(HLS_RE, html or ""))
            else:
                master = self._abs(pid)
            if not master:
                return {
                    "parse": 1, "jx": 0, "playUrl": "", "url": "",
                    "header": {"Referer": self.base + "/"},
                }
            playable = self._pick(master, want)
            return {
                "parse": 0,
                "jx": 0,
                "playUrl": "",
                "url": self._proxy(playable),
                "header": {"Referer": self.base + "/", "User-Agent": UA},
                "format": "application/x-mpegURL",
            }
        except Exception as e:
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "", "msg": "播放失败：" + type(e).__name__}

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
                url = self.base + url
            ref = self.base + "/"
            if "/api/hls_key/" in url:
                data = self._open(url, referer=ref, binary=True)
                if not data:
                    return [404, "text/plain", b"Not Found", {}]
                return [200, "application/octet-stream", data, {"Access-Control-Allow-Origin": "*"}]
            if "m3u8" in url.lower():
                txt = self._open(url, referer=ref)
                if not txt:
                    return [404, "text/plain", b"Not Found", {}]
                body = self._rw(txt, url).encode("utf-8")
                return [200, "application/vnd.apple.mpegurl", body, {"Access-Control-Allow-Origin": "*"}]
            data = self._open(url, referer=ref, binary=True)
            if not data:
                return [404, "text/plain", b"Not Found", {}]
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
        return ".m3u8" in u or ".mp4" in u or ".ts" in u or "type=hg" in u

    def liveContent(self, url=""):
        return {"list": []}

    def action(self, action=""):
        return {}

    def destroy(self):
        self._mcache = {}
