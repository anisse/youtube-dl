# encoding: utf-8
from __future__ import unicode_literals

from .common import InfoExtractor
from .cbs import CBSIE
from ..utils import (
    parse_duration,
)


class CBSNewsIE(CBSIE):
    IE_DESC = 'CBS News'
    _VALID_URL = r'https?://(?:www\.)?cbsnews\.com/(?:news|videos)/(?P<id>[\da-z_-]+)'

    _TESTS = [
        {
            'url': 'http://www.cbsnews.com/news/tesla-and-spacex-elon-musks-industrial-empire/',
            'info_dict': {
                'id': 'tesla-and-spacex-elon-musks-industrial-empire',
                'ext': 'flv',
                'title': 'Tesla and SpaceX: Elon Musk\'s industrial empire',
                'thumbnail': 'http://beta.img.cbsnews.com/i/2014/03/30/60147937-2f53-4565-ad64-1bdd6eb64679/60-0330-pelley-640x360.jpg',
                'duration': 791,
            },
            'params': {
                # rtmp download
                'skip_download': True,
            },
            'skip': 'Subscribers only',
        },
        {
            'url': 'http://www.cbsnews.com/videos/fort-hood-shooting-army-downplays-mental-illness-as-cause-of-attack/',
            'info_dict': {
                'id': 'SNJBOYzXiWBOvaLsdzwH8fmtP1SCd91Y',
                'ext': 'mp4',
                'title': 'Fort Hood shooting: Army downplays mental illness as cause of attack',
                'description': 'md5:4a6983e480542d8b333a947bfc64ddc7',
                'upload_date': '20140404',
                'timestamp': 1396650660,
                'uploader': 'CBSI-NEW',
                'thumbnail': 're:^https?://.*\.jpg$',
                'duration': 205,
                'subtitles': {
                    'en': [{
                        'ext': 'ttml',
                    }],
                },
            },
            'params': {
                # m3u8 download
                'skip_download': True,
            },
        },
    ]

    def _real_extract(self, url):
        video_id = self._match_id(url)

        webpage = self._download_webpage(url, video_id)

        video_info = self._parse_json(self._html_search_regex(
            r'(?:<ul class="media-list items" id="media-related-items"><li data-video-info|<div id="cbsNewsVideoPlayer" data-video-player-options)=\'({.+?})\'',
            webpage, 'video JSON info'), video_id)

        item = video_info['item'] if 'item' in video_info else video_info
        guid = item['mpxRefId']
        return self._extract_video_info(guid)


class CBSNewsLiveVideoIE(InfoExtractor):
    IE_DESC = 'CBS News Live Videos'
    _VALID_URL = r'https?://(?:www\.)?cbsnews\.com/live/video/(?P<id>[\da-z_-]+)'

    # Live videos get deleted soon. See http://www.cbsnews.com/live/ for the latest examples
    _TEST = {
        'url': 'http://www.cbsnews.com/live/video/clinton-sanders-prepare-to-face-off-in-nh/',
        'info_dict': {
            'id': 'clinton-sanders-prepare-to-face-off-in-nh',
            'ext': 'flv',
            'title': 'Clinton, Sanders Prepare To Face Off In NH',
            'duration': 334,
        },
        'skip': 'Video gone',
    }

    def _real_extract(self, url):
        video_id = self._match_id(url)

        webpage = self._download_webpage(url, video_id)

        video_info = self._parse_json(self._html_search_regex(
            r'data-story-obj=\'({.+?})\'', webpage, 'video JSON info'), video_id)['story']

        hdcore_sign = 'hdcore=3.3.1'
        f4m_formats = self._extract_f4m_formats(video_info['url'] + '&' + hdcore_sign, video_id)
        if f4m_formats:
            for entry in f4m_formats:
                # URLs without the extra param induce an 404 error
                entry.update({'extra_param_to_segment_url': hdcore_sign})
        self._sort_formats(f4m_formats)

        return {
            'id': video_id,
            'title': video_info['headline'],
            'thumbnail': video_info.get('thumbnail_url_hd') or video_info.get('thumbnail_url_sd'),
            'duration': parse_duration(video_info.get('segmentDur')),
            'formats': f4m_formats,
        }
