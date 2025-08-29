import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urlunparse
from urllib.robotparser import RobotFileParser
import time
import re
from io import StringIO
import base64
from collections import defaultdict

# Import our enhanced modules
from sitemap_processor import SitemapProcessor

# Import optional modules with fallbacks
try:
    # Try lite version first (works without NLTK)
    from anchor_text_analyzer_lite import AnchorTextAnalyzerLite
    ANCHOR_ANALYSIS_AVAILABLE = True
    ANCHOR_ANALYZER_CLASS = AnchorTextAnalyzerLite
    print("Using lite anchor text analyzer")
except ImportError:
    ANCHOR_ANALYSIS_AVAILABLE = False
    ANCHOR_ANALYZER_CLASS = None
    print("Warning: Anchor text analysis not available")

try:
    from recommendation_engine import RecommendationEngine
    RECOMMENDATIONS_AVAILABLE = True
except ImportError:
    RECOMMENDATIONS_AVAILABLE = False
    print("Warning: Recommendations not available")

# Page configuration
st.set_page_config(
    page_title="Enhanced Internal Link Analyzer",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state variables
if 'urls' not in st.session_state:
    st.session_state.urls = []
if 'results' not in st.session_state:
    st.session_state.results = None
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False
if 'config' not in st.session_state:
    st.session_state.config = None

st.title("Enhanced Internal Link Analyzer")
st.markdown("""
This advanced tool analyzes internal hyperlinks on your website URLs to identify **duplicate links** and **anchor text optimization opportunities**.
It provides comprehensive SEO insights and actionable recommendations for improving your internal linking strategy.
""")

# ----------- DYNAMIC CONFIGURATION -----------

def get_dynamic_config(url_count):
    """Automatically determine optimal settings based on URL count."""
    if url_count <= 100:
        return {
            'delay': 1.0,
            'strategy': 'fast',
            'description': 'Fast analysis (≤100 URLs)',
            'estimated_time': '< 5 minutes'
        }
    elif url_count <= 500:
        return {
            'delay': 2.0,
            'strategy': 'balanced',
            'description': 'Balanced analysis (101-500 URLs)',
            'estimated_time': '5-20 minutes'
        }
    else:  # > 500
        return {
            'delay': 3.0,
            'strategy': 'thorough',
            'description': 'Thorough analysis (500+ URLs)',
            'estimated_time': '20+ minutes'
        }

# Sidebar configuration
st.sidebar.header("⚙️ Analysis Configuration")

# Content filtering option
content_filtering = st.sidebar.checkbox("Filter to main content only", value=True,
                                       help="Extract links only from main content, excluding navigation/footer")

# Skip blocked pages option
skip_blocked_pages = st.sidebar.checkbox("Skip blocked pages", value=False,
                                        help="Skip pages that return 403 errors instead of retrying")

# Inter-page delay option
inter_page_delay = st.sidebar.slider("Delay between pages (seconds)", min_value=1.0, max_value=10.0, value=3.0, step=0.5,
                                    help="Additional delay between processing different pages")

# Aggressive anti-bot mode
aggressive_mode = st.sidebar.checkbox("Aggressive anti-bot mode", value=False,
                                     help="Use more sophisticated browser simulation (slower but more effective)")

# Enhanced analysis options
if ANCHOR_ANALYSIS_AVAILABLE:
    enable_anchor_analysis = st.sidebar.checkbox("Enable Anchor Text Analysis", value=True,
                                               help="Analyze anchor text uniqueness and optimization")
    enable_optimization_scoring = st.sidebar.checkbox("Enable Optimization Scoring", value=True,
                                                    help="Score anchor text quality on multiple dimensions")
else:
    st.sidebar.warning("⚠️ Anchor text analysis unavailable (NLTK not installed)")
    enable_anchor_analysis = False
    enable_optimization_scoring = False

if RECOMMENDATIONS_AVAILABLE:
    enable_recommendations = st.sidebar.checkbox("Generate Recommendations", value=True,
                                               help="Generate prioritized SEO recommendations")
else:
    st.sidebar.warning("⚠️ Recommendations unavailable (dependencies missing)")
    enable_recommendations = False

st.sidebar.header("📋 About")
st.sidebar.info("""
This enhanced analyzer provides:
- ✅ Duplicate link detection
- ✅ Anchor text uniqueness validation
- ✅ Optimization scoring & recommendations
- ✅ Sitemap processing
- ✅ Comprehensive SEO insights
- ✅ Export capabilities
""")

st.sidebar.header("⚠️ Disclaimer")
st.sidebar.warning(
    "**Web Scraping Ethics:**\n"
    "- Only analyze websites you own or have permission to crawl\n"
    "- Respect robots.txt files\n"
    "- Use reasonable delays between requests\n"
    "- This tool is for SEO analysis purposes only"
)

def parse_urls_from_text(text):
    """Parse URLs from multiline text input."""
    urls = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            urls.append(line)
    return urls

def parse_urls_from_csv(csv_content):
    """Parse URLs from CSV content, looking for URL column."""
    try:
        df = pd.read_csv(StringIO(csv_content))
        # Look for URL column (case insensitive)
        url_col = None
        for col in df.columns:
            if 'url' in col.lower():
                url_col = col
                break
        if url_col:
            return df[url_col].dropna().tolist()
        else:
            # If no URL column, assume first column
            return df.iloc[:, 0].dropna().tolist()
    except Exception as e:
        st.error(f"Error parsing CSV: {str(e)}")
        return []

def validate_url(url):
    """Validate if URL is properly formatted."""
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except:
        return False

def get_domain(url):
    """Extract domain from URL."""
    parsed = urlparse(url)
    return parsed.netloc.lower()

def normalize_url(url):
    """Normalize URL by removing fragments and trailing slashes."""
    parsed = urlparse(url)
    # Remove fragment
    parsed = parsed._replace(fragment='')
    # Remove trailing slash unless it's the root
    path = parsed.path
    if path.endswith('/') and len(path) > 1:
        path = path.rstrip('/')
    parsed = parsed._replace(path=path)
    return urlunparse(parsed)

# ----------- ROBOTS.TXT FUNCTIONS -----------

@st.cache_data(ttl=3600)  # Cache for 1 hour
def check_robots_txt(domain, user_agent='*'):
    """Check if crawling is allowed for the domain."""
    try:
        robots_url = f"https://{domain}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, '/')
    except:
        # If robots.txt is not accessible, assume allowed
        return True

# ----------- WEB SCRAPING FUNCTIONS -----------

def fetch_page_content(url, timeout=20, max_retries=5, skip_blocked=False, aggressive_mode=False):
    """Fetch page content with proper headers and aggressive retry logic."""
    import random

    # Extended user agents for aggressive mode
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0',
    ]

    if aggressive_mode:
        # Add more user agents and randomize order
        additional_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        ]
        user_agents.extend(additional_agents)
        random.shuffle(user_agents)  # Randomize order

    for attempt in range(max_retries):
        try:
            headers = {
                'User-Agent': user_agents[attempt % len(user_agents)],
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
                'DNT': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            }

            if aggressive_mode:
                # Add more realistic headers
                headers.update({
                    'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                    'Sec-Ch-Ua-Mobile': '?0',
                    'Sec-Ch-Ua-Platform': '"Windows"',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1',
                })

            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.text

        except requests.HTTPError as e:
            if e.response.status_code in [403, 429] and attempt < max_retries - 1:
                # Longer wait for 403/429 errors
                wait_time = min(2 ** attempt * 2, 30)  # Cap at 30 seconds
                if aggressive_mode:
                    wait_time = min(wait_time * 1.5, 45)  # Even longer in aggressive mode
                st.warning(f"HTTP {e.response.status_code} for {url}, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                if skip_blocked and e.response.status_code in [403, 429]:
                    st.warning(f"Skipping blocked page: {url}")
                    return None  # Return None to indicate page should be skipped
                raise Exception(f"HTTP {e.response.status_code} for {url}: {e.response.reason}")

        except requests.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = min(2 ** attempt, 15)  # Cap at 15 seconds
                if aggressive_mode:
                    wait_time = min(wait_time * 1.2, 20)  # Slightly longer in aggressive mode
                time.sleep(wait_time)
                continue
            else:
                if skip_blocked:
                    st.warning(f"Skipping unreachable page: {url}")
                    return None  # Return None to indicate page should be skipped
                raise Exception(f"Failed to fetch {url} after {max_retries} attempts: {str(e)}")

    if skip_blocked:
        st.warning(f"Skipping blocked page after all retries: {url}")
        return None
    raise Exception(f"Failed to fetch {url} after {max_retries} attempts")

def extract_main_content_links(html_content, base_url, filter_content=True):
    """Extract hyperlinks from page content, with optional main content filtering."""
    soup = BeautifulSoup(html_content, 'lxml')
    links = []

    if filter_content:
        # Remove unwanted elements
        unwanted_selectors = [
            'nav', 'header', '.nav', '.navigation', '.navbar', '.menu',
            'footer', '.footer', '.site-footer',
            'aside', '.sidebar', '.widget', '.widget-area',
            '.comments', '.comment', '#comments',
            '.related-posts', '.related', '.similar',
            '.social-share', '.share', '.sharing',
            '.advertisement', '.ads', '.ad',
            '.breadcrumb', '.breadcrumbs',
            '.pagination', '.pager'
        ]

        for selector in unwanted_selectors:
            for element in soup.select(selector):
                element.decompose()

        # Try to find main content areas (be less restrictive)
        content_selectors = [
            'article', '.post-content', '.entry-content', '.content',
            'main', '.main-content', '.article-content',
            '.post', '.entry', '.single-post',
            '.blog-post', '.article-body', '.post-body',
            '[role="main"]', '.main',
            '#content', '#main', '.container', '.wrapper'
        ]

        main_content = None

        # Try to find main content container
        for selector in content_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break

        # If no main content found, use body but be less aggressive in filtering
        if not main_content:
            main_content = soup.find('body')

        # Only remove the most obvious non-content elements
        if main_content:
            # Remove script, style, and navigation elements
            for element in main_content.find_all(['script', 'style', 'nav', '.nav', '.navigation']):
                element.decompose()

        content_to_search = main_content if main_content else soup
    else:
        # Extract from entire page
        content_to_search = soup

    if content_to_search:
        # Extract links from content area
        for a_tag in content_to_search.find_all('a', href=True):
            href = a_tag.get('href')

            # Improved anchor text extraction
            anchor_text = ''

            # First, try to get direct text content
            if a_tag.string and a_tag.string.strip():
                anchor_text = a_tag.string.strip()
            else:
                # If no direct text, get all text content but exclude certain elements
                text_parts = []
                for element in a_tag.contents:
                    if isinstance(element, str):
                        text_parts.append(element.strip())
                    elif element.name not in ['img', 'svg', 'script', 'style']:
                        text_parts.append(element.get_text(strip=True))

                anchor_text = ' '.join(text_parts).strip()

            # Clean up the anchor text
            anchor_text = re.sub(r'\s+', ' ', anchor_text)  # Replace multiple whitespace with single space
            anchor_text = anchor_text[:200] if len(anchor_text) > 200 else anchor_text  # Limit length

            # Skip if anchor text is empty, too short, or generic
            if not anchor_text or len(anchor_text) < 3:
                continue

            generic_terms = ['read more', 'click here', 'learn more', 'here', 'more', 'continue reading', 'see more']
            if anchor_text.lower() in generic_terms:
                continue

            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, href)

            # Normalize the URL
            normalized_url = normalize_url(absolute_url)

            links.append({
                'url': normalized_url,
                'anchor': anchor_text
            })

    return links

