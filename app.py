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

st.title("Internal Link Analyzer")
st.markdown("""
This tool analyzes internal hyperlinks on your website URLs to identify duplicate links pointing to the same destination,
which may indicate diluted link equity and potential SEO issues.
""")

# Sidebar configuration
st.sidebar.header("⚙️ Configuration")
max_urls = st.sidebar.slider("Maximum URLs to analyze", min_value=1, max_value=50, value=10)
delay = st.sidebar.slider("Delay between requests (seconds)", min_value=0.5, max_value=5.0, value=1.0, step=0.5)

st.sidebar.header("📋 About")
st.sidebar.info("""
This app analyzes internal links on provided URLs to find duplicates that may dilute link equity.
- Supports manual URL entry and file uploads (CSV/txt)
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

def fetch_page_content(url, timeout=10):
    """Fetch page content with proper headers."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        raise Exception(f"Failed to fetch {url}: {str(e)}")

def extract_links_from_html(html_content, base_url):
    """Extract all hyperlinks from HTML content."""
    soup = BeautifulSoup(html_content, 'lxml')
    links = []

    for a_tag in soup.find_all('a', href=True):
        href = a_tag.get('href')
        anchor_text = a_tag.get_text(strip=True) or '[No Text]'

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
                all_links = extract_links_from_html(html_content, url)

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
    """Find duplicate links pointing to the same destination."""
    from collections import defaultdict

    # Group by destination URL
    destination_groups = defaultdict(list)

    for link in internal_links:
        destination_groups[link['url']].append({
            'source_url': link['source_url'],
            'anchor': link['anchor']
        })

    # Find duplicates (more than one link to same destination)
    duplicates = []
    for dest_url, sources in destination_groups.items():
        if len(sources) > 1:
            duplicates.append({
                'destination_url': dest_url,
                'count': len(sources),
                'sources': sources
            })

    # Sort by count (most duplicates first)
    duplicates.sort(key=lambda x: x['count'], reverse=True)

    return duplicates

def create_results_dataframe(duplicates):
    """Create a pandas DataFrame from duplicates data."""
    if not duplicates:
        return pd.DataFrame(columns=['Destination URL', 'Count', 'Source URLs', 'Anchors'])

    rows = []
    for dup in duplicates:
        source_urls = [s['source_url'] for s in dup['sources']]
        anchors = [s['anchor'] for s in dup['sources']]

        rows.append({
            'Destination URL': dup['destination_url'],
            'Count': dup['count'],
            'Source URLs': ', '.join(source_urls),
            'Anchors': ', '.join(anchors)
        })

    return pd.DataFrame(rows)

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
                st.session_state.urls = valid_urls[:max_urls]  # Limit to max_urls
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
                st.session_state.urls = valid_urls[:max_urls]  # Limit to max_urls
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

                    duplicates = find_duplicate_links(internal_links)
                    results_df = create_results_dataframe(duplicates)

                    st.session_state.results = {
                        'duplicates': duplicates,
                        'dataframe': results_df,
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
        st.metric("Duplicate Destinations", len(results['duplicates']))
    with col3:
        total_duplicates = sum(d['count'] for d in results['duplicates'])
        st.metric("Total Duplicate Links", total_duplicates)

    # Errors
    if results['errors']:
        with st.expander("⚠️ Errors Encountered"):
            for error in results['errors'][:10]:  # Show first 10 errors
                st.write(f"• {error}")
            if len(results['errors']) > 10:
                st.write(f"... and {len(results['errors']) - 10} more errors")

    # Results table
    if not results['dataframe'].empty:
        st.subheader("Duplicate Internal Links")

        # Highlight duplicates
        def highlight_duplicates(row):
            return ['background-color: #ffe6e6' if row['Count'] > 1 else '' for _ in row]

        styled_df = results['dataframe'].style.apply(highlight_duplicates, axis=1)

        st.dataframe(styled_df, use_container_width=True)

        # Export
        st.subheader("💾 Export Results")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**CSV Export:**")
            csv_link = get_csv_download_link(
                results['dataframe'],
                'internal_link_duplicates.csv'
            )
            st.markdown(csv_link, unsafe_allow_html=True)

        with col2:
            st.markdown("**Excel Export:**")
            # For Excel, we'd need openpyxl, but for now just CSV
            st.markdown("Coming soon - use CSV for now")

    else:
        st.success("✅ No duplicate internal links found! All internal links are unique.")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666;">
    <p>Internal Link Analyzer - SEO Tool for identifying diluted link equity</p>
    <p><small>Use responsibly and respect website terms of service</small></p>
</div>
""", unsafe_allow_html=True)

# Global variables for session state
if 'urls' not in st.session_state:
    st.session_state.urls = []
if 'results' not in st.session_state:
    st.session_state.results = None
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False