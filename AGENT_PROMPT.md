# Hyperlink Scraper Agent Prompt

Use this prompt with any LLM agent (ChatGPT, Claude, Copilot, etc.) to scrape links from a webpage.

---

## Reusable Agent Prompt

Copy and use this prompt, replacing `{{URL}}` and `{{OUTPUT_FILE}}` with your values:

```
Execute the following command to scrape hyperlinks:

python script/scrape_links.py "{{URL}}" "{{OUTPUT_FILE}}"

If the script doesn't exist, run this pip install first:
pip install requests beautifulsoup4

Optional flags:
- Add --scope internal    → Only same-domain links
- Add --scope external    → Only external links  
- Add --scope sidebar     → Only sidebar/navigation links (for docs)
- Add --include-text      → Include link anchor text
- Add --verbose           → Show debug information
```

---

## Quick Examples

### 1. Scrape all links from a webpage
```bash
python script/scrape_links.py "https://example.com" "output/links.txt"
```

### 2. Scrape only internal links
```bash
python script/scrape_links.py "https://docs.python.org" "output/python_docs.txt" --scope internal
```

### 3. Scrape sidebar navigation (for documentation sites)
```bash
python script/scrape_links.py "https://docs.molt.bot/" "output/molt_nav.txt" --scope sidebar
```

### 4. Scrape with link text included
```bash
python script/scrape_links.py "https://example.com" "output/links_with_text.txt" --include-text
```

---

## One-Liner Template

For quick agent use, just substitute the URL and filename:

```bash
python script/scrape_links.py "YOUR_URL_HERE" "output/YOUR_FILENAME.txt"
```

---

## Python API Usage

You can also import and use the scraper programmatically:

```python
from script.scrape_links import scrape_links

# Basic usage
scrape_links(
    url="https://example.com",
    output_file="output/links.txt"
)

# With options
scrape_links(
    url="https://docs.example.com",
    output_file="output/docs.txt",
    scope="internal",      # 'all', 'internal', 'external', 'sidebar'
    verbose=True,
    include_text=True
)
```

---

## Output Format

Default output (one URL per line):
```
https://example.com/page1
https://example.com/page2
https://example.com/page3
```

With `--include-text`:
```
https://example.com/page1 | Home Page
https://example.com/page2 | About Us
https://example.com/page3 | Contact
```
