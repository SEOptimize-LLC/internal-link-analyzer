# Internal Link Analyzer

A comprehensive Streamlit application for analyzing internal link structure of websites. This tool helps identify SEO issues and optimization opportunities in your website's internal linking.

## Features

### Core Analysis
- **Duplicate Link Detection**: Identifies multiple links from the same source to the same destination
- **Duplicate Anchor Text Analysis**: Finds duplicate anchor texts linking to same or different URLs
- **Orphaned Pages**: Discovers pages with no internal links pointing to them
- **Click Depth Calculation**: Measures how many clicks pages are from the homepage
- **Link Distribution Analysis**: Analyzes the balance of inbound/outbound links
- **Broken Link Detection**: Identifies 404s and other HTTP errors

### Additional Features
- **Sitemap Support**: Parse XML sitemaps including nested sitemap indexes
- **Concurrent Crawling**: Fast, multi-threaded crawling with configurable workers
- **Interactive Visualizations**: Network graphs, distribution charts, and severity breakdowns
- **Export Options**: Download reports in CSV or JSON format
- **Link Position Analysis**: Distinguishes between navigation, content, footer, and sidebar links
- **Generic Anchor Detection**: Flags non-descriptive anchor texts like "click here"

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/internal-link-analyzer.git
cd internal-link-analyzer