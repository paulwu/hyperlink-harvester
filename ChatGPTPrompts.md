You are a senior software engineer. Implement a small, production-quality CLI tool that extracts ONLY the left sidebar navigation links from https://docs.molt.bot/ and saves unique links to links.txt.

GOAL
- I primarily want the links shown in the left navigation pane (primary/sidebar nav).
- I do NOT want body-content links, header/footer links, or the “On this page” table-of-contents links.

HARD REQUIREMENTS
1) Language/runtime: Python 3.11+.
2) Output: Create/overwrite links.txt (or --out) in UTF-8. One absolute URL per line. No extra whitespace.
3) Scope filter: Only include URLs on the same origin as the start URL (https://docs.molt.bot). Exclude external URLs.
4) De-duplicate: Remove duplicates after normalization; preserve stable first-seen order.
5) URL normalization:
   - Resolve relative hrefs against the start URL.
   - Strip fragments (#...).
   - Keep query strings.
   - Normalize scheme to https for this domain.
   - Pick and document a consistent trailing-slash policy (either always strip or always keep) and apply it.
6) Sidebar-only extraction:
   - Parse the HTML and locate the “primary sidebar navigation” element.
   - Strategy (must implement):
     a) Try known/common selectors first (implement several):
        - nav[aria-label="Navigation"]
        - nav[role="navigation"]
        - aside nav
        - elements whose id/class contains "sidebar" or "nav" (e.g., md-sidebar / md-nav patterns used by common doc themes)
     b) If multiple candidates match, choose the best one using a heuristic:
        - Prefer the candidate containing the text "Navigation" (case-insensitive), OR
        - Prefer the candidate with the largest count of INTERNAL <a href> links, excluding any candidate containing the text "On this page".
     c) If no reasonable sidebar candidate is found, fail with a clear error message and exit non-zero.
7) Link extraction rules:
   - Only <a href="..."> inside the chosen sidebar container.
   - Ignore mailto:, tel:, javascript:, empty href, and purely fragment hrefs.
   - Optionally allow including non-HTML internal assets as output, but default behavior should include ANY internal URL found in sidebar (docs pages), while still filtering external.
8) CLI UX (argparse):
   - --start-url (default https://docs.molt.bot/)
   - --out (default links.txt)
   - --verbose (prints chosen sidebar selection reason + counts)
9) Networking:
   - Use requests with a descriptive User-Agent.
   - Use timeouts (connect+read).
   - If request fails, show an actionable error.

DELIVERABLES
- Single file: extract_sidebar_links.py
- Include docstring, inline comments, and type hints.
- Must run: python extract_sidebar_links.py (defaults should work)

ACCEPTANCE CRITERIA
- Running with defaults writes only https://docs.molt.bot/... links that appear in the left nav pane.
- No “On this page” TOC links.
- Duplicates removed; order stable.

Now implement extract_sidebar_links.py. Before the code, briefly explain the sidebar-detection heuristic (selectors + fallback scoring). Then provide full runnable code only (no pseudocode).


IMPORTANT: Do not omit any requirement. If any requirement is ambiguous, make a reasonable choice and document it in code comments. Do not return pseudo-code; return complete runnable code only.
