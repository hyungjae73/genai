"""
Unit tests for ScreenshotManager (Task 3.4).

Covers:
- Screenshot capture success case
- Timeout error handling
- Filename generation logic
- Compression functionality
"""

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.screenshot_manager import ScreenshotManager


# ------------------------------------------------------------------
# Filename generation
# ------------------------------------------------------------------


class TestGenerateFilePath:
    """Tests for _generate_file_path — directory structure and naming."""

    def test_generates_correct_directory_structure(self, tmp_path):
        mgr = ScreenshotManager(base_dir=str(tmp_path))
        ts = datetime(2024, 3, 15, 10, 30, 45)
        path = mgr._generate_file_path(site_id=42, timestamp=ts)

        assert path == tmp_path / "2024" / "03" / "42" / "20240315_103045_42.png"

    def test_pads_month_with_zero(self, tmp_path):
        mgr = ScreenshotManager(base_dir=str(tmp_path))
        ts = datetime(2024, 1, 5, 0, 0, 0)
        path = mgr._generate_file_path(site_id=1, timestamp=ts)

        assert "01" in path.parts  # month zero-padded

    def test_uses_utcnow_when_no_timestamp(self, tmp_path):
        mgr = ScreenshotManager(base_dir=str(tmp_path))
        before = datetime.utcnow()
        path = mgr._generate_file_path(site_id=7)
        after = datetime.utcnow()

        # The year directory should match current year
        assert str(before.year) in str(path) or str(after.year) in str(path)
        assert path.suffix == ".png"

    def test_filename_contains_site_id_and_timestamp(self, tmp_path):
        mgr = ScreenshotManager(base_dir=str(tmp_path))
        ts = datetime(2025, 12, 31, 23, 59, 59)
        path = mgr._generate_file_path(site_id=999, timestamp=ts)

        assert path.name == "20251231_235959_999.png"


# ------------------------------------------------------------------
# Compression
# ------------------------------------------------------------------


