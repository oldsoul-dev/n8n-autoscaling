# SPDX-License-Identifier: AGPL-3.0-or-later
"""Engine to search a self-hosted Shlink_ instance's short URLs (go-links) by
title, short code, and destination URL.

.. _Shlink: https://shlink.io/

Configuration
=============

Mandatory settings:

- :py:obj:`base_url` - Shlink's API base, e.g. ``https://go.myhomelab.space``
- :py:obj:`api_key` - a Shlink API key (Shlink CLI: ``shlink api-key:generate``)

.. code:: yaml

  - name: shlink
    engine: shlink
    base_url: https://go.myhomelab.space
    api_key: "your-key-here"
    shortcut: go

See https://shlink.io/documentation/api-docs/ - this engine uses
``GET /rest/v3/short-urls?searchTerm=`` (v3 API, ``X-Api-Key`` header auth).
"""

import typing as t
from urllib.parse import urlencode
from dateutil import parser

about = {
    "website": 'https://shlink.io',
    "wikidata_id": None,
    "official_api_documentation": 'https://shlink.io/documentation/api-docs/',
    "use_official_api": True,
    "require_api_key": True,
    "results": 'JSON',
}

categories = ['general']
paging = True

base_url: str = ''
"""URL of the Shlink_ instance's API (same host Traefik routes go.* to)."""

api_key: str = ''
"""Shlink API key."""

page_size: int = 10


def setup(_: dict[str, t.Any]) -> bool | None:
    if not base_url:
        raise ValueError('shlink engine: base_url is unset')
    if not api_key:
        raise ValueError('shlink engine: api_key is unset')


def request(query, params):
    args = {
        'searchTerm': query,
        'itemsPerPage': page_size,
        'page': params['pageno'],
    }
    params['url'] = f"{base_url}/rest/v3/short-urls?{urlencode(args)}"
    params['headers']['X-Api-Key'] = api_key

    return params


def response(resp):
    results = []

    for item in resp.json().get('shortUrls', {}).get('data', []):
        title = item.get('title') or item.get('shortCode')
        tags = item.get('tags', [])
        content = item.get('longUrl', '')
        if tags:
            content = f"{content} [{', '.join(tags)}]"

        created = item.get('dateCreated')

        result = {
            'url': item.get('shortUrl'),
            'title': title,
            'content': content,
        }
        if created:
            try:
                result['publishedDate'] = parser.parse(created)
            except (ValueError, TypeError):
                pass

        results.append(result)

    return results
