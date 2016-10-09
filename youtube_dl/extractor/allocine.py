# coding: utf-8
from __future__ import unicode_literals

from .common import InfoExtractor
from ..utils import (
    qualities,
    url_basename,
)


class AllocineIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?allocine\.fr/(?:article|video|film)/(?:fichearticle_gen_carticle=|player_gen_cmedia=|fichefilm_gen_cfilm=|video-)(?P<id>[0-9]+)(?:\.html)?'

    _TESTS = [{
        'url': 'http://www.allocine.fr/article/fichearticle_gen_carticle=18635087.html',
        'md5': '0c9fcf59a841f65635fa300ac43d8269',
        'info_dict': {
            'id': '19546517',
            'display_id': '18635087',
            'ext': 'mp4',
            'title': 'Astérix - Le Domaine des Dieux Teaser VF',
            'description': 'md5:4a754271d9c6f16c72629a8a993ee884',
            'thumbnail': 're:http://.*\.jpg',
        },
    }, {
        'url': 'http://www.allocine.fr/video/player_gen_cmedia=19540403&cfilm=222257.html',
        'md5': 'd0cdce5d2b9522ce279fdfec07ff16e0',
        'info_dict': {
            'id': '19540403',
            'display_id': '19540403',
            'ext': 'mp4',
            'title': 'Planes 2 Bande-annonce VF',
            'description': 'Regardez la bande annonce du film Planes 2 (Planes 2 Bande-annonce VF). Planes 2, un film de Roberts Gannaway',
            'thumbnail': 're:http://.*\.jpg',
        },
    }, {
        'url': 'http://www.allocine.fr/video/player_gen_cmedia=19544709&cfilm=181290.html',
        'md5': '101250fb127ef9ca3d73186ff22a47ce',
        'info_dict': {
            'id': '19544709',
            'display_id': '19544709',
            'ext': 'mp4',
            'title': 'Dragons 2 - Bande annonce finale VF',
            'description': 'md5:6cdd2d7c2687d4c6aafe80a35e17267a',
            'thumbnail': 're:http://.*\.jpg',
        },
    }, {
        'url': 'http://www.allocine.fr/video/video-19550147/',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        display_id = self._match_id(url)

        webpage = self._download_webpage(url, display_id)

        model = self._html_search_regex(
            r'data-model="([^"]+)"', webpage, 'data model')
        model_data = self._parse_json(model, display_id)

        quality = qualities(['ld', 'md', 'hd'])

        formats = []
        for video_url in model_data['sources'].values():
            video_id, format_id = url_basename(video_url).split('_')[:2]
            formats.append({
                'format_id': format_id,
                'quality': quality(format_id),
                'url': video_url,
            })
        self._sort_formats(formats)

        return {
            'id': video_id,
            'display_id': display_id,
            'title': model_data['title'],
            'thumbnail': self._og_search_thumbnail(webpage),
            'formats': formats,
            'description': self._og_search_description(webpage),
        }
