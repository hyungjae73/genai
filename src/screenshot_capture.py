"""
Screenshot capture utility using Playwright.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, Page


class ScreenshotCapture:
    """
    Utility class for capturing screenshots of web pages.
    """
    
    def __init__(self, screenshot_dir: str = "screenshots"):
        """
        Initialize screenshot capture utility.
        
        Args:
            screenshot_dir: Directory to save screenshots
        """
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(exist_ok=True)
        self.browser: Optional[Browser] = None
    
    async def __aenter__(self):
        """Context manager entry."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def capture_screenshot(
        self,
        url: str,
        site_id: int,
        screenshot_type: str,
        file_format: str = "png",
        full_page: bool = True,
        wait_time: int = 2000
    ) -> Path:
        """
        Capture a screenshot of a web page.
        
        Args:
            url: URL to capture
            site_id: Site ID
            screenshot_type: Type of screenshot ('baseline' or 'violation')
            file_format: File format ('png' or 'pdf')
            full_page: Whether to capture full page
            wait_time: Time to wait after page load (milliseconds)
        
        Returns:
            Path to saved screenshot file
        """
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use context manager.")
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = "png" if file_format == "png" else "pdf"
        filename = f"site_{site_id}_{screenshot_type}_{timestamp}.{ext}"
        file_path = self.screenshot_dir / filename
        
        # Create new page
        page: Page = await self.browser.new_page()
        
        try:
            # Navigate to URL
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Wait for additional time to ensure page is fully loaded
            await asyncio.sleep(wait_time / 1000)
            
            # Capture screenshot
            if file_format == "png":
                await page.screenshot(
                    path=str(file_path),
                    full_page=full_page
                )
            else:  # PDF
                await page.pdf(
                    path=str(file_path),
                    format="A4",
                    print_background=True
                )
            
            return file_path
        
        finally:
            await page.close()
    
    async def capture_multiple_screenshots(
        self,
        urls: list[tuple[str, int, str]],
        file_format: str = "png"
    ) -> list[Path]:
        """
        Capture multiple screenshots.
        
        Args:
            urls: List of tuples (url, site_id, screenshot_type)
            file_format: File format ('png' or 'pdf')
        
        Returns:
            List of paths to saved screenshot files
        """
        results = []
        for url, site_id, screenshot_type in urls:
            try:
                file_path = await self.capture_screenshot(
                    url, site_id, screenshot_type, file_format
                )
                results.append(file_path)
            except Exception as e:
                print(f"Error capturing screenshot for {url}: {e}")
                results.append(None)
        
        return results


async def capture_site_screenshot(
    url: str,
    site_id: int,
    screenshot_type: str = "baseline",
    file_format: str = "png"
) -> Path:
    """
    Convenience function to capture a single screenshot.
    
    Args:
        url: URL to capture
        site_id: Site ID
        screenshot_type: Type of screenshot ('baseline' or 'violation')
        file_format: File format ('png' or 'pdf')
    
    Returns:
        Path to saved screenshot file
    """
    async with ScreenshotCapture() as capture:
        return await capture.capture_screenshot(
            url, site_id, screenshot_type, file_format
        )
