import httpx
from typing import Optional, List, Dict, Any
from app.config import settings
from playwright.async_api import async_playwright, Browser, Page


class WebScraperService:
    def __init__(self):
        self.tavily_api_key = settings.tavily_api_key
        self.serper_api_key = settings.serper_api_key
        self.browser: Optional[Browser] = None
    
    async def search_web(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search the web using Tavily API (preferred) or Serper API (fallback).
        """
        # Try Tavily first
        if self.tavily_api_key:
            try:
                return await self._search_with_tavily(query, max_results)
            except Exception as e:
                print(f"Tavily search failed: {e}")
        
        # Fallback to Serper
        if self.serper_api_key:
            try:
                return await self._search_with_serper(query, max_results)
            except Exception as e:
                print(f"Serper search failed: {e}")
        
        # If both fail, return empty
        return []
    
    async def _search_with_tavily(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search using Tavily API."""
        try:
            from tavily import TavilyClient
            
            client = TavilyClient(api_key=self.tavily_api_key)
            response = client.search(query=query, max_results=max_results)
            
            results = []
            for result in response.get("results", []):
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                    "score": result.get("score", 0)
                })
            
            return results
        except ImportError:
            # Fallback to direct API call
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.tavily_api_key,
                        "query": query,
                        "max_results": max_results
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                
                results = []
                for result in data.get("results", []):
                    results.append({
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "content": result.get("content", ""),
                        "score": result.get("score", 0)
                    })
                
                return results
    
    async def _search_with_serper(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search using Serper API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": self.serper_api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "q": query,
                    "num": max_results
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for result in data.get("organic", []):
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("link", ""),
                    "content": result.get("snippet", ""),
                    "score": 0
                })
            
            return results
    
    async def scrape_url(self, url: str) -> Optional[str]:
        """
        Scrape content from a specific URL using Playwright.
        """
        try:
            if not self.browser:
                playwright = await async_playwright().start()
                self.browser = await playwright.chromium.launch(headless=True)
            
            page: Page = await self.browser.new_page()
            
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                
                # Extract main content
                content = await page.evaluate("""
                    () => {
                        // Remove script and style elements
                        const scripts = document.querySelectorAll('script, style, nav, header, footer, aside');
                        scripts.forEach(el => el.remove());
                        
                        // Get main content
                        const main = document.querySelector('main') || 
                                    document.querySelector('article') || 
                                    document.querySelector('.content') ||
                                    document.body;
                        
                        return main.innerText || main.textContent || '';
                    }
                """)
                
                return content[:5000]  # Limit to 5000 characters
            finally:
                await page.close()
        except Exception as e:
            print(f"Failed to scrape {url}: {e}")
            return None
    
    async def get_web_context(self, query: str, scrape_content: bool = False) -> str:
        """
        Get web context for a query by searching and optionally scraping.
        """
        # Search the web
        search_results = await self.search_web(query, max_results=5)
        
        if not search_results:
            return ""
        
        context_parts = []
        sources = []
        
        for result in search_results:
            title = result.get("title", "")
            url = result.get("url", "")
            content = result.get("content", "")
            
            # Optionally scrape full content
            if scrape_content and url:
                scraped = await self.scrape_url(url)
                if scraped:
                    content = scraped
            
            if content:
                context_parts.append(f"Source: {title} ({url})\n{content}\n")
                sources.append(url)
        
        context = "\n---\n".join(context_parts)
        
        return context
    
    async def close(self):
        """Close the browser if it's open."""
        if self.browser:
            await self.browser.close()
            self.browser = None