class TestCompressScreenshot:
    """Tests for compress_screenshot — size reduction logic."""

    def test_no_compression_when_under_limit(self, tmp_path):
        """File under max_size_mb should not be modified."""
        mgr = ScreenshotManager(base_dir=str(tmp_path))
        img_path = tmp_path / "small.png"

        # Create a small valid PNG via Pillow
        from PIL import Image
        img = Image.new("RGB", (10, 10), color="red")
        img.save(str(img_path), format="PNG")

        original_size = img_path.stat().st_size
        mgr.compress_screenshot(str(img_path), max_size_mb=5.0)

        # Size should remain the same (no compression needed)
        assert img_path.stat().st_size == original_size

    def test_compression_reduces_large_image(self, tmp_path):
        """An image exceeding max_size should be reduced."""
        mgr = ScreenshotManager(base_dir=str(tmp_path))
        img_path = tmp_path / "large.png"

        # Create a large image with random-ish data that compresses poorly
        from PIL import Image
        import random
        random.seed(42)
        img = Image.new("RGB", (2000, 2000))
        pixels = img.load()
        for x in range(2000):
            for y in range(2000):
                pixels[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        img.save(str(img_path), format="PNG")

        original_size = img_path.stat().st_size
        # Set a very small limit to force compression
        mgr.compress_screenshot(str(img_path), max_size_mb=0.5)

        assert img_path.stat().st_size < original_size

    def test_compression_nonexistent_file(self, tmp_path):
        """Should silently return when file doesn't exist."""
        mgr = ScreenshotManager(base_dir=str(tmp_path))
        # Should not raise
        mgr.compress_screenshot(str(tmp_path / "nonexistent.png"))


# ------------------------------------------------------------------
# Screenshot capture — success
# ------------------------------------------------------------------


class TestCaptureScreenshotSuccess:
    """Tests for capture_screenshot — happy path."""

    @pytest.mark.asyncio
    async def test_returns_file_path_on_success(self, tmp_path):
        mgr = ScreenshotManager(base_dir=str(tmp_path))

        # Mock _do_capture to simulate a successful capture
        expected_path = str(tmp_path / "2024" / "01" / "5" / "20240101_000000_5.png")

        async def fake_do_capture(url, site_id, file_path, timeout):
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.touch()
            return str(file_path)

        with patch.object(mgr, "_do_capture", side_effect=fake_do_capture):
            result = await mgr.capture_screenshot("https://example.com", site_id=5, timeout=10)

        assert result is not None
        assert "5.png" in result

    @pytest.mark.asyncio
    async def test_creates_directory_structure(self, tmp_path):
        mgr = ScreenshotManager(base_dir=str(tmp_path))

        async def fake_do_capture(url, site_id, file_path, timeout):
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.touch()
            return str(file_path)

        with patch.object(mgr, "_do_capture", side_effect=fake_do_capture):
            result = await mgr.capture_screenshot("https://example.com", site_id=10)

        assert result is not None
        result_path = Path(result)
        assert result_path.exists()


# ------------------------------------------------------------------
# Screenshot capture — timeout / error
# ------------------------------------------------------------------


class TestCaptureScreenshotErrors:
    """Tests for capture_screenshot — timeout and failure cases."""

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout(self, tmp_path):
        mgr = ScreenshotManager(base_dir=str(tmp_path))

        async def slow_capture(url, site_id, file_path, timeout):
            await asyncio.sleep(100)  # Will be cancelled by wait_for
            return str(file_path)

        with patch.object(mgr, "_do_capture", side_effect=slow_capture):
            result = await mgr.capture_screenshot(
                "https://example.com", site_id=1, timeout=1
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self, tmp_path):
        mgr = ScreenshotManager(base_dir=str(tmp_path))

        async def failing_capture(url, site_id, file_path, timeout):
            raise RuntimeError("Browser crashed")

        with patch.object(mgr, "_do_capture", side_effect=failing_capture):
            result = await mgr.capture_screenshot(
                "https://example.com", site_id=2, timeout=10
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_cleans_up_partial_file_on_timeout(self, tmp_path):
        mgr = ScreenshotManager(base_dir=str(tmp_path))

        async def slow_capture_with_file(url, site_id, file_path, timeout):
            # Simulate partial file creation before timeout
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.touch()
            await asyncio.sleep(100)
            return str(file_path)

        with patch.object(mgr, "_do_capture", side_effect=slow_capture_with_file):
            result = await mgr.capture_screenshot(
                "https://example.com", site_id=3, timeout=1
            )

        assert result is None
        # Partial file should be cleaned up
        generated_files = list(tmp_path.rglob("*.png"))
        assert len(generated_files) == 0

    @pytest.mark.asyncio
    async def test_cleans_up_partial_file_on_exception(self, tmp_path):
        mgr = ScreenshotManager(base_dir=str(tmp_path))

        async def failing_capture_with_file(url, site_id, file_path, timeout):
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.touch()
            raise RuntimeError("Rendering failed")

        with patch.object(mgr, "_do_capture", side_effect=failing_capture_with_file):
            result = await mgr.capture_screenshot(
                "https://example.com", site_id=4, timeout=10
            )

        assert result is None
        generated_files = list(tmp_path.rglob("*.png"))
        assert len(generated_files) == 0


# ------------------------------------------------------------------
# Cleanup and storage usage
# ------------------------------------------------------------------


class TestCleanupAndStorage:
    """Tests for cleanup_old_screenshots and get_storage_usage."""

    def test_cleanup_deletes_old_files(self, tmp_path):
        mgr = ScreenshotManager(base_dir=str(tmp_path))

        # Create an "old" file
        old_dir = tmp_path / "2023" / "01" / "1"
        old_dir.mkdir(parents=True)
        old_file = old_dir / "old_screenshot.png"
        old_file.touch()
        # Set mtime to 100 days ago
        old_time = (datetime.utcnow() - timedelta(days=100)).timestamp()
        os.utime(str(old_file), (old_time, old_time))

        # Create a "recent" file
        new_dir = tmp_path / "2025" / "01" / "1"
        new_dir.mkdir(parents=True)
        new_file = new_dir / "new_screenshot.png"
        new_file.touch()

        deleted = mgr.cleanup_old_screenshots(retention_days=90)

        assert deleted == 1
        assert not old_file.exists()
        assert new_file.exists()

    def test_cleanup_returns_zero_when_no_old_files(self, tmp_path):
        mgr = ScreenshotManager(base_dir=str(tmp_path))

        new_dir = tmp_path / "2025" / "06" / "1"
        new_dir.mkdir(parents=True)
        (new_dir / "recent.png").touch()

        deleted = mgr.cleanup_old_screenshots(retention_days=90)
        assert deleted == 0

    def test_cleanup_handles_nonexistent_base_dir(self, tmp_path):
        mgr = ScreenshotManager(base_dir=str(tmp_path / "nonexistent"))
        deleted = mgr.cleanup_old_screenshots()
        assert deleted == 0

    def test_get_storage_usage(self, tmp_path):
        mgr = ScreenshotManager(base_dir=str(tmp_path))

        # Create some files
        d = tmp_path / "2024" / "01" / "1"
        d.mkdir(parents=True)
        for i in range(3):
            f = d / f"screenshot_{i}.png"
            f.write_bytes(b"\x00" * 1024)  # 1KB each

        usage = mgr.get_storage_usage()
        assert usage["total_files"] == 3
        assert usage["total_size_bytes"] == 3072

    def test_get_storage_usage_empty(self, tmp_path):
        mgr = ScreenshotManager(base_dir=str(tmp_path / "empty"))
        usage = mgr.get_storage_usage()
        assert usage["total_files"] == 0
        assert usage["total_size_bytes"] == 0
