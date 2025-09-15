"""
Mock browser session for cloud deployment without Playwright dependencies
"""
from contextlib import contextmanager
from typing import Optional, List
import time

class MockPage:
    """Mock page object that simulates browser operations"""
    
    def __init__(self):
        self.url = None
        
    def goto(self, url: str):
        self.url = url
        print(f"Mock: Navigating to {url}")
        
    def wait_for_selector(self, selector: str, timeout: int = 30000):
        print(f"Mock: Waiting for selector {selector}")
        time.sleep(0.1)  # Simulate wait
        
    def screenshot(self, **kwargs):
        # Return a minimal mock screenshot
        return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
        
    def wait_for_timeout(self, timeout: int):
        time.sleep(timeout / 1000.0)
        
    def frame_locator(self, selector: str):
        return MockFrame()
        
    def locator(self, selector: str):
        return MockLocator()

class MockFrame:
    """Mock frame object"""
    
    def wait_for_selector(self, selector: str, timeout: int = 30000):
        print(f"Mock Frame: Waiting for selector {selector}")
        
    def click(self, selector: str):
        print(f"Mock Frame: Clicking {selector}")
        
    def fill(self, selector: str, value: str):
        print(f"Mock Frame: Filling {selector} with {value}")
        
    def locator(self, selector: str):
        return MockLocator()

class MockLocator:
    """Mock locator object"""
    
    def click(self):
        print("Mock Locator: Click")
        
    def fill(self, value: str):
        print(f"Mock Locator: Fill with {value}")
        
    def is_visible(self):
        return True

class MockBrowserSession:
    """
    Mock browser session for cloud deployment without browser dependencies
    """

    def __init__(self, headless: bool = True, permissions: Optional[List[str]] = None):
        self.headless = headless
        self.permissions = permissions or []
        self.page = MockPage()

    def __enter__(self):
        print("Mock: Starting browser session")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Mock: Closing browser session")
        pass
