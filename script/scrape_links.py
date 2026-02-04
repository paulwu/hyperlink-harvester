#!/usr/bin/env python3
"""
scrape_links.py - Reusable CLI tool to extract hyperlinks from any webpage.

This is a general-purpose link scraper that can be used as:
- A standalone CLI tool
- An agent/automation component (accepts URL and output file as parameters)

Usage:
  python script/scrape_links.py <URL> <OUTPUT_FILE>
  python script/scrape_links.py https://example.com output/links.txt
  python script/scrape_links.py https://example.com output/links.txt --scope all
  python script/scrape_links.py https://example.com output/links.txt --scope internal --verbose
  python script/scrape_links.py https://example.com output/links.txt --js  # For JS-rendered pages

Scope Options:
  - 'all'      : Extract all hyperlinks (internal + external)
  - 'internal' : Only links on the same domain as the URL
  - 'external' : Only links to different domains
  - 'sidebar'  : Only sidebar/navigation links (for documentation sites)

Author: Hyperlink Harvester
"""

import argparse
import os
import sys
import time
from typing import Optional
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, Tag

# Optional: Selenium for JavaScript-rendered pages
SELENIUM_AVAILABLE = False
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    pass


# Constants
USER_AGENT = "HyperlinkHarvester/1.0 (Python link scraper tool)"
REQUEST_TIMEOUT = (10, 30)  # (connect timeout, read timeout)


def normalize_url(href: str, base_url: str, strip_fragments: bool = True) -> Optional[str]:
    """
    Normalize a URL:
    - Resolve relative hrefs against base_url
    - Optionally strip fragments (#...)
    - Keep query strings
    - Strip trailing slashes (except for root path)
    
    Returns None if URL is invalid or should be skipped.
    """
    # Ignore special protocols and empty/fragment-only hrefs
    if not href or href.startswith(('mailto:', 'tel:', 'javascript:', 'data:')):
        return None
    
    # Skip purely fragment hrefs (e.g., "#section")
    if href.startswith('#'):
        return None
    
    # Resolve relative URL against base
    absolute_url = urljoin(base_url, href)
    
    # Parse the URL
    parsed = urlparse(absolute_url)
    
    # Validate scheme
    if parsed.scheme not in ('http', 'https'):
        return None
    
    # Strip fragment if requested
    fragment = '' if strip_fragments else parsed.fragment
    
    # Strip trailing slash (except for root path)
    path = parsed.path.rstrip('/') if parsed.path != '/' else '/'
    
    # Reconstruct URL
    normalized = urlunparse((parsed.scheme, parsed.netloc, path, '', parsed.query, fragment))
    
    return normalized


def is_internal_url(url: str, base_url: str) -> bool:
    """Check if a URL is on the same domain as the base URL."""
    parsed_url = urlparse(url)
    parsed_base = urlparse(base_url)
    return parsed_url.netloc == parsed_base.netloc


def count_internal_links(element: Tag, base_url: str) -> int:
    """Count internal links within an element."""
    count = 0
    for a_tag in element.find_all('a', href=True):
        href = a_tag.get('href', '')
        normalized = normalize_url(href, base_url)
        if normalized and is_internal_url(normalized, base_url):
            count += 1
    return count