def filter_internal_links(links, domain):
    """Filter links to only include internal ones."""
    internal_links = []
    for link in links:
        link_domain = get_domain(link['url'])
        if link_domain == domain:
            internal_links.append(link)
    return internal_links

# ----------- ANALYSIS FUNCTIONS -----------

def analyze_internal_links_enhanced(urls, progress_callback=None):
    """Enhanced analysis function with new features."""
    all_internal_links = []
    errors = []

    # Get dynamic configuration based on URL count
    config = get_dynamic_config(len(urls))
    delay = config['delay']

    # Group URLs by domain
    domain_groups = {}
    for url in urls:
        domain = get_domain(url)
        if domain not in domain_groups:
            domain_groups[domain] = []
        domain_groups[domain].append(url)

    total_urls = len(urls)
    processed = 0

    for domain, domain_urls in domain_groups.items():
        # Check robots.txt for this domain
        if not check_robots_txt(domain):
            errors.append(f"Robots.txt disallows crawling for domain: {domain}")
            continue

        for url in domain_urls:
            try:
                # Fetch page content
                html_content = fetch_page_content(url, skip_blocked=skip_blocked_pages, aggressive_mode=aggressive_mode)

                # Skip if page was blocked and we're skipping blocked pages
                if html_content is None:
                    processed += 1
                    if progress_callback:
                        progress = processed / total_urls
                        progress_callback(progress, f"Processed {processed}/{total_urls} URLs (skipped blocked page)")
                    continue

                # Extract all links
                all_links = extract_main_content_links(html_content, url, content_filtering)

                # Filter internal links
                internal_links = filter_internal_links(all_links, domain)

                # Add source information
                for link in internal_links:
                    link['source_url'] = url
                    link['source_domain'] = domain
                    all_internal_links.append(link)

                processed += 1
                if progress_callback:
                    progress = processed / total_urls
                    progress_callback(progress, f"Processed {processed}/{total_urls} URLs ({len(internal_links)} internal links found)")

                # Rate limiting - use the longer of the two delays
                actual_delay = max(delay, inter_page_delay)
                time.sleep(actual_delay)

            except Exception as e:
                errors.append(f"Error processing {url}: {str(e)}")
                processed += 1
                if progress_callback:
                    progress = processed / total_urls
                    progress_callback(progress, f"Processed {processed}/{total_urls} URLs")

    return all_internal_links, errors

