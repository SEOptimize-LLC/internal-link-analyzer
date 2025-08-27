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

# Page configuration
st.set_page_config(
    page_title="Internal Link Analyzer",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state variables at the start
if 'urls' not in st.session_state:
    st.session_state.urls = []
if 'results' not in st.session_state:
    st.session_state.results = None
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False

st.title("Internal Link Analyzer")
st.markdown("""
This tool analyzes internal hyperlinks on your website URLs to identify **duplicate links on the same page** pointing to identical destinations.
This helps identify genuine SEO issues where multiple links to the same URL from one page dilute link equity.
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

# Sidebar configuration (now informational)
st.sidebar.header("⚙️ Analysis Configuration")

# This will be populated dynamically based on loaded URLs
if 'config' not in st.session_state:
    st.session_state.config = None

if st.session_state.config:
    config = st.session_state.config
    st.sidebar.success(f"📊 **{config['description']}**")
    st.sidebar.info(f"⏱️ **Estimated time:** {config['estimated_time']}")
    st.sidebar.info(f"⏳ **Delay between requests:** {config['delay']}s")
    st.sidebar.info(f"🎯 **Strategy:** {config['strategy'].title()}")

    if config['strategy'] == 'thorough':
        st.sidebar.warning(
            "⚠️ Large dataset detected. Analysis will take longer but be more thorough."
        )
else:
    st.sidebar.info("📝 Load your URLs to see automatic configuration.")

st.sidebar.header("📋 About")
st.sidebar.info("""
This app analyzes internal links on provided URLs to find duplicates that may dilute link equity.
- Supports manual URL entry and file uploads (CSV/txt)
- Handles large datasets (up to 1000 URLs)
- Respects robots.txt files
- Identifies duplicate internal links with source anchors
- Exports results to CSV
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

def fetch_page_content(url, timeout=15, max_retries=3):
    """Fetch page content with proper headers and retry logic."""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]

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
            }

            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.text

        except requests.HTTPError as e:
            if e.response.status_code == 403 and attempt < max_retries - 1:
                # Wait before retry with different user agent
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                raise Exception(f"HTTP {e.response.status_code} for {url}: {e.response.reason}")

        except requests.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            else:
                raise Exception(f"Failed to fetch {url} after {max_retries} attempts: {str(e)}")

    raise Exception(f"Failed to fetch {url} after {max_retries} attempts")

def extract_main_content_links(html_content, base_url):
    """Extract hyperlinks only from main content area, excluding navigation, footer, etc."""
    soup = BeautifulSoup(html_content, 'lxml')
    links = []

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

    # Try to find main content areas
    content_selectors = [
        'article', '.post-content', '.entry-content', '.content',
        'main', '.main-content', '.article-content',
        '.post', '.entry', '.single-post',
        '.blog-post', '.article-body', '.post-body',
        '[role="main"]', '.main'
    ]

    main_content = None

    # Try to find main content container
    for selector in content_selectors:
        main_content = soup.select_one(selector)
        if main_content:
            break

    # If no main content found, use body but filter out common non-content elements
    if not main_content:
        main_content = soup.find('body')
        if main_content:
            # Remove script and style elements
            for script in main_content.find_all(['script', 'style']):
                script.decompose()

    if main_content:
        # Extract links from main content only
        for a_tag in main_content.find_all('a', href=True):
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

def analyze_internal_links(urls, progress_callback=None):
    """Main analysis function."""
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
                html_content = fetch_page_content(url)

                # Extract all links
                all_links = extract_main_content_links(html_content, url)

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
                    progress_callback(progress, f"Processed {processed}/{total_urls} URLs")

                # Rate limiting
                time.sleep(delay)

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

tab1, tab2 = st.tabs(["Manual Entry", "File Upload"])

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
                st.warning(f"Invalid URLs found and skipped: {', '.join(invalid_urls[:5])}" +
                          (f" and {len(invalid_urls)-5} more" if len(invalid_urls) > 5 else ""))

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
                st.warning(f"Invalid URLs found and skipped: {', '.join(invalid_urls[:5])}" +
                          (f" and {len(invalid_urls)-5} more" if len(invalid_urls) > 5 else ""))

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
                    internal_links, errors = analyze_internal_links(
                        st.session_state.urls,
                        progress_callback
                    )

                    duplicate_records = find_duplicate_links(internal_links)
                    results_df = create_results_dataframe(duplicate_records)
                    horizontal_df = create_horizontal_dataframe(duplicate_records)

                    st.session_state.results = {
                        'duplicate_records': duplicate_records,
                        'dataframe': results_df,
                        'horizontal_dataframe': horizontal_df,
                        'total_links': len(internal_links),
                        'errors': errors
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

    st.header("📊 Results")

    # Summary
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Internal Links Found", results['total_links'])
    with col2:
        # Count unique target URLs that have duplicate links
        unique_targets = len(set(record['target_url'] for record in results['duplicate_records']))
        st.metric("Pages with Duplicate Links", unique_targets)
    with col3:
        st.metric("Total Duplicate Link Instances", len(results['duplicate_records']))

    # Errors
    if results['errors']:
        with st.expander("⚠️ Errors Encountered"):
            for error in results['errors'][:10]:  # Show first 10 errors
                st.write(f"• {error}")
            if len(results['errors']) > 10:
                st.write(f"... and {len(results['errors']) - 10} more errors")

    # Results table
    if 'horizontal_dataframe' in results and not results['horizontal_dataframe'].empty:
        st.subheader("Duplicate Internal Links")
        st.markdown("*Each row shows a target URL with all its duplicate links horizontally*")

        # Display the horizontal dataframe
        st.dataframe(results['horizontal_dataframe'], use_container_width=True)

        # Export
        st.subheader("💾 Export Results")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**CSV Export:**")
            csv_link = get_csv_download_link(
                results['horizontal_dataframe'],
                'duplicate_internal_links.csv'
            )
            st.markdown(csv_link, unsafe_allow_html=True)

        with col2:
            st.markdown("**Excel Export:**")
            # For Excel, we'd need openpyxl, but for now just CSV
            st.markdown("Coming soon - use CSV for now")
else:
    st.success("✅ No duplicate internal links found! Each internal link is unique.")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666;">
    <p>Internal Link Analyzer - SEO Tool for identifying diluted link equity</p>
    <p><small>Use responsibly and respect website terms of service</small></p>
</div>
""", unsafe_allow_html=True)