"""Robots.txt Checker 单元测试."""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.ecomradar.robots_checker import (
    RobotsChecker,
    parse_robots_txt,
    is_path_allowed,
)


class TestParseRobotsTxt:
    """Robots.txt 解析测试."""

    def test_parses_simple_disallow(self):
        text = """
User-agent: *
Disallow: /private/
Disallow: /admin
Allow: /public
"""
        rules = parse_robots_txt(text)
        assert "/private/" in rules["disallow"]
        assert "/admin" in rules["disallow"]
        assert "/public" in rules["allow"]

    def test_empty_text_returns_empty_rules(self):
        rules = parse_robots_txt("")
        assert rules["disallow"] == []
        assert rules["allow"] == []

    def test_handles_comments(self):
        text = """
# This is a comment
User-agent: *
Disallow: /api
"""
        rules = parse_robots_txt(text)
        assert "/api" in rules["disallow"]


class TestIsPathAllowed:
    """路径允许判断测试."""

    def test_empty_rules_allows_everything(self):
        assert is_path_allowed("/anywhere", {"disallow": [], "allow": []}) is True

    def test_disallow_blocks_matching_path(self):
        rules = {"disallow": ["/admin"], "allow": []}
        assert is_path_allowed("/admin/users", rules) is False
        assert is_path_allowed("/home", rules) is True

    def test_disallow_with_prefix_match(self):
        rules = {"disallow": ["/private/"], "allow": []}
        assert is_path_allowed("/private/secret", rules) is False
        assert is_path_allowed("/private", rules) is True

    def test_allow_overrides_disallow(self):
        rules = {"disallow": ["/private/"], "allow": ["/private/public"]}
        assert is_path_allowed("/private/public/file", rules) is True
        assert is_path_allowed("/private/secret", rules) is False


class TestRobotsChecker:
    """RobotsChecker 异步获取与缓存测试."""

    @pytest.mark.asyncio
    async def test_allowed_url_returns_true(self):
        checker = RobotsChecker(user_agent="EcomRadar", cache_ttl=60)
        robots_txt = "User-agent: *\nDisallow: /private\n"
        with patch.object(checker, "_fetch_robots", new=AsyncMock(return_value=robots_txt)):
            assert await checker.is_allowed("https://a.com/public") is True
            assert await checker.is_allowed("https://a.com/private/page") is False

    @pytest.mark.asyncio
    async def test_uses_cache_on_second_call(self):
        checker = RobotsChecker(user_agent="EcomRadar", cache_ttl=60)
        fetch_mock = AsyncMock(return_value="User-agent: *\nDisallow:\n")
        with patch.object(checker, "_fetch_robots", new=fetch_mock):
            await checker.is_allowed("https://a.com/page1")
            await checker.is_allowed("https://a.com/page2")
            assert fetch_mock.call_count == 1, "robots.txt 应只抓取一次"

    @pytest.mark.asyncio
    async def test_fetch_failure_conservatively_blocks(self):
        """抓取失败时保守拒绝(默认安全)."""
        checker = RobotsChecker(user_agent="EcomRadar", cache_ttl=60)
        with patch.object(checker, "_fetch_robots", new=AsyncMock(side_effect=Exception("timeout"))):
            assert await checker.is_allowed("https://a.com/page") is False

    @pytest.mark.asyncio
    async def test_missing_robots_allows_when_safe(self):
        """服务器返回 404(无 robots.txt)时按惯例允许."""
        checker = RobotsChecker(user_agent="EcomRadar", cache_ttl=60)
        with patch.object(checker, "_fetch_robots", new=AsyncMock(return_value=None)):
            assert await checker.is_allowed("https://a.com/page") is True