def find_duplicate_links(internal_links):
    """Find duplicate links on the SAME page pointing to the same destination."""
    from collections import defaultdict

    # Group by source page (target_url), then by destination URL
    page_destination_groups = defaultdict(lambda: defaultdict(list))

    for link in internal_links:
        page_destination_groups[link['source_url']][link['url']].append(link['anchor'])

    # Find duplicates: same source page linking multiple times to same destination
    duplicate_records = []
    for target_url, destinations in page_destination_groups.items():
        for dest_url, anchors in destinations.items():
            if len(anchors) > 1:  # Multiple links to same destination from same page
                for anchor in anchors:
                    duplicate_records.append({
                        'target_url': target_url,        # Page being analyzed
                        'destination_url': dest_url,     # Where links point to
                        'anchor_text_used': anchor       # Anchor text of each duplicate link
                    })

    # Sort by target URL, then destination URL
    duplicate_records.sort(key=lambda x: (x['target_url'], x['destination_url']))

    return duplicate_records

def create_horizontal_dataframe(duplicate_records):
    """Convert vertical duplicate records to horizontal format."""
    if not duplicate_records:
        return pd.DataFrame()

    # Group by target URL
    from collections import defaultdict
    target_groups = defaultdict(list)

    for record in duplicate_records:
        target_groups[record['target_url']].append({
            'destination_url': record['destination_url'],
            'anchor_text_used': record['anchor_text_used']
        })

    # Create horizontal rows
    horizontal_rows = []
    max_duplicates = max(len(duplicates) for duplicates in target_groups.values())

    for target_url, duplicates in target_groups.items():
        row = {'target_url': target_url}

        for i, duplicate in enumerate(duplicates):
            row[f'destination_url_{i+1}'] = duplicate['destination_url']
            row[f'anchor_text_used_{i+1}'] = duplicate['anchor_text_used']

        # Fill empty columns with empty strings
        for i in range(len(duplicates), max_duplicates):
            row[f'destination_url_{i+1}'] = ''
            row[f'anchor_text_used_{i+1}'] = ''

        horizontal_rows.append(row)

    return pd.DataFrame(horizontal_rows)

