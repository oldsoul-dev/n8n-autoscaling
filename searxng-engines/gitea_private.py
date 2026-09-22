# SPDX-License-Identifier: AGPL-3.0-or-later
"""Gitea engine, forked from SearXNG's built-in `gitea.py`, with one addition:
an Authorization header carrying a Personal Access Token, so repos private to
that token's owner are included in results (not just public ones - the stock
engine sends no credential at all, so private repos never show up there).

Configuration
=============

Same as the built-in gitea engine, plus one mandatory setting:

- :py:obj:`api_key` - a Gitea Personal Access Token, scope `read:repository`
  (add `read:user` too if repos reachable only via org/team membership should
  also be searchable).

.. code:: yaml

  - name: gitea (private)
    engine: gitea_private
    base_url: https://internal-gitea-host:3000
    api_key: "your-token-here"
    shortcut: gitp

Gitea's `/api/v1/repos/search` includes both public and private repos
reachable by the authenticated token's owner by default (no `private=`
filter needed) - see https://docs.gitea.com/next/development/api-usage.
"""

import typing as t
from urllib.parse import urlencode
from dateutil import parser

about = {
    "website": 'https://about.gitea.com',
    "wikidata_id": None,
    "official_api_documentation": 'https://docs.gitea.com/next/development/api-usage',
    "use_official_api": True,
    "require_api_key": True,
    "results": 'JSON',
}

categories = ['it', 'repos']
paging = True

base_url: str = ''
"""URL of the Gitea_ instance."""

api_key: str = ''
"""Gitea Personal Access Token, scope `read:repository` (private repos)."""

sort: str = "updated"
order = "desc"
page_size: int = 10


def setup(_: dict[str, t.Any]) -> bool | None:
    if not base_url:
        raise ValueError('gitea_private engine: base_url is unset')
    if not api_key:
        raise ValueError('gitea_private engine: api_key is unset')


def request(query, params):
    args = {'q': query, 'limit': page_size, 'sort': sort, 'order': order, 'page': params['pageno']}
    params['url'] = f"{base_url}/api/v1/repos/search?{urlencode(args)}"
    params['headers']['Authorization'] = f"token {api_key}"

    return params


def response(resp):
    results = []

    for item in resp.json().get('data', []):
        content = [item.get(i) for i in ['language', 'description'] if item.get(i)]

        results.append(
            {
                'template': 'packages.html',
                'url': item.get('html_url'),
                'title': item.get('full_name') + (' [private]' if item.get('private') else ''),
                'content': ' / '.join(content),
                'thumbnail': item.get('avatar_url') or item.get('owner', {}).get('avatar_url'),
                'package_name': item.get('name'),
                'maintainer': item.get('owner', {}).get('username'),
                'publishedDate': parser.parse(item.get("updated_at") or item.get("created_at")),
                'tags': item.get('topics', []),
                'popularity': item.get('stars_count'),
                'homepage': item.get('website'),
                'source_code_url': item.get('clone_url'),
            }
        )

    return results
