# -*- coding: utf-8 -*-
import json
import sys
import re
import html as html_parser
from urllib.parse import quote

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        def __init__(self):
            pass

DEFAULT_HOST = "https://www.hanime163.com"
FALLBACK_HOSTS = ["https://www.hanime163.com", "https://hanime163.com", "https://hanime1.best"]


class Spider(BaseSpider):
    def __init__(self):
        try:
            BaseSpider.__init__(self)
        except Exception:
            pass
        self.host = DEFAULT_HOST
        self.headers = {}

    def init(self, extend=""):
        host = ""
        if isinstance(extend, dict):
            host = str(extend.get("host") or extend.get("site") or "")
        elif isinstance(extend, str) and extend.strip():
            t = extend.strip()
            if t.startswith("{"):
                try:
                    host = str(json.loads(t).get("host") or "")
                except Exception:
                    host = ""
            elif t.startswith("http"):
                host = t
        self.host = (host or DEFAULT_HOST).rstrip("/")
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.host + '/',
        }

    def getName(self):
        return "Hanime"

    def homeContent(self, filter):
        classes = [
            {'type_name': '最新上市', 'type_id': 'latest_rank'},
            {'type_name': '裏番', 'type_id': '裏番'},
            {'type_name': '泡麵番', 'type_id': '泡麵番'},
            {'type_name': 'Motion Anime', 'type_id': 'Motion Anime'},
            {'type_name': '3DCG', 'type_id': '3DCG'},
            {'type_name': '2D動畫', 'type_id': '2D動畫'},
            {'type_name': 'AI生成', 'type_id': 'AI生成'},
            {'type_name': 'MMD', 'type_id': 'MMD'},
            {'type_name': 'Cosplay', 'type_id': 'Cosplay'},
            {'type_name': '本日排行', 'type_id': 'daily_rank'},
            {'type_name': '本週排行', 'type_id': 'weekly_rank'},
            {'type_name': '本月排行', 'type_id': 'monthly_rank'}
        ]
        sort_options = [
            {"n": "最新上市", "v": "最新上市"},
            {"n": "最新上傳", "v": "最新上傳"},
            {"n": "本日排行", "v": "本日排行"},
            {"n": "本週排行", "v": "本週排行"},
            {"n": "本月排行", "v": "本月排行"},
            {"n": "觀看次數", "v": "觀看次數"}
        ]
        filters = {}
        for item in classes:
            filters[item['type_id']] = [{"key": "sort", "name": "排序", "value": sort_options}]
        try:
            content = self._get(self.host + "/search?sort=" + quote("最新上市") + "&page=1")
            return {'class': classes, 'filters': filters, 'list': self.parse_vod_list(content)}
        except Exception:
            return {'class': classes, 'filters': filters, 'list': []}

    def _get(self, url):
        for host in [self.host] + [h for h in FALLBACK_HOSTS if h != self.host]:
            u = url.replace(self.host, host)
            try:
                r = self.fetch(u, headers=self.headers, timeout=20)
                text = getattr(r, 'text', '') or ''
                if text and len(text) > 2000:
                    self.host = host
                    return text
            except Exception:
                continue
        return ""

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() else 1
        sort = ""
        if isinstance(extend, dict):
            sort = str(extend.get('sort', '') or '')
        sort = sort or '最新上市'
        if 'rank' in tid or tid == 'latest_rank':
            rank_map = {'latest_rank': '最新上市', 'daily_rank': '本日排行',
                        'weekly_rank': '本週排行', 'monthly_rank': '本月排行'}
            url = "%s/search?sort=%s&page=%d" % (self.host, quote(rank_map.get(tid, '最新上市')), page)
        else:
            url = "%s/search?genre=%s&sort=%s&page=%d" % (self.host, quote(tid), quote(sort), page)
        content = self._get(url)
        vods = self.parse_vod_list(content)
        pc_match = re.search(r'\/ (\d+)', content)
        pagecount = int(pc_match.group(1)) if pc_match else page + 1
        return {'list': vods, 'page': page, 'pagecount': pagecount}

    def parse_vod_list(self, html):
        vods = []
        seen = set()
        p1 = re.compile(r'class="video-item-container".*?href="[^"]*v=(\d+)".*?src="([^"]+)".*?class="duration">(.*?)<.*?class="title">(.*?)<', re.S)
        p2 = re.compile(r'href="[^"]*watch\?v=(\d+)".*?src="([^"]+)".*?class="home-rows-videos-title"[^>]*>(.*?)</div>', re.S)
        for vid, pic, dur, title in p1.findall(html or ""):
            if vid not in seen:
                seen.add(vid)
                vods.append({
                    "vod_id": vid,
                    "vod_name": html_parser.unescape(title).strip(),
                    "vod_pic": pic,
                    "vod_remarks": dur.strip()
                })
        if not vods:
            for vid, pic, title in p2.findall(html or ""):
                if vid not in seen:
                    seen.add(vid)
                    vods.append({
                        "vod_id": vid,
                        "vod_name": html_parser.unescape(title).strip(),
                        "vod_pic": pic,
                        "vod_remarks": ""
                    })
        return vods

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        if not vid:
            return {'list': []}
        html = self._get("%s/watch?v=%s" % (self.host, vid))
        if not html:
            return {'list': []}
        m = re.search(r'<meta property="og:title" content="(.*?)"', html)
        title = html_parser.unescape(m.group(1)) if m else vid
        m = re.search(r'<meta property="og:image" content="(.*?)"', html)
        pic = m.group(1) if m else ""
        sources = re.findall(r'<source[^>]+src="([^"]+)"', html)
        if not sources:
            sources = re.findall(r'https?://[^\s"\'<>]+?\.mp4[^\s"\'<>]*', html)
        play_parts = []
        seen_urls = set()
        for s_url in sources:
            s_url = html_parser.unescape(s_url).replace('&amp;', '&')
            if s_url in seen_urls:
                continue
            seen_urls.add(s_url)
            if '1080' in s_url:
                tag = "1080P"
            elif '720' in s_url:
                tag = "720P"
            else:
                tag = "标清"
            play_parts.append("%s$%s" % (tag, s_url))
        play_parts.sort(key=lambda x: 0 if "1080" in x else (1 if "720" in x else 2))
        content = ""
        m = re.search(r'<meta property="og:description" content="(.*?)"', html)
        if m:
            content = html_parser.unescape(m.group(1)).strip()
        if (not content) or content == title:
            m = re.search(r'<meta name="description" content="(.*?)"', html)
            if m:
                content = html_parser.unescape(m.group(1)).strip()
        if content == title:
            content = ""
        return {'list': [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": content,
            "vod_play_from": "Hanime",
            "vod_play_url": "#".join(play_parts)
        }]}

    def searchContent(self, key, quick, pg="1", extend=None):
        content = self._get("%s/search?query=%s&page=%s" % (self.host, quote(str(key or "")), pg))
        return {'list': self.parse_vod_list(content), 'page': pg}

    def playerContent(self, flag, id, vipFlags):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.host + '/',
            'Connection': 'keep-alive'
        }
        return {'parse': 0, 'url': id, 'header': headers}

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return ".m3u8" in u or ".mp4" in u

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def destroy(self):
        pass