def create_results_dataframe(duplicate_records):
    """Create a pandas DataFrame from individual duplicate link records."""
    if not duplicate_records:
        return pd.DataFrame(columns=['Target URL', 'Destination URL', 'Anchor Text Used'])

    return pd.DataFrame(duplicate_records)

# ----------- EXPORT FUNCTIONS -----------

def get_csv_download_link(df, filename):
    """Generate CSV download link."""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV</a>'
    return href

# ----------- MAIN APP INTERFACE -----------

# URL Input Section
st.header("📝 URL Input")

tab1, tab2, tab3 = st.tabs(["Manual Entry", "File Upload", "Sitemap URL"])

with tab1:
    st.subheader("Enter URLs Manually")
    st.markdown("Enter one URL per line:")
    manual_urls = st.text_area(
        "URLs",
        height=150,
        placeholder="https://example.com/page1\nhttps://example.com/page2\nhttps://other.com/page",
        help="Enter each URL on a new line"
    )

    if st.button("Process Manual URLs", key="manual_btn"):
        if manual_urls.strip():
            urls = parse_urls_from_text(manual_urls)
            valid_urls = [url for url in urls if validate_url(url)]
            invalid_urls = [url for url in urls if not validate_url(url)]

            if invalid_urls:
                st.warning(f"Invalid URLs found and skipped: {', '.join(invalid_urls[:5])}"
                          + (f" and {len(invalid_urls)-5} more" if len(invalid_urls) > 5 else ""))

            if valid_urls:
                st.session_state.urls = valid_urls  # No artificial limit
                # Set dynamic configuration based on URL count
                st.session_state.config = get_dynamic_config(len(valid_urls))
                st.success(f"Loaded {len(st.session_state.urls)} valid URLs")
                st.session_state.analysis_complete = False
            else:
                st.error("No valid URLs found")
        else:
            st.error("Please enter some URLs")

