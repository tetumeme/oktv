# -*- coding: utf-8 -*-
# 51吃瓜（51cg1）FongMi 源：域名从 cg51.com 发布页自动解析
import gzip
import html as htmlmod
import json
import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Linux; Android 16; PKM110 Build/BP2A.250605.015) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.179 Mobile Safari/537.36"
PUB = "https://cg51.com/"
SITE = "https://avoid.sbazviql.cc"

CATS = [
    ("mrds", "每日大赛"),
    ("whhj", "网黄合集"),
    ("mrdg", "吃瓜榜单"),
    ("qghj", "瓜友点播"),
    ("rdsj", "热门大瓜"),
    ("bkdg", "必看大瓜"),
    ("ysyl", "成人视频"),
    ("lldd", "伦理道德"),
    ("gcjq", "国产视频"),
    ("thjx", "探花精选"),
    ("xsxy", "学生校园"),
    ("whhl", "网红黑料"),
    ("snsn", "骚男骚女"),
    ("whmx", "明星爆料"),
    ("hwcg", "海外吃瓜"),
    ("rrcg", "人人吃瓜"),
    ("ldcg", "领导干部"),
    ("jpll", "软萌甜妹"),
    ("sjb", "竞技吃瓜"),
    ("qubk", "吃瓜看戏"),
    ("dcbq", "擦边撩骚"),
    ("zzs", "性爱技巧"),
    ("cgxw", "吃瓜新闻"),
    ("51djc", "51原创短剧"),
    ("yczq", "原创博主"),
]


class Spider:
    def __init__(self):
        self.extend = ""
        self.base = SITE
        self.timeout = 15

    # ---------- 网络 ----------
    def _req(self, url, referer=None, binary=False):
        hdr = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,image/*,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": referer or (self.base + "/"),
        }
        req = urllib.request.Request(url, headers=hdr)
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = r.read()
            enc = (r.headers.get("Content-Encoding") or "").lower()
            if enc == "gzip":
                data = gzip.decompress(data)
            code = r.getcode() or 200
            ctype = r.headers.get("Content-Type") or ""
        if binary:
            return code, ctype, data
        return data.decode("utf-8", "ignore")

    def _get(self, url):
        return self._req(url)

    # ---------- 域名 ----------
    def init(self, extend=""):
        self.extend = extend or ""
        self.base = self._resolve()

    def _resolve(self):
        try:
            h = self._req(PUB, referer=PUB)
        except Exception:
            return SITE
        hosts = []
        for m in re.findall(r"https?://([a-z0-9][a-z0-9\-.]*\.(?:sbazviql\.cc|51cg1\.com))", h):
            if m not in hosts:
                hosts.append(m)
        for host in hosts[:6]:
            b = "https://" + host
            try:
                if "post-card" in self._get(b + "/"):
                    return b
            except Exception:
                continue
        return SITE

    # ---------- 解析 ----------
    def _txt(self, s):
        s = re.sub(r"<[^>]+>", "", s or "")
        s = htmlmod.unescape(s)
        return re.sub(r"\s+", " ", s).strip()

    def _cards(self, h):
        out = []
        for seg in re.split(r'<div class="post-card" id="post-card-', h)[1:]:
            m = re.match(r"(\d+)", seg)
            if not m:
                continue
            vid = m.group(1)
            t = re.search(r'<h2 class="post-card-title"[^>]*>(.*?)</h2>', seg, re.S)
            name = self._txt(t.group(1)) if t else vid
            b = re.search(r'x-bg-loader-url="([^"]+)"', seg)
            pic = htmlmod.unescape(b.group(1)) if b else ""
            out.append({"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": ""})
        return out

    # ---------- 入口 ----------
    def homeContent(self, filter=False):
        return {"class": [{"type_id": k, "type_name": v} for k, v in CATS]}

    def homeVideoContent(self):
        return {"list": self._cards(self._get(self.base + "/"))}

    def categoryContent(self, tid, pg, filter, extend):
        p = int(pg) if str(pg).isdigit() else 1
        url = "%s/category/%s/" % (self.base, tid)
        if p > 1:
            url = "%s/category/%s/%d/" % (self.base, tid, p)
        vl = self._cards(self._get(url))
        return {"list": vl, "page": p, "pagecount": 999 if vl else p, "limit": len(vl) or 25, "total": 999}

    def searchContent(self, key, quick=False, pg="1"):
        p = int(pg) if str(pg).isdigit() else 1
        kw = urllib.parse.quote(key)
        url = "%s/search/%s/" % (self.base, kw)
        if p > 1:
            url = "%s/search/%s/%d/" % (self.base, kw, p)
        vl = self._cards(self._get(url))
        return {"list": vl, "page": p, "pagecount": 999 if vl else p, "limit": len(vl) or 25, "total": 999}

    def detailContent(self, ids):
        vid = ids[0]
        h = self._get("%s/archives/%s/" % (self.base, vid))
        name = ""
        m = re.search(r'<meta property="og:title" content="([^"]*)"', h)
        if m:
            name = htmlmod.unescape(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", h, re.S)
            if m:
                name = re.split(r"\s*\|\s*", htmlmod.unescape(m.group(1)))[0]
        name = (name or "").replace("$", " ").replace("#", " ").strip()

        pic = ""
        for pat in (r'<meta property="og:image" content="([^"]*)"', r'x-bg-loader-url="([^"]+)"'):
            m = re.search(pat, h)
            if m:
                pic = htmlmod.unescape(m.group(1))
                break

        desc = ""
        m = re.search(r'<meta name="description" content="([^"]*)"', h)
        if m:
            desc = htmlmod.unescape(m.group(1))

        urls = []
        for c in re.findall(r'data-config="([^"]*)"', h):
            try:
                j = json.loads(htmlmod.unescape(c))
            except Exception:
                continue
            u = (j.get("url") or "").strip()
            if u and u not in urls:
                urls.append(u)
        if not urls:
            return {"list": [], "msg": "没有找到播放地址"}

        play = "#".join(["线路%d$%s" % (i + 1, u) for i, u in enumerate(urls)])
        return {"list": [{
            "vod_id": vid,
            "vod_name": name or vid,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": "51吃瓜",
            "vod_play_url": play,
        }]}

    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "url": self.getProxyUrl({"url": id}),
            "header": {"Referer": self.base + "/", "User-Agent": UA},
        }

    # ---------- 代理 ----------
    def localProxy(self, param):
        url = str(param.get("url") or "")
        if not url:
            return [404, "text/plain", "no url", {}]
        try:
            code, ctype, body = self._req(url, referer=self.base + "/", binary=True)
        except Exception as e:
            return [502, "text/plain", str(e), {}]
        if ".m3u8" in url.split("?")[0].lower():
            text = body.decode("utf-8", "ignore")
            base = url.rsplit("/", 1)[0] + "/"
            out = []
            for line in text.splitlines():
                s = line.strip()
                if s and not s.startswith("#"):
                    out.append(self.getProxyUrl({"url": urllib.parse.urljoin(base, s)}))
                else:
                    out.append(line)
            return [200, "application/vnd.apple.mpegurl", "\n".join(out), {}]
        return [code, ctype or "application/octet-stream", body, {}]

    # 兼容新版命名
    def proxy(self, param):
        return self.localProxy(param)

    def proxyUrl(self, params):
        return self.getProxyUrl(params)