def find_sidebar_container(soup: BeautifulSoup, base_url: str, verbose: bool = False) -> Optional[Tag]:
    """
    Find the primary sidebar navigation container using heuristics.
    """
    candidates: list[tuple[Tag, str, int]] = []
    
    # Selector strategies in priority order
    selector_strategies = [
        ('nav[aria-label="Navigation"]', 'nav with aria-label="Navigation"'),
        ('nav[aria-label*="navigation" i]', 'nav with aria-label containing navigation'),
        ('nav[role="navigation"]', 'nav with role="navigation"'),
        ('aside nav', 'nav inside aside element'),
        ('.sidebar nav', 'nav inside .sidebar'),
        ('#sidebar nav', 'nav inside #sidebar'),
    ]
    
    # Try CSS selectors first
    for selector, description in selector_strategies:
        try:
            elements = soup.select(selector)
            for el in elements:
                candidates.append((el, description, 0))
        except Exception:
            continue
    
    # Try id/class containing "sidebar" or "nav" patterns
    for tag in soup.find_all(['nav', 'aside', 'div', 'ul']):
        tag_id = tag.get('id', '') or ''
        tag_class = ' '.join(tag.get('class', []))
        combined = f"{tag_id} {tag_class}".lower()
        
        if 'sidebar' in combined or 'sidenav' in combined or 'site-nav' in combined:
            if tag not in [c[0] for c in candidates]:
                candidates.append((tag, f'element with sidebar/nav pattern: {tag_id or tag_class[:50]}', 0))
    
    if not candidates:
        return None
    
    if verbose:
        print(f"[DEBUG] Found {len(candidates)} sidebar candidates")
    
    # Filter and score candidates
    scored_candidates: list[tuple[Tag, str, int]] = []
    
    for element, reason, _ in candidates:
        element_text = element.get_text(separator=' ', strip=True).lower()
        
        # EXCLUDE candidates containing "on this page" (likely TOC)
        if 'on this page' in element_text or 'table of contents' in element_text:
            if verbose:
                print(f"[DEBUG] Excluding candidate ({reason}): contains TOC text")
            continue
        
        score = 0
        
        # Prefer candidates containing "Navigation" text
        if 'navigation' in element_text:
            score += 100
        
        # Add score based on number of internal links
        link_count = count_internal_links(element, base_url)
        score += link_count
        
        scored_candidates.append((element, reason, score))
        
        if verbose:
            print(f"[DEBUG] Candidate ({reason}): score={score}, links={link_count}")
    
    if not scored_candidates:
        return None
    
    # Sort by score descending and pick the best
    scored_candidates.sort(key=lambda x: x[2], reverse=True)
    best_candidate, best_reason, best_score = scored_candidates[0]
    
    if verbose:
        print(f"[INFO] Selected sidebar: {best_reason} (score: {best_score})")
    
    return best_candidate


def fetch_page_html(url: str, use_js: bool = False, verbose: bool = False, wait_time: int = 3) -> Optional[str]:
    """
    Fetch page HTML, optionally using Selenium for JavaScript-rendered pages.
    
    Args:
        url: The URL to fetch
        use_js: Use Selenium for JavaScript rendering
        verbose: Print debug information
        wait_time: Seconds to wait for JS rendering
    
    Returns:
        HTML content as string, or None on failure
    """
    if use_js:
        if not SELENIUM_AVAILABLE:
            print("[ERROR] Selenium not installed. Install with: pip install selenium", file=sys.stderr)
            print("[INFO] Falling back to standard HTTP request...", file=sys.stderr)
            use_js = False
        else:
            try:
                if verbose:
                    print(f"[INFO] Using Selenium for JavaScript rendering...")
                
                options = ChromeOptions()
                options.add_argument('--headless')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument(f'--user-agent={USER_AGENT}')
                
                driver = webdriver.Chrome(options=options)
                driver.get(url)
                
                # Wait for page to load
                time.sleep(wait_time)
                
                html = driver.page_source
                driver.quit()
                
                if verbose:
                    print(f"[INFO] Received {len(html)} bytes via Selenium")
                
                return html
            except Exception as e:
                print(f"[ERROR] Selenium failed: {e}", file=sys.stderr)
                print("[INFO] Falling back to standard HTTP request...", file=sys.stderr)
                use_js = False
    
    # Standard HTTP request
    try:
        response = requests.get(
            url,
            headers={'User-Agent': USER_AGENT},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )
        response.raise_for_status()
        
        if verbose:
            print(f"[INFO] Received {len(response.content)} bytes, status: {response.status_code}")
        
        return response.text
    except requests.exceptions.Timeout:
        print(f"[ERROR] Request timed out while fetching {url}", file=sys.stderr)
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"[ERROR] Connection error: {e}", file=sys.stderr)
        return None
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] HTTP error: {e}", file=sys.stderr)
        return None
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Request failed: {e}", file=sys.stderr)
        return None


def scrape_links(
    url: str,
    output_file: str,
    scope: str = 'all',
    verbose: bool = False,
    include_text: bool = False,
    use_js: bool = False,
    wait_time: int = 3
) -> int:
    """
    Main scraping function.
    
    Args:
        url: The webpage URL to scrape
        output_file: Path to the output file
        scope: 'all', 'internal', 'external', or 'sidebar'
        verbose: Print detailed progress information
        include_text: Include link text in output (format: URL | Text)
        use_js: Use Selenium for JavaScript-rendered pages
        wait_time: Seconds to wait for JS rendering
    
    Returns:
        0 on success, non-zero on failure
    """
    if verbose:
        print(f"[INFO] Scraping: {url}")
        print(f"[INFO] Scope: {scope}")
        print(f"[INFO] Output: {output_file}")
        if use_js:
            print(f"[INFO] JavaScript rendering: enabled (wait: {wait_time}s)")
    
    # Fetch the page
    html = fetch_page_html(url, use_js=use_js, verbose=verbose, wait_time=wait_time)
    if html is None:
        return 1
    
    # Parse HTML
    soup = BeautifulSoup(html, 'html.parser')
    
    # Determine the search container
    if scope == 'sidebar':
        container = find_sidebar_container(soup, url, verbose)
        if container is None:
            print("[ERROR] Could not find a sidebar navigation container.", file=sys.stderr)
            return 1
    else:
        container = soup
    
    # Extract links
    seen_urls: set[str] = set()
    results: list[tuple[str, str]] = []  # (url, text)
    
    for a_tag in container.find_all('a', href=True):
        href = a_tag.get('href', '')
        normalized = normalize_url(href, url)
        
        if not normalized:
            continue
        
        # Apply scope filter
        is_internal = is_internal_url(normalized, url)
        
        if scope == 'internal' or scope == 'sidebar':
            if not is_internal:
                continue
        elif scope == 'external':
            if is_internal:
                continue
        # scope == 'all' includes everything
        
        # De-duplicate
        if normalized not in seen_urls:
            seen_urls.add(normalized)
            link_text = a_tag.get_text(strip=True) if include_text else ''
            results.append((normalized, link_text))
    
    if verbose:
        print(f"[INFO] Extracted {len(results)} unique links")
    
    # Ensure output directory exists
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Write to output file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for link, text in results:
                if include_text and text:
                    f.write(f"{link} | {text}\n")
                else:
                    f.write(f"{link}\n")
        
        print(f"✓ Extracted {len(results)} links to {output_file}")
            
    except IOError as e:
        print(f"[ERROR] Failed to write to {output_file}: {e}", file=sys.stderr)
        return 1
    
    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Scrape hyperlinks from any webpage.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape all links from a page
  python script/scrape_links.py https://example.com output/links.txt

  # Scrape only internal links
  python script/scrape_links.py https://example.com output/links.txt --scope internal

  # Scrape sidebar links from documentation sites
  python script/scrape_links.py https://docs.example.com output/nav.txt --scope sidebar

  # For JavaScript-rendered pages (requires: pip install selenium)
  python script/scrape_links.py https://example.com output/links.txt --js

  # Include link text in output
  python script/scrape_links.py https://example.com output/links.txt --include-text

  # Verbose mode for debugging
  python script/scrape_links.py https://example.com output/links.txt --verbose
        """
    )
    
    parser.add_argument(
        'url',
        type=str,
        help='The URL of the webpage to scrape'
    )
    
    parser.add_argument(
        'output',
        type=str,
        help='Output file path (e.g., output/links.txt)'
    )
    
    parser.add_argument(
        '--scope',
        type=str,
        choices=['all', 'internal', 'external', 'sidebar'],
        default='all',
        help='Scope of links to extract: all, internal, external, or sidebar (default: all)'
    )
    
    parser.add_argument(
        '--include-text',
        action='store_true',
        help='Include link text in output (format: URL | Text)'
    )
    
    parser.add_argument(
        '--js',
        action='store_true',
        help='Use Selenium for JavaScript-rendered pages (requires: pip install selenium)'
    )
    
    parser.add_argument(
        '--wait',
        type=int,
        default=3,
        help='Seconds to wait for JavaScript rendering (default: 3, only used with --js)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Print detailed progress information'
    )
    
    args = parser.parse_args()
    
    return scrape_links(
        url=args.url,
        output_file=args.output,
        scope=args.scope,
        verbose=args.verbose,
        include_text=args.include_text,
        use_js=args.js,
        wait_time=args.wait
    )


if __name__ == '__main__':
    sys.exit(main())