with tab2:
    st.subheader("Upload File")
    st.markdown("Upload a CSV file with URLs or a text file with one URL per line:")

    uploaded_file = st.file_uploader(
        "Choose file",
        type=['csv', 'txt'],
        help="CSV should have a column named 'URL' or URLs in the first column. Text files should have one URL per line."
    )

    if uploaded_file is not None:
        try:
            content = uploaded_file.read().decode('utf-8')

            if uploaded_file.name.endswith('.csv'):
                urls = parse_urls_from_csv(content)
            else:
                urls = parse_urls_from_text(content)

            valid_urls = [url for url in urls if validate_url(url)]
            invalid_urls = [url for url in urls if not validate_url(url)]

            if invalid_urls:
                st.warning(f"Invalid URLs found and skipped: {', '.join(invalid_urls[:5])}"
                          + (f" and {len(invalid_urls)-5} more" if len(invalid_urls) > 5 else ""))

            if valid_urls:
                st.session_state.urls = valid_urls  # No artificial limit
                # Set dynamic configuration based on URL count
                st.session_state.config = get_dynamic_config(len(valid_urls))
                st.success(f"Loaded {len(st.session_state.urls)} valid URLs from file")
                st.session_state.analysis_complete = False
            else:
                st.error("No valid URLs found in file")

        except Exception as e:
            st.error(f"Error reading file: {str(e)}")

