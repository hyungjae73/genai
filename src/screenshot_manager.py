"""
Screenshot management module for crawl data enhancement.

Provides ScreenshotManager class for capturing, compressing, and managing
screenshots using Playwright and Pillow.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from PIL import Image
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

# Default base directory for screenshots
DEFAULT_SCREENSHOT_DIR = os.getenv("SCREENSHOT_DIR", "screenshots")


class ScreenshotManager:
    """
    Manages screenshot capture, compression, storage, and cleanup.

    Screenshots are stored in a hierarchical directory structure:
        screenshots/{year}/{month}/{site_id}/{timestamp}_{site_id}.png
    """

    def __init__(self, base_dir: str = DEFAULT_SCREENSHOT_DIR):
        """
        Initialize ScreenshotManager.

        Args:
            base_dir: Base directory for screenshot storage.
        """
        self.base_dir = Path(base_dir)

    def _generate_file_path(self, site_id: int, timestamp: Optional[datetime] = None) -> Path:
        """
        Generate a unique file path for a screenshot.

        Directory structure: {base_dir}/{year}/{month}/{site_id}/{timestamp}_{site_id}.png

        Args:
            site_id: The site identifier.
            timestamp: Optional timestamp; defaults to now.

        Returns:
            Path object for the screenshot file.
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        year = str(timestamp.year)
        month = f"{timestamp.month:02d}"
        ts_str = timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"{ts_str}_{site_id}.png"

        return self.base_dir / year / month / str(site_id) / filename

    async def capture_screenshot(
        self,
        url: str,
        site_id: int,
        timeout: int = 30,
    ) -> Optional[str]:
        """
        Capture a full-page screenshot of the given URL.

        Uses Playwright to render the page and saves a PNG screenshot.
        The entire operation is wrapped in an ``asyncio.wait_for`` with
        *timeout* seconds so it never blocks the crawl pipeline longer
        than the configured limit (Req 19.1, 19.3).

        On failure or timeout, logs a warning and returns None so the
        crawl can continue without a screenshot (Req 19.4).

        Args:
            url: The page URL to capture.
            site_id: The site identifier.
            timeout: Overall timeout in seconds (default 30).

        Returns:
            The file path of the saved screenshot, or None on failure.
        """
        file_path = self._generate_file_path(site_id)
        start_time = asyncio.get_event_loop().time()

        try:
            # Wrap the whole capture in an asyncio timeout (Req 19.3)
            screenshot_path = await asyncio.wait_for(
                self._do_capture(url, site_id, file_path, timeout),
                timeout=timeout,
            )

            elapsed = asyncio.get_event_loop().time() - start_time
            logger.info(
                "Screenshot captured in %.2fs: site_id=%d, path=%s",
                elapsed, site_id, file_path,
            )
            return screenshot_path

        except asyncio.TimeoutError:
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.warning(
                "Screenshot timeout (%.1fs / %ds limit) for site_id=%d, url=%s — continuing without screenshot",
                elapsed, timeout, site_id, url,
            )
            # Clean up partial file if it exists
            if file_path.exists():
                file_path.unlink()
            return None

        except Exception:
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.exception(
                "Screenshot capture failed (%.2fs) for site_id=%d, url=%s",
                elapsed, site_id, url,
            )
            # Clean up partial file if it exists
            if file_path.exists():
                file_path.unlink()
            return None

    async def _do_capture(
        self,
        url: str,
        site_id: int,
        file_path: Path,
        timeout: int,
    ) -> str:
        """Inner coroutine that performs the actual Playwright capture.

        Rendering wait strategy (optimised for SPA / Shopify-style sites):
        1. Navigate with ``domcontentloaded`` (fast initial load)
        2. Wait for ``networkidle`` state separately (tolerates slow assets)
        3. Run an in-page readiness check:
           a. Web fonts loaded
           b. All visible ``<img>`` elements finished loading
           c. Lazy-load images scrolled into view and loaded
           d. DOM mutations settled (no changes for 1 000 ms)
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Per-step timeout: 60 % of overall so asyncio.wait_for can still fire
        step_timeout_ms = max(int(timeout * 1000 * 0.6), 5000)

        from src.pipeline.stealth_browser import StealthBrowserFactory

        async with StealthBrowserFactory() as factory:
            browser = await factory.create_browser()
            try:
                context = await factory.create_context(
                    browser,
                    viewport={"width": 1920, "height": 1080},
                    device_scale_factor=2,
                )
                try:
                    page = await context.new_page()
                    await factory.apply_stealth(page)
                    try:
                        # Step 1: fast initial navigation
                        await page.goto(
                            url,
                            wait_until="domcontentloaded",
                            timeout=step_timeout_ms,
                        )

                        # Step 2: wait for network to settle (SPA data fetches)
                        try:
                            await page.wait_for_load_state(
                                "networkidle", timeout=step_timeout_ms
                            )
                        except Exception:
                            # Some sites never reach networkidle; continue anyway
                            logger.debug(
                                "networkidle not reached within timeout for site_id=%d, continuing",
                                site_id,
                            )

                        # Step 3: in-page readiness — fonts, images, lazy-load, DOM stable
                        await page.evaluate("""() => {
                            return new Promise((resolve) => {
                                /* --- helpers --- */
                                function waitForDomStable(quietMs, maxMs) {
                                    return new Promise((res) => {
                                        let timer = null;
                                        const observer = new MutationObserver(() => {
                                            if (timer) clearTimeout(timer);
                                            timer = setTimeout(() => { observer.disconnect(); res(); }, quietMs);
                                        });
                                        observer.observe(document.body, {
                                            childList: true, subtree: true, attributes: true
                                        });
                                        // Kick-start: if DOM is already quiet, resolve after quietMs
                                        timer = setTimeout(() => { observer.disconnect(); res(); }, maxMs);
                                    });
                                }

                                function scrollAndWaitForLazy() {
                                    return new Promise((res) => {
                                        // Scroll to bottom to trigger lazy-load images
                                        const scrollStep = window.innerHeight;
                                        let scrolled = 0;
                                        const maxScroll = document.body.scrollHeight;
                                        function step() {
                                            scrolled += scrollStep;
                                            window.scrollTo(0, scrolled);
                                            if (scrolled < maxScroll) {
                                                requestAnimationFrame(step);
                                            } else {
                                                // Scroll back to top and give lazy images time to load
                                                window.scrollTo(0, 0);
                                                setTimeout(res, 500);
                                            }
                                        }
                                        step();
                                    });
                                }

                                const promises = [];

                                // 1. Web fonts
                                if (document.fonts && document.fonts.ready) {
                                    promises.push(document.fonts.ready);
                                }

                                // 2. Trigger lazy-load images by scrolling
                                promises.push(scrollAndWaitForLazy());

                                // 3. Wait for DOM mutations to settle (1 s quiet, 5 s max)
                                promises.push(waitForDomStable(1000, 5000));

                                Promise.all(promises).then(() => {
                                    // 4. After DOM is stable, wait for all <img> to finish
                                    const imgs = Array.from(document.querySelectorAll('img'));
                                    const imgPromises = imgs
                                        .filter(img => !img.complete)
                                        .map(img => new Promise((r) => {
                                            img.addEventListener('load', r, {once: true});
                                            img.addEventListener('error', r, {once: true});
                                            // Safety: don't wait forever for a single image
                                            setTimeout(r, 3000);
                                        }));
                                    return Promise.all(imgPromises);
                                }).then(() => resolve());
                            });
                        }""")

                        await page.screenshot(
                            path=str(file_path),
                            full_page=True,
                            type="png",
                            timeout=step_timeout_ms,
                        )
                    finally:
                        await page.close()
                finally:
                    await context.close()
            finally:
                await browser.close()

        # Compress if needed — but keep a high-res copy for OCR
        self._save_ocr_copy(str(file_path))
        self.compress_screenshot(str(file_path))
        return str(file_path)

    def compress_screenshot(self, image_path: str, max_size_mb: float = 5.0) -> None:
        """
        Compress a screenshot if it exceeds the maximum file size.

        Reduces image quality iteratively until the file is within the limit.

        Args:
            image_path: Path to the PNG image file.
            max_size_mb: Maximum allowed file size in megabytes.
        """
        path = Path(image_path)
        if not path.exists():
            return

        max_size_bytes = int(max_size_mb * 1024 * 1024)
        file_size = path.stat().st_size

        if file_size <= max_size_bytes:
            return

        try:
            img = Image.open(path)

            # First attempt: optimize PNG
            img.save(path, format="PNG", optimize=True)
            if path.stat().st_size <= max_size_bytes:
                return

            # Second attempt: reduce resolution progressively
            scale = 0.9
            while path.stat().st_size > max_size_bytes and scale > 0.3:
                new_width = int(img.width * scale)
                new_height = int(img.height * scale)
                resized = img.resize((new_width, new_height), Image.LANCZOS)
                resized.save(path, format="PNG", optimize=True)
                scale -= 0.1

            logger.info(
                "Screenshot compressed: %s (%.2f MB)",
                image_path,
                path.stat().st_size / (1024 * 1024),
            )
        except Exception:
            logger.exception("Failed to compress screenshot: %s", image_path)

    @staticmethod
    def _save_ocr_copy(image_path: str) -> None:
        """
        Save a high-resolution copy of the screenshot for OCR processing.

        The OCR copy is stored alongside the original with an ``_ocr`` suffix
        so that compression of the display copy does not degrade OCR quality.
        """
        path = Path(image_path)
        if not path.exists():
            return
        ocr_path = path.with_name(path.stem + "_ocr" + path.suffix)
        try:
            import shutil
            shutil.copy2(str(path), str(ocr_path))
        except Exception:
            logger.warning("Failed to create OCR copy: %s", ocr_path)

    @staticmethod
    def get_ocr_image_path(screenshot_path: str) -> str:
        """
        Return the path to the high-res OCR copy of a screenshot.

        Falls back to the original path if the OCR copy does not exist.
        """
        p = Path(screenshot_path)
        ocr_path = p.with_name(p.stem + "_ocr" + p.suffix)
        if ocr_path.exists():
            return str(ocr_path)
        return screenshot_path



    def cleanup_old_screenshots(self, retention_days: int = 90) -> int:
        """
        Delete screenshots older than the retention period.

        Args:
            retention_days: Number of days to retain screenshots.

        Returns:
            Number of files deleted.
        """
        if not self.base_dir.exists():
            return 0

        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        deleted_count = 0

        for png_file in self.base_dir.rglob("*.png"):
            try:
                mtime = datetime.utcfromtimestamp(png_file.stat().st_mtime)
                if mtime < cutoff:
                    png_file.unlink()
                    deleted_count += 1
                    logger.debug("Deleted old screenshot: %s", png_file)
            except Exception:
                logger.exception("Failed to delete screenshot: %s", png_file)

        # Remove empty directories
        self._remove_empty_dirs()

        logger.info(
            "Cleanup complete: deleted %d screenshots older than %d days",
            deleted_count, retention_days,
        )
        return deleted_count

    def get_storage_usage(self) -> dict:
        """
        Get storage usage statistics for the screenshot directory.

        Returns:
            Dictionary with total_files, total_size_bytes, total_size_mb keys.
        """
        if not self.base_dir.exists():
            return {
                "total_files": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0.0,
            }

        total_files = 0
        total_size = 0

        for png_file in self.base_dir.rglob("*.png"):
            total_files += 1
            total_size += png_file.stat().st_size

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }

    def _remove_empty_dirs(self) -> None:
        """Remove empty directories under the base directory."""
        if not self.base_dir.exists():
            return

        # Walk bottom-up to remove empty leaf directories first
        for dirpath in sorted(self.base_dir.rglob("*"), reverse=True):
            if dirpath.is_dir() and not any(dirpath.iterdir()):
                try:
                    dirpath.rmdir()
                except OSError as e:
                    logger.debug("Failed to remove empty directory %s: %s", dirpath, e)
