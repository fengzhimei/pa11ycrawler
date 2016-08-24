import pytest
import json
from datetime import datetime
import scrapy
from scrapy.http.response.text import TextResponse
import textwrap
from freezegun import freeze_time
from urlobject import URLObject
from pa11ycrawler.spiders.edx import EdxSpider


def urls_are_equal(url1, url2):
    """
    Compare to URLs for equality, ignoring the ordering of non-ordered elements.
    """
    url1 = URLObject(url1)
    url2 = URLObject(url2)
    return (
        url1.without_query() == url2.without_query() and
        url1.query_multi_dict == url2.query_multi_dict
    )


def test_start_with_login():
    spider = EdxSpider(email="staff@example.com", password="edx")
    requests = list(spider.start_requests())

    assert len(requests) == 1
    request = requests[0]
    assert isinstance(request, scrapy.Request)
    expected_url = 'http://localhost:8000/user_api/v1/account/login_session/'
    assert urls_are_equal(request.url, expected_url)
    expected_body = b'email=staff%40example.com&password=edx'
    assert request.body == expected_body
    assert request.method == "POST"
    assert request.headers == {
        b'Content-Type': [b'application/x-www-form-urlencoded'],
    }
    assert request.callback


def test_start_with_auto_auth():
    spider = EdxSpider(email=None, password=None)
    requests = list(spider.start_requests())
    assert len(requests) == 1
    request = requests[0]
    assert isinstance(request, scrapy.Request)
    expected_url = 'http://localhost:8000/auto_auth?course_id=course-v1%3AedX%2BTest101%2Bcourse&staff=true'
    assert urls_are_equal(request.url, expected_url)
    assert request.method == "GET"
    assert request.headers == {
        b"Accept": [b"application/json"]
    }
    assert request.callback


def test_auto_auth_response(mocker):
    spider = EdxSpider(email=None, password=None)
    fake_result = {
        "email": "sparky@gooddog.woof",
        "password": "b4rkb4rkwo0f",
    }
    fake_response = TextResponse(
        url="http://localhost:8000/auto_auth",
        body=json.dumps(fake_result).encode('utf8'),
        encoding="utf-8",
    )

    assert spider.login_email == None
    assert spider.login_password == None
    requests = list(spider.after_auto_auth(fake_response))
    assert spider.login_email == "sparky@gooddog.woof"
    assert spider.login_password == "b4rkb4rkwo0f"

    assert len(requests) == 1
    request = requests[0]
    assert isinstance(request, scrapy.Request)
    expected_url = 'http://localhost:8000/api/courses/v1/blocks?course_id=course-v1%3AedX%2BTest101%2Bcourse&depth=all&all_blocks=true'
    assert urls_are_equal(request.url, expected_url)
    assert request.method == "GET"
    assert request.headers == {}
    assert not request.callback


@freeze_time("2016-01-01")
def test_log_back_in(mocker):
    login_html = textwrap.dedent("""
    <html>
      <head>
        <title>Sign in or Register</title>
      </head>
      <body>
        <h1>Sign In</h1>
        <form id="login">
          <input name="email">
          <input name="password">
          <input type="checkbox" name="remember">
        </form>
        <button>Create an account</button>
      </body>
    </html>
    """)
    fake_request = scrapy.Request(
        url="http://localhost:8000/foo/bar"
    )
    fake_response = TextResponse(
        url="http://localhost:8000/login?next=/foo/bar",
        request=fake_request,
        body=login_html.encode("utf-8"),
        encoding="utf-8",
    )
    spider = EdxSpider(email="abc@def.com", password="xyz")

    requests = list(spider.parse_item(fake_response))

    assert len(requests) == 2
    request = requests[0]
    item = requests[1]
    expected_url = 'http://localhost:8000/user_api/v1/account/login_session/?next=%2Ffoo%2Fbar'
    assert urls_are_equal(request.url, expected_url)
    expected_body = b'email=abc%40def.com&password=xyz'
    assert request.body == expected_body
    assert item == {
        'accessed_at': datetime(2016, 1, 1),
        'page_title': 'Sign in or Register',
        'request_headers': {},
        'url': 'http://localhost:8000/login?next=/foo/bar',
    }

