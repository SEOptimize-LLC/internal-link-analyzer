import streamlit as st
import pandas as pd
import requests
from urllib.parse import urlparse, urljoin, unquote
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
from bs4 import BeautifulSoup
import time
import json
import csv
from io import StringIO, BytesIO
import networkx as nx
from typing import Dict, List, Set, Tuple, Optional
import re
import concurrent.futures
from dataclasses import dataclass, asdict
import hashlib

# Page configuration
st.set_page_config(
    page_title="Internal Link Analyzer",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .stAlert {
        margin-top: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .issue-critical {
        background-color: #ff4b4b;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
    }
    .issue-high {
        background-color: #ffa500;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
    }
    .issue-medium {
        background-color: #ffee58;
        color: black;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
    }
    .issue-low {
        background-color: #4caf50;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
    }
    </style>
    """, unsafe_allow_html=True)

@dataclass
class Link:
    """Data class for storing link information"""
    source_url: str
    destination_url: str
    anchor_text: str
    position: str = "content"
    attributes: Dict = None
    
    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}

@dataclass
class PageInfo:
    """Data class for storing page information"""
    url: str
    title: str = ""
    status_code: int = 0
    response_time: float = 0.0
    inbound_links: int = 0
    outbound_links: int = 0
    click_depth: int = -1

class InternalLinkAnalyzer:
    """Main analyzer class for internal link analysis"""
    
    def __init__(self, domain: str, max_workers: int = 5):
        self.domain = self._normalize_domain(domain)
        self.max_workers = max_workers
        self.pages = {}
        self.links = []
        self.crawled_urls = set()
        self.to_crawl = set()
        self.issues = defaultdict(list)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'InternalLinkAnalyzer/1.0 (Streamlit App)'
        })
        
    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain URL"""
        if not domain.startswith(('http://', 'https://')):
            domain = 'https://' + domain
        parsed = urlparse(domain)
        return f"{parsed.scheme}://{parsed.netloc}"
    
    def _normalize_url(self, url: str, base_url: str = None) -> str:
        """Normalize and resolve relative URLs"""
        if base_url:
            url = urljoin(base_url, url)
        
        # Remove fragment
        url = url.split('#')[0]
        
        # Remove trailing slash for consistency
        if url.endswith('/') and url != self.domain + '/':
            url = url[:-1]
            
        # Decode URL-encoded characters
        url = unquote(url)
        
        return url
    
    def _is_internal_url(self, url: str) -> bool:
        """Check if URL is internal to the domain"""
        try:
            parsed = urlparse(url)
            domain_parsed = urlparse(self.domain)
            return parsed.netloc == domain_parsed.netloc
        except:
            return False
    
    def fetch_sitemap_urls(self, sitemap_url: str) -> Set[str]:
        """Fetch all URLs from a sitemap"""
        urls = set()
        
        try:
            response = self.session.get(sitemap_url, timeout=30)
            response.raise_for_status()
            
            # Parse XML
            root = ET.fromstring(response.content)
            
            # Handle sitemap index
            if 'sitemapindex' in root.tag:
                for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                    if sitemap.text:
                        # Recursively fetch URLs from nested sitemaps
                        urls.update(self.fetch_sitemap_urls(sitemap.text))
            else:
                # Regular sitemap
                for url in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                    if url.text:
                        normalized = self._normalize_url(url.text)
                        if self._is_internal_url(normalized):
                            urls.add(normalized)
        except Exception as e:
            st.error(f"Error fetching sitemap: {str(e)}")
            
        return urls
    
    def crawl_page(self, url: str) -> Optional[PageInfo]:
        """Crawl a single page and extract links"""
        if url in self.crawled_urls:
            return None
            
        try:
            start_time = time.time()
            response = self.session.get(url, timeout=30, allow_redirects=True)
            response_time = time.time() - start_time
            
            # Store final URL after redirects
            final_url = self._normalize_url(response.url)
            self.crawled_urls.add(url)
            
            if final_url != url:
                self.crawled_urls.add(final_url)
            
            # Create page info
            page_info = PageInfo(
                url=final_url,
                status_code=response.status_code,
                response_time=response_time
            )
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract title
                title_tag = soup.find('title')
                if title_tag:
                    page_info.title = title_tag.text.strip()
                
                # Extract all links
                for link_tag in soup.find_all('a', href=True):
                    href = link_tag['href']
                    
                    # Skip mailto, tel, and javascript links
                    if href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                        continue
                    
                    # Normalize destination URL
                    dest_url = self._normalize_url(href, final_url)
                    
                    # Only process internal links
                    if self._is_internal_url(dest_url):
                        # Extract anchor text
                        anchor_text = link_tag.get_text(strip=True)
                        if not anchor_text and link_tag.find('img'):
                            # Use alt text for image links
                            img = link_tag.find('img')
                            anchor_text = img.get('alt', '') if img else ''
                        
                        # Determine link position
                        position = self._determine_link_position(link_tag)
                        
                        # Extract attributes
                        attributes = {
                            'rel': link_tag.get('rel', []),
                            'target': link_tag.get('target', ''),
                            'title': link_tag.get('title', '')
                        }
                        
                        # Create link object
                        link = Link(
                            source_url=final_url,
                            destination_url=dest_url,
                            anchor_text=anchor_text,
                            position=position,
                            attributes=attributes
                        )
                        
                        self.links.append(link)
                        
                        # Add to crawl queue if not already crawled
                        if dest_url not in self.crawled_urls:
                            self.to_crawl.add(dest_url)
            
            self.pages[final_url] = page_info
            return page_info
            
        except requests.RequestException as e:
            # Handle broken links
            page_info = PageInfo(url=url, status_code=0)
            self.pages[url] = page_info
            self.issues['broken_links'].append({
                'url': url,
                'error': str(e),
                'severity': 'critical'
            })
            return page_info
        except Exception as e:
            st.error(f"Error crawling {url}: {str(e)}")
            return None
    
    def _determine_link_position(self, link_tag) -> str:
        """Determine the position of a link in the page"""
        # Check ancestors for common structural elements
        for parent in link_tag.parents:
            if parent.name == 'nav':
                return 'navigation'
            elif parent.name == 'header':
                return 'header'
            elif parent.name == 'footer':
                return 'footer'
            elif parent.name == 'aside':
                return 'sidebar'
            elif parent.name in ['article', 'main', 'section']:
                return 'content'
        
        return 'content'
    
    def crawl_urls(self, urls: Set[str], progress_callback=None):
        """Crawl multiple URLs concurrently"""
        urls_to_crawl = list(urls - self.crawled_urls)
        total = len(urls_to_crawl)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {executor.submit(self.crawl_page, url): url for url in urls_to_crawl}
            
            for i, future in enumerate(concurrent.futures.as_completed(future_to_url)):
                if progress_callback:
                    progress_callback(i + 1, total)
                
                # Add a small delay to be respectful
                time.sleep(0.1)
    
    def analyze_duplicate_links(self):
        """Analyze duplicate links from same source to same destination"""
        link_pairs = defaultdict(list)
        
        for link in self.links:
            key = (link.source_url, link.destination_url)
            link_pairs[key].append(link)
        
        for (source, destination), links_list in link_pairs.items():
            if len(links_list) > 1:
                self.issues['duplicate_links'].append({
                    'source_url': source,
                    'destination_url': destination,
                    'count': len(links_list),
                    'anchor_texts': [link.anchor_text for link in links_list],
                    'positions': [link.position for link in links_list],
                    'severity': 'high'
                })
    
    def analyze_duplicate_anchors(self):
        """Analyze duplicate anchor texts"""
        # Group by anchor text
        anchor_groups = defaultdict(list)
        
        for link in self.links:
            if link.anchor_text:  # Skip empty anchors
                anchor_groups[link.anchor_text.lower()].append(link)
        
        for anchor_text, links_list in anchor_groups.items():
            if len(links_list) > 1:
                # Check if they point to the same destination
                destinations = set(link.destination_url for link in links_list)
                
                if len(destinations) == 1:
                    # Same anchor to same destination from different sources
                    self.issues['duplicate_anchors_same_dest'].append({
                        'anchor_text': anchor_text,
                        'destination': list(destinations)[0],
                        'sources': [link.source_url for link in links_list],
                        'count': len(links_list),
                        'severity': 'medium'
                    })
                else:
                    # Same anchor to different destinations
                    self.issues['duplicate_anchors_diff_dest'].append({
                        'anchor_text': anchor_text,
                        'destinations': list(destinations),
                        'count': len(links_list),
                        'severity': 'high'
                    })
        
        # Also check for generic anchor texts
        generic_anchors = ['click here', 'read more', 'learn more', 'here', 'link', 'more']
        for link in self.links:
            if link.anchor_text and link.anchor_text.lower() in generic_anchors:
                self.issues['generic_anchors'].append({
                    'source_url': link.source_url,
                    'destination_url': link.destination_url,
                    'anchor_text': link.anchor_text,
                    'severity': 'low'
                })
    
    def analyze_orphaned_pages(self):
        """Find pages with no internal links pointing to them"""
        # Get all destination URLs
        linked_pages = set(link.destination_url for link in self.links)
        
        # Find pages that were crawled but have no inbound links
        for page_url in self.pages:
            if page_url != self.domain and page_url not in linked_pages:
                self.issues['orphaned_pages'].append({
                    'url': page_url,
                    'title': self.pages[page_url].title,
                    'severity': 'critical'
                })
    
    def calculate_click_depth(self, start_url: str = None):
        """Calculate click depth for all pages using BFS"""
        if not start_url:
            start_url = self.domain
        
        # Build adjacency list
        graph = defaultdict(set)
        for link in self.links:
            graph[link.source_url].add(link.destination_url)
        
        # BFS to calculate depth
        depths = {start_url: 0}
        queue = [start_url]
        visited = {start_url}
        
        while queue:
            current = queue.pop(0)
            current_depth = depths[current]
            
            for neighbor in graph[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    depths[neighbor] = current_depth + 1
                    queue.append(neighbor)
        
        # Update page info with click depth
        for url, depth in depths.items():
            if url in self.pages:
                self.pages[url].click_depth = depth
        
        # Find pages with excessive depth
        for url, depth in depths.items():
            if depth > 3:
                self.issues['excessive_depth'].append({
                    'url': url,
                    'depth': depth,
                    'title': self.pages[url].title if url in self.pages else '',
                    'severity': 'high' if depth > 5 else 'medium'
                })
    
    def analyze_link_distribution(self):
        """Analyze the distribution of inbound and outbound links"""
        # Count inbound and outbound links
        inbound_count = Counter()
        outbound_count = Counter()
        
        for link in self.links:
            outbound_count[link.source_url] += 1
            inbound_count[link.destination_url] += 1
        
        # Update page info
        for url in self.pages:
            self.pages[url].inbound_links = inbound_count.get(url, 0)
            self.pages[url].outbound_links = outbound_count.get(url, 0)
        
        # Find issues
        for url, count in outbound_count.items():
            if count > 100:
                self.issues['excessive_outbound_links'].append({
                    'url': url,
                    'count': count,
                    'severity': 'medium'
                })
        
        for url in self.pages:
            if self.pages[url].outbound_links == 0 and url != self.domain:
                self.issues['no_outbound_links'].append({
                    'url': url,
                    'title': self.pages[url].title,
                    'severity': 'low'
                })
    
    def check_broken_links(self):
        """Identify broken links"""
        for url, page_info in self.pages.items():
            if page_info.status_code >= 400:
                # Find all links pointing to this broken page
                sources = [link.source_url for link in self.links if link.destination_url == url]
                
                self.issues['broken_links'].append({
                    'url': url,
                    'status_code': page_info.status_code,
                    'linked_from': sources,
                    'severity': 'critical'
                })
    
    def generate_report(self) -> Dict:
        """Generate comprehensive analysis report"""
        total_pages = len(self.pages)
        total_links = len(self.links)
        
        # Count issues by severity
        severity_counts = defaultdict(int)
        for issue_type, issues_list in self.issues.items():
            for issue in issues_list:
                severity_counts[issue.get('severity', 'low')] += 1
        
        report = {
            'summary': {
                'domain': self.domain,
                'total_pages': total_pages,
                'total_links': total_links,
                'unique_links': len(set((l.source_url, l.destination_url) for l in self.links)),
                'issues': {
                    'critical': severity_counts['critical'],
                    'high': severity_counts['high'],
                    'medium': severity_counts['medium'],
                    'low': severity_counts['low']
                }
            },
            'issues': dict(self.issues),
            'pages': {url: asdict(info) for url, info in self.pages.items()},
            'timestamp': datetime.now().isoformat()
        }
        
        return report

def create_network_graph(links: List[Link], pages: Dict[str, PageInfo]) -> go.Figure:
    """Create an interactive network graph of internal links"""
    G = nx.DiGraph()
    
    # Add nodes and edges
    for link in links[:500]:  # Limit for performance
        G.add_edge(link.source_url, link.destination_url)
    
    # Calculate layout
    pos = nx.spring_layout(G, k=1, iterations=50)
    
    # Create edge trace
    edge_trace = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_trace.append(go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode='lines',
            line=dict(width=0.5, color='#888'),
            hoverinfo='none'
        ))
    
    # Create node trace
    node_trace = go.Scatter(
        x=[pos[node][0] for node in G.nodes()],
        y=[pos[node][1] for node in G.nodes()],
        mode='markers+text',
        hoverinfo='text',
        marker=dict(
            showscale=True,
            colorscale='YlOrRd',
            size=10,
            colorbar=dict(
                thickness=15,
                title='Click Depth',
                xanchor='left',
                titleside='right'
            )
        )
    )
    
    # Add node properties
    node_colors = []
    node_text = []
    for node in G.nodes():
        if node in pages:
            depth = pages[node].click_depth
            node_colors.append(depth if depth >= 0 else 10)
            node_text.append(f"URL: {node}<br>Depth: {depth}<br>Title: {pages[node].title[:50]}")
        else:
            node_colors.append(0)
            node_text.append(node)
    
    node_trace.marker.color = node_colors
    node_trace.text = node_text
    
    # Create figure
    fig = go.Figure(data=edge_trace + [node_trace],
                    layout=go.Layout(
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=0, l=0, r=0, t=0),
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        height=600
                    ))
    
    return fig

def export_to_csv(report: Dict) -> str:
    """Export report to CSV format"""
    output = StringIO()
    
    # Write summary
    writer = csv.writer(output)
    writer.writerow(['Internal Link Analysis Report'])
    writer.writerow(['Generated', report['timestamp']])
    writer.writerow([])
    
    # Write issues by type
    for issue_type, issues_list in report['issues'].items():
        if issues_list:
            writer.writerow([f'{issue_type.upper().replace("_", " ")}'])
            
            if issue_type == 'duplicate_links':
                writer.writerow(['Source URL', 'Destination URL', 'Count', 'Anchor Texts'])
                for issue in issues_list:
                    writer.writerow([
                        issue['source_url'],
                        issue['destination_url'],
                        issue['count'],
                        ', '.join(issue['anchor_texts'])
                    ])
            
            elif issue_type == 'orphaned_pages':
                writer.writerow(['URL', 'Title'])
                for issue in issues_list:
                    writer.writerow([issue['url'], issue.get('title', '')])
            
            elif issue_type == 'excessive_depth':
                writer.writerow(['URL', 'Depth', 'Title'])
                for issue in issues_list:
                    writer.writerow([issue['url'], issue['depth'], issue.get('title', '')])
            
            writer.writerow([])
    
    return output.getvalue()

# Streamlit App Interface
def main():
    st.title("🔗 Internal Link Analyzer")
    st.markdown("Comprehensive analysis of your website's internal linking structure")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")
        
        input_method = st.radio(
            "Input Method",
            ["Enter URLs", "Sitemap URL"]
        )
        
        if input_method == "Enter URLs":
            urls_input = st.text_area(
                "Enter URLs (one per line)",
                height=200,
                placeholder="https://example.com\nhttps://example.com/page1\nhttps://example.com/page2"
            )
        else:
            sitemap_url = st.text_input(
                "Sitemap URL",
                placeholder="https://example.com/sitemap.xml"
            )
        
        st.subheader("Crawl Settings")
        max_workers = st.slider("Concurrent Requests", 1, 10, 5)
        crawl_limit = st.number_input("Max Pages to Crawl", min_value=10, max_value=1000, value=100)
        
        analyze_btn = st.button("🚀 Start Analysis", type="primary", use_container_width=True)
    
    # Main content area
    if analyze_btn:
        # Validate input
        if input_method == "Enter URLs" and not urls_input:
            st.error("Please enter at least one URL")
            return
        elif input_method == "Sitemap URL" and not sitemap_url:
            st.error("Please enter a sitemap URL")
            return
        
        # Initialize analyzer
        if input_method == "Enter URLs":
            urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
            domain = urls[0] if urls else None
        else:
            domain = urlparse(sitemap_url).scheme + "://" + urlparse(sitemap_url).netloc
        
        if not domain:
            st.error("Could not determine domain")
            return
        
        analyzer = InternalLinkAnalyzer(domain, max_workers)
        
        # Progress tracking
        progress_container = st.container()
        with progress_container:
            st.info("🔍 Starting analysis...")
            progress_bar = st.progress(0)
            status_text = st.empty()
        
        # Fetch URLs to analyze
        if input_method == "Sitemap URL":
            status_text.text("Fetching sitemap...")
            urls = analyzer.fetch_sitemap_urls(sitemap_url)
            if not urls:
                st.error("No URLs found in sitemap")
                return
            st.success(f"Found {len(urls)} URLs in sitemap")
        else:
            urls = set(urls)
        
        # Limit crawl
        urls = set(list(urls)[:crawl_limit])
        
        # Crawl pages
        def update_progress(current, total):
            progress = current / total
            progress_bar.progress(progress)
            status_text.text(f"Crawling pages... {current}/{total}")
        
        analyzer.crawl_urls(urls, update_progress)
        
        # Run analyses
        status_text.text("Analyzing duplicate links...")
        analyzer.analyze_duplicate_links()
        
        status_text.text("Analyzing anchor texts...")
        analyzer.analyze_duplicate_anchors()
        
        status_text.text("Finding orphaned pages...")
        analyzer.analyze_orphaned_pages()
        
        status_text.text("Calculating click depth...")
        analyzer.calculate_click_depth()
        
        status_text.text("Analyzing link distribution...")
        analyzer.analyze_link_distribution()
        
        status_text.text("Checking for broken links...")
        analyzer.check_broken_links()
        
        # Generate report
        report = analyzer.generate_report()
        
        # Clear progress indicators
        progress_container.empty()
        
        # Display results
        st.success("✅ Analysis Complete!")
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Pages Analyzed", report['summary']['total_pages'])
        with col2:
            st.metric("Total Links", report['summary']['total_links'])
        with col3:
            st.metric("Unique Links", report['summary']['unique_links'])
        with col4:
            st.metric("Total Issues", sum(report['summary']['issues'].values()))
        
        # Issue severity breakdown
        st.subheader("📊 Issue Severity Breakdown")
        severity_df = pd.DataFrame([
            {'Severity': 'Critical', 'Count': report['summary']['issues']['critical'], 'Color': '#ff4b4b'},
            {'Severity': 'High', 'Count': report['summary']['issues']['high'], 'Color': '#ffa500'},
            {'Severity': 'Medium', 'Count': report['summary']['issues']['medium'], 'Color': '#ffee58'},
            {'Severity': 'Low', 'Count': report['summary']['issues']['low'], 'Color': '#4caf50'}
        ])
        
        fig_severity = px.bar(
            severity_df, 
            x='Severity', 
            y='Count',
            color='Severity',
            color_discrete_map={
                'Critical': '#ff4b4b',
                'High': '#ffa500',
                'Medium': '#ffee58',
                'Low': '#4caf50'
            }
        )
        st.plotly_chart(fig_severity, use_container_width=True)
        
        # Detailed issues
        st.subheader("🔍 Detailed Issues")
        
        tabs = st.tabs([
            "Duplicate Links",
            "Duplicate Anchors",
            "Orphaned Pages",
            "Click Depth",
            "Link Distribution",
            "Broken Links"
        ])
        
        with tabs[0]:
            if report['issues'].get('duplicate_links'):
                st.warning(f"Found {len(report['issues']['duplicate_links'])} instances of duplicate links")
                
                for issue in report['issues']['duplicate_links'][:10]:
                    with st.expander(f"{issue['source_url'][:50]}... → {issue['destination_url'][:50]}..."):
                        st.write(f"**Count:** {issue['count']}")
                        st.write(f"**Anchor Texts:** {', '.join(issue['anchor_texts'])}")
                        st.write(f"**Positions:** {', '.join(issue['positions'])}")
            else:
                st.success("No duplicate links found!")
        
        with tabs[1]:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Same Anchor → Same Destination")
                if report['issues'].get('duplicate_anchors_same_dest'):
                    for issue in report['issues']['duplicate_anchors_same_dest'][:10]:
                        with st.expander(f"'{issue['anchor_text']}'"):
                            st.write(f"**Destination:** {issue['destination']}")
                            st.write(f"**Used {issue['count']} times from different sources**")
                else:
                    st.success("No issues found!")
            
            with col2:
                st.subheader("Same Anchor → Different Destinations")
                if report['issues'].get('duplicate_anchors_diff_dest'):
                    for issue in report['issues']['duplicate_anchors_diff_dest'][:10]:
                        with st.expander(f"'{issue['anchor_text']}'"):
                            st.write(f"**Used for {issue['count']} different destinations:**")
                            for dest in issue['destinations'][:5]:
                                st.write(f"• {dest}")
                else:
                    st.success("No issues found!")
        
        with tabs[2]:
            if report['issues'].get('orphaned_pages'):
                st.error(f"Found {len(report['issues']['orphaned_pages'])} orphaned pages")
                
                orphaned_df = pd.DataFrame(report['issues']['orphaned_pages'])
                st.dataframe(orphaned_df[['url', 'title']], use_container_width=True)
            else:
                st.success("No orphaned pages found!")
        
        with tabs[3]:
            if report['issues'].get('excessive_depth'):
                st.warning(f"Found {len(report['issues']['excessive_depth'])} pages with excessive click depth")
                
                depth_df = pd.DataFrame(report['issues']['excessive_depth'])
                fig_depth = px.histogram(
                    depth_df,
                    x='depth',
                    nbins=20,
                    title="Click Depth Distribution"
                )
                st.plotly_chart(fig_depth, use_container_width=True)
                
                st.dataframe(
                    depth_df[['url', 'depth', 'title']].sort_values('depth', ascending=False),
                    use_container_width=True
                )
            else:
                st.success("All pages are within acceptable click depth!")
        
        with tabs[4]:
            # Create distribution charts
            pages_df = pd.DataFrame([asdict(page) for page in analyzer.pages.values()])
            
            col1, col2 = st.columns(2)
            with col1:
                fig_inbound = px.histogram(
                    pages_df,
                    x='inbound_links',
                    nbins=30,
                    title="Inbound Links Distribution"
                )
                st.plotly_chart(fig_inbound, use_container_width=True)
            
            with col2:
                fig_outbound = px.histogram(
                    pages_df,
                    x='outbound_links',
                    nbins=30,
                    title="Outbound Links Distribution"
                )
                st.plotly_chart(fig_outbound, use_container_width=True)
            
            if report['issues'].get('excessive_outbound_links'):
                st.warning("Pages with excessive outbound links:")
                for issue in report['issues']['excessive_outbound_links']:
                    st.write(f"• {issue['url']}: {issue['count']} outbound links")
        
        with tabs[5]:
            if report['issues'].get('broken_links'):
                st.error(f"Found {len(report['issues']['broken_links'])} broken links")
                
                for issue in report['issues']['broken_links']:
                    with st.expander(f"{issue['url']} - Status: {issue.get('status_code', 'Error')}"):
                        st.write("**Linked from:**")
                        for source in issue.get('linked_from', [])[:10]:
                            st.write(f"• {source}")
            else:
                st.success("No broken links found!")
        
        # Network visualization
        st.subheader("🕸️ Link Network Visualization")
        if len(analyzer.links) > 0:
            with st.spinner("Generating network graph..."):
                fig_network = create_network_graph(analyzer.links, analyzer.pages)
                st.plotly_chart(fig_network, use_container_width=True)
        
        # Export options
        st.subheader("📥 Export Report")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            csv_data = export_to_csv(report)
            st.download_button(
                label="Download CSV Report",
                data=csv_data,
                file_name=f"link_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        with col2:
            json_data = json.dumps(report, indent=2)
            st.download_button(
                label="Download JSON Report",
                data=json_data,
                file_name=f"link_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        
        with col3:
            # Store report in session state for reference
            st.session_state['last_report'] = report
            st.success("Report saved to session")

if __name__ == "__main__":
    main()