with tab3:
    st.subheader("Process Sitemap")
    st.markdown("Enter a sitemap URL or domain to auto-discover sitemaps:")

    sitemap_input = st.text_input(
        "Sitemap URL or Domain",
        placeholder="https://example.com/sitemap.xml or example.com",
        help="Enter full sitemap URL or just domain to auto-discover"
    )

    if st.button("Process Sitemap", key="sitemap_btn"):
        if sitemap_input.strip():
            try:
                processor = SitemapProcessor()

                if '://' in sitemap_input:
                    # Full sitemap URL provided
                    if 'sitemap' in sitemap_input.lower():
                        urls_data = processor.parse_sitemap(sitemap_input)
                        urls = [item['url'] for item in urls_data if 'url' in item]
                    else:
                        st.error("Please provide a valid sitemap URL")
                        urls = []
                else:
                    # Domain provided - auto-discover
                    urls = processor.extract_urls_from_sitemaps(sitemap_input)

                if urls:
                    st.session_state.urls = urls
                    st.session_state.config = get_dynamic_config(len(urls))
                    st.success(f"Loaded {len(urls)} URLs from sitemap")
                    st.session_state.analysis_complete = False
                else:
                    st.error("No URLs found in sitemap")

            except Exception as e:
                error_msg = str(e)
                if "403 Forbidden" in error_msg:
                    st.error("❌ **Access Blocked**: The website is blocking automated access to this sitemap. This is common with protected or high-security sites.")
                    st.info("💡 **Suggestions**:\n"
                           "- Try accessing the sitemap URL manually in your browser\n"
                           "- The website may require special permissions or authentication\n"
                           "- Consider using manual URL entry instead")
                elif "Not a gzipped file" in error_msg:
                    st.error("❌ **Sitemap Format Error**: The sitemap content couldn't be processed properly.")
                    st.info("💡 **Suggestions**:\n"
                           "- Try accessing the sitemap URL directly in your browser\n"
                           "- The sitemap may be corrupted or in an unsupported format\n"
                           "- Consider using manual URL entry for individual pages")
                elif "Failed to parse XML" in error_msg:
                    st.error("❌ **XML Parsing Error**: The sitemap contains invalid XML format.")
                    st.info("💡 **Suggestions**:\n"
                           "- Check if the sitemap URL is correct\n"
                           "- The sitemap may be malformed or corrupted\n"
                           "- Try a different sitemap URL from the same site")
                else:
                    st.error(f"❌ **Processing Error**: {error_msg}")
                    st.info("💡 **General Suggestions**:\n"
                           "- Verify the sitemap URL is accessible\n"
                           "- Try using manual URL entry instead\n"
                           "- Check if the website has changed its structure")

# Display loaded URLs
if st.session_state.urls:
    st.header("📋 Loaded URLs")
    st.write(f"Total URLs: {len(st.session_state.urls)}")

    # Show domains
    domains = list(set(get_domain(url) for url in st.session_state.urls))
    st.write(f"Domains: {', '.join(domains)}")

    with st.expander("Show URLs"):
        for i, url in enumerate(st.session_state.urls, 1):
            st.write(f"{i}. {url}")

    # Analysis Section
    st.header("🔍 Analysis")

    if st.button("Start Analysis", type="primary"):
        if not st.session_state.urls:
            st.error("No URLs loaded")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()

            def progress_callback(progress, message):
                progress_bar.progress(progress)
                status_text.text(message)

            with st.spinner("Analyzing internal links..."):
                try:
                    internal_links, errors = analyze_internal_links_enhanced(
                        st.session_state.urls,
                        progress_callback
                    )

                    duplicate_records = find_duplicate_links(internal_links)
                    results_df = create_results_dataframe(duplicate_records)
                    horizontal_df = create_horizontal_dataframe(duplicate_records)

                    # Enhanced analysis
                    enhanced_results = {
                        'duplicate_records': duplicate_records,
                        'anchor_issues': {},
                        'optimization_scores': {},
                        'recommendations': [],
                        'site_summary': {}
                    }

                    if enable_anchor_analysis and ANCHOR_ANALYSIS_AVAILABLE and ANCHOR_ANALYZER_CLASS:
                        analyzer = ANCHOR_ANALYZER_CLASS()
                        enhanced_results['anchor_issues'] = analyzer.analyze_uniqueness(internal_links)

                    if enable_optimization_scoring and ANCHOR_ANALYSIS_AVAILABLE and ANCHOR_ANALYZER_CLASS:
                        analyzer = ANCHOR_ANALYZER_CLASS()
                        for link in internal_links:
                            key = f"{link['source_url']} -> {link['url']}"
                            enhanced_results['optimization_scores'][key] = analyzer.score_anchor_text(
                                link['anchor'],
                                {'source_url': link['source_url'], 'target_url': link['url']}
                            )

                    # Generate site summary
                    total_links = len(internal_links)
                    duplicate_count = len(enhanced_results['duplicate_records'])
                    enhanced_results['site_summary'] = {
                        'total_internal_links': total_links,
                        'duplicate_percentage': (duplicate_count / total_links * 100) if total_links > 0 else 0,
                        'unique_anchors': len(set(link['anchor'].strip().lower() for link in internal_links if link['anchor'].strip())),
                        'unique_anchor_percentage': 0  # Calculate this
                    }

                    if enable_recommendations and RECOMMENDATIONS_AVAILABLE:
                        engine = RecommendationEngine()
                        enhanced_results['recommendations'] = engine.generate_comprehensive_recommendations(
                            enhanced_results['duplicate_records'],
                            enhanced_results['anchor_issues'],
                            enhanced_results['optimization_scores'],
                            enhanced_results['site_summary']
                        )

                    st.session_state.results = {
                        'duplicate_records': duplicate_records,
                        'dataframe': results_df,
                        'horizontal_dataframe': horizontal_df,
                        'total_links': len(internal_links),
                        'errors': errors,
                        'enhanced_results': enhanced_results
                    }
                    st.session_state.analysis_complete = True

                    progress_bar.empty()
                    status_text.empty()

                except Exception as e:
                    st.error(f"Analysis failed: {str(e)}")
                    progress_bar.empty()
                    status_text.empty()

# Results Section
if st.session_state.analysis_complete and st.session_state.results:
    results = st.session_state.results

    # Create tabs for different result types
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Summary", "🔗 Duplicate Links", "📝 Anchor Analysis", "💡 Recommendations"
    ])

    with tab1:
        # Summary dashboard
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Internal Links Found", results['total_links'])
        with col2:
            st.metric("Duplicate Links", len(results['duplicate_records']))
        with col3:
            unique_anchors = results.get('enhanced_results', {}).get('site_summary', {}).get('unique_anchors', 0)
            st.metric("Unique Anchors", unique_anchors)
        with col4:
            avg_score = 0
            if results.get('enhanced_results', {}).get('optimization_scores'):
                scores = [score.get('overall', 0) for score in results['enhanced_results']['optimization_scores'].values()]
                avg_score = sum(scores) / len(scores) if scores else 0
            st.metric("Avg Optimization Score", f"{avg_score:.1f}")

    with tab2:
        # Existing duplicate links display
        if results['duplicate_records']:
            st.dataframe(create_results_dataframe(results['duplicate_records']))
        else:
            st.success("✅ No duplicate internal links found!")

    with tab3:
        # New anchor text analysis
        enhanced = results.get('enhanced_results', {})
        if enhanced.get('anchor_issues'):
            for issue_type, issues in enhanced['anchor_issues'].items():
                st.subheader(f"⚠️ {issue_type.replace('_', ' ').title()}")
                for issue in issues:
                    with st.expander(f"🔍 {issue['anchor_text']}"):
                        st.write(f"**Used for {issue['unique_destinations']} different destinations**")
                        st.write("**Affected links:**")
                        for link in issue['links']:
                            st.write(f"- {link['source_url']} → {link['url']}")
        else:
            st.success("✅ No anchor text uniqueness issues found!")

    with tab4:
        # Recommendations
        enhanced = results.get('enhanced_results', {})
        if enhanced.get('recommendations'):
            engine = RecommendationEngine()
            action_plan_df = engine.create_action_plan(enhanced['recommendations'])

            st.subheader("🎯 Action Plan")
            st.dataframe(action_plan_df)

            # Export action plan
            st.subheader("💾 Export Action Plan")
            csv_link = get_csv_download_link(action_plan_df, 'seo_action_plan.csv')
            st.markdown(csv_link, unsafe_allow_html=True)
        else:
            st.info("No specific recommendations generated.")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666;">
    <p>Enhanced Internal Link Analyzer - Advanced SEO Tool</p>
    <p><small>Use responsibly and respect website terms of service</small></p>
</div>
""", unsafe_allow_html=True)