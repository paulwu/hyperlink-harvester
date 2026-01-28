#!/usr/bin/env python3
"""
extract_links.py - CLI tool to extract left sidebar navigation links from documentation sites.

Sidebar Detection Heuristic:
============================
1. Try known/common selectors in priority order:
   - nav[aria-label="Navigation"]
   - nav[role="navigation"]
   - aside nav
   - Elements with id/class containing "sidebar" or "nav" (e.g., md-sidebar, md-nav)

2. If multiple candidates match, score them using:
   - EXCLUDE any candidate containing "On this page" text (likely TOC)
   - PREFER candidate containing "Navigation" text (case-insensitive)
   - FALLBACK: prefer candidate with the most internal <a href> links

3. If no reasonable sidebar found, exit with clear error.

Trailing Slash Policy: STRIP trailing slashes for consistency (documented choice).

Author: Generated CLI Tool
"""

import argparse
import os
import sys
from typing import Optional
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, Tag


# Constants
DEFAULT_START_URL = "https://docs.molt.bot/"
DEFAULT_OUTPUT_FILE = "output/links.txt"
USER_AGENT = "SidebarLinkExtractor/1.0 (Python CLI tool for extracting sidebar navigation links)"
REQUEST_TIMEOUT = (10, 30)  # (connect timeout, read timeout)


def normalize_url(href: str, base_url: str, target_origin: str) -> Optional[str]:
    """
    Normalize a URL:
    - Resolve relative hrefs against base_url
    - Strip fragments (#...)
    - Keep query strings
    - Normalize scheme to https for target domain
    - Strip trailing slashes (documented policy)
    
    Returns None if URL should be excluded (external, invalid, etc.)
    """
    # Ignore special protocols and empty/fragment-only hrefs
    if not href or href.startswith(('mailto:', 'tel:', 'javascript:')):
        return None
    
    # Skip purely fragment hrefs (e.g., "#section")
    if href.startswith('#'):
        return None
    
    # Resolve relative URL against base
    absolute_url = urljoin(base_url, href)
    
    # Parse the URL
    parsed = urlparse(absolute_url)
    
    # Check if same origin
    target_parsed = urlparse(target_origin)
    if parsed.netloc != target_parsed.netloc:
        return None  # External URL, exclude
    
    # Normalize: ensure https scheme for this domain
    scheme = 'https'
    
    # Strip fragment
    fragment = ''
    
    # Keep query string as-is
    query = parsed.query
    
    # Strip trailing slash (documented policy)
    path = parsed.path.rstrip('/') if parsed.path != '/' else '/'
    
    # Reconstruct URL
    normalized = urlunparse((scheme, parsed.netloc, path, '', query, fragment))
    
    return normalized


def count_internal_links(element: Tag, base_url: str, target_origin: str) -> int:
    """Count the number of internal links within an element."""
    count = 0
    for a_tag in element.find_all('a', href=True):
        href = a_tag.get('href', '')
        normalized = normalize_url(href, base_url, target_origin)
        if normalized:
            count += 1
    return count


def find_sidebar_container(soup: BeautifulSoup, base_url: str, target_origin: str, verbose: bool = False) -> Optional[Tag]:
    """
    Find the primary sidebar navigation container using heuristics.
    
    Strategy:
    1. Try known selectors
    2. Score candidates and pick the best one
    3. Exclude candidates containing "On this page" text
    """
    candidates: list[tuple[Tag, str, int]] = []  # (element, reason, score)
    
    # Selector strategies in priority order
    selector_strategies = [
        ('nav[aria-label="Navigation"]', 'nav with aria-label="Navigation"'),
        ('nav[role="navigation"]', 'nav with role="navigation"'),
        ('aside nav', 'nav inside aside element'),
    ]
    
    # Try CSS selectors first
    for selector, description in selector_strategies:
        elements = soup.select(selector)
        for el in elements:
            candidates.append((el, description, 0))
    
    # Try id/class containing "sidebar" or "nav" patterns
    # Common patterns: md-sidebar, sidebar, nav, md-nav
    for tag in soup.find_all(['nav', 'aside', 'div', 'ul']):
        tag_id = tag.get('id', '') or ''
        tag_class = ' '.join(tag.get('class', []))
        combined = f"{tag_id} {tag_class}".lower()
        
        if 'sidebar' in combined or 'md-nav' in combined or 'site-nav' in combined:
            # Avoid duplicates
            if tag not in [c[0] for c in candidates]:
                candidates.append((tag, f'element with id/class containing sidebar/nav pattern: {tag_id or tag_class[:50]}', 0))
    
    if not candidates:
        return None
    
    if verbose:
        print(f"[DEBUG] Found {len(candidates)} initial sidebar candidates")
    
    # Filter and score candidates
    scored_candidates: list[tuple[Tag, str, int]] = []
    
    for element, reason, _ in candidates:
        element_text = element.get_text(separator=' ', strip=True).lower()
        
        # EXCLUDE candidates containing "on this page" (likely TOC)
        if 'on this page' in element_text:
            if verbose:
                print(f"[DEBUG] Excluding candidate ({reason}): contains 'on this page'")
            continue
        
        # Score the candidate
        score = 0
        
        # Prefer candidates containing "Navigation" text
        if 'navigation' in element_text:
            score += 100
        
        # Add score based on number of internal links
        link_count = count_internal_links(element, base_url, target_origin)
        score += link_count
        
        scored_candidates.append((element, reason, score))
        
        if verbose:
            print(f"[DEBUG] Candidate ({reason}): score={score}, internal_links={link_count}")
    
    if not scored_candidates:
        return None
    
    # Sort by score descending and pick the best
    scored_candidates.sort(key=lambda x: x[2], reverse=True)
    best_candidate, best_reason, best_score = scored_candidates[0]
    
    if verbose:
        print(f"[INFO] Selected sidebar: {best_reason} (score: {best_score})")
    
    return best_candidate


def extract_sidebar_links(
    start_url: str,
    output_file: str,
    verbose: bool = False
) -> int:
    """
    Main extraction logic.
    
    Returns:
        0 on success, non-zero on failure
    """
    # Parse target origin from start URL
    parsed_start = urlparse(start_url)
    target_origin = f"{parsed_start.scheme}://{parsed_start.netloc}"
    
    if verbose:
        print(f"[INFO] Fetching: {start_url}")
        print(f"[INFO] Target origin: {target_origin}")
    
    # Fetch the page
    try:
        response = requests.get(
            start_url,
            headers={'User-Agent': USER_AGENT},
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        print(f"[ERROR] Request timed out while fetching {start_url}", file=sys.stderr)
        print("[ACTION] Check your internet connection or try again later.", file=sys.stderr)
        return 1
    except requests.exceptions.ConnectionError as e:
        print(f"[ERROR] Connection error while fetching {start_url}: {e}", file=sys.stderr)
        print("[ACTION] Verify the URL is correct and the site is accessible.", file=sys.stderr)
        return 1
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] HTTP error {response.status_code} while fetching {start_url}", file=sys.stderr)
        print(f"[ACTION] The server returned an error. Details: {e}", file=sys.stderr)
        return 1
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to fetch {start_url}: {e}", file=sys.stderr)
        return 1
    
    if verbose:
        print(f"[INFO] Received {len(response.content)} bytes, status: {response.status_code}")
    
    # Parse HTML
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find sidebar container
    sidebar = find_sidebar_container(soup, start_url, target_origin, verbose)
    
    if sidebar is None:
        print("[ERROR] Could not find a suitable sidebar navigation container.", file=sys.stderr)
        print("[ACTION] The page structure may not match expected patterns. Check if the URL is correct.", file=sys.stderr)
        return 1
    
    # Extract links from sidebar
    seen_urls: set[str] = set()
    unique_links: list[str] = []  # Preserve first-seen order
    
    for a_tag in sidebar.find_all('a', href=True):
        href = a_tag.get('href', '')
        normalized = normalize_url(href, start_url, target_origin)
        
        if normalized and normalized not in seen_urls:
            seen_urls.add(normalized)
            unique_links.append(normalized)
    
    if verbose:
        print(f"[INFO] Extracted {len(unique_links)} unique internal links from sidebar")
    
    # Ensure output directory exists
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Write to output file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for link in unique_links:
                f.write(f"{link}\n")
        
        if verbose:
            print(f"[INFO] Wrote {len(unique_links)} links to {output_file}")
        else:
            print(f"Extracted {len(unique_links)} sidebar links to {output_file}")
            
    except IOError as e:
        print(f"[ERROR] Failed to write to {output_file}: {e}", file=sys.stderr)
        return 1
    
    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Extract sidebar navigation links from documentation sites.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python script/extract_links.py
  python script/extract_links.py --start-url https://docs.example.com/
  python script/extract_links.py --out my_links.txt --verbose
        """
    )
    
    parser.add_argument(
        '--start-url',
        type=str,
        default=DEFAULT_START_URL,
        help=f'The documentation URL to extract sidebar links from (default: {DEFAULT_START_URL})'
    )
    
    parser.add_argument(
        '--out',
        type=str,
        default=DEFAULT_OUTPUT_FILE,
        help=f'Output file path (default: {DEFAULT_OUTPUT_FILE})'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print detailed information about sidebar selection and link counts'
    )
    
    args = parser.parse_args()
    
    return extract_sidebar_links(
        start_url=args.start_url,
        output_file=args.out,
        verbose=args.verbose
    )


if __name__ == '__main__':
    sys.exit(main())
