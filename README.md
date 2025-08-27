# Internal Link Analyzer

A Streamlit web application that analyzes internal hyperlinks on websites to identify **duplicate links on the same page** pointing to identical destinations. This helps identify genuine SEO issues where multiple links to the same URL from one page dilute link equity.

## Features

- **URL Input Options**: Manual entry or file upload (CSV/txt)
- **Dynamic Configuration**: Automatically adapts analysis strategy based on dataset size
- **Domain-Aware Analysis**: Analyzes each domain separately for accurate internal link detection
- **Robots.txt Compliance**: Automatically checks and respects robots.txt files
- **Duplicate Detection**: Identifies multiple internal links pointing to the same destination
- **SEO Insights**: Highlights potential link equity dilution issues
- **Export Functionality**: Download results as CSV files
- **Error Handling**: Comprehensive error handling for network issues and invalid URLs
- **Progress Tracking**: Real-time progress indicators during analysis
- **Smart Performance**: Automatic rate limiting and resource optimization

## Installation

1. Clone or download the project files
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Local Development
```bash
streamlit run app.py
```

### Streamlit Cloud Deployment
1. Push code to GitHub
2. Connect to Streamlit Cloud
3. Deploy from your repository

## How It Works

1. **Input URLs**: Enter URLs manually (one per line) or upload a CSV/text file
2. **Domain Grouping**: URLs are grouped by domain for separate analysis
3. **Robots.txt Check**: Each domain's robots.txt is checked for crawling permissions
4. **Web Scraping**: Pages are fetched with proper headers and user-agent
5. **Link Extraction**: All hyperlinks are extracted and normalized
6. **Internal Link Filtering**: Only links within the same domain are considered
7. **Duplicate Analysis**: Links are grouped by destination URL to find duplicates
8. **Results Display**: Duplicate links are displayed with source anchors and counts
9. **Export**: Results can be downloaded as CSV files

## Automatic Configuration

The app automatically adapts its behavior based on your URL list size:

### 📊 **Dynamic Analysis Strategies**

- **Fast Analysis (≤100 URLs)**:
  - 1 second delay between requests
  - Estimated time: < 5 minutes
  - Optimized for quick results

- **Balanced Analysis (101-500 URLs)**:
  - 2 second delay between requests
  - Estimated time: 5-20 minutes
  - Good balance of speed and server respect

- **Thorough Analysis (500+ URLs)**:
  - 3 second delay between requests
  - Estimated time: 20+ minutes
  - Maximum care for server resources

### 🎯 **Smart Features**

- **No Manual Configuration**: The app automatically chooses the best settings
- **Real-time Feedback**: See exactly what strategy will be used before analysis
- **Server Protection**: Automatically increases delays for large datasets
- **Performance Warnings**: Alerts for very large analyses

## Error Handling & Resilience

The app includes robust error handling for common web scraping issues:

- **403 Forbidden Errors**: Automatic retry with different user agents and exponential backoff
- **Network Timeouts**: Configurable timeout handling with retry logic
- **Robots.txt Blocking**: Respects website crawling restrictions
- **Invalid URLs**: Graceful handling of malformed or unreachable URLs

## Web Scraping Ethics

This tool is designed with responsible web scraping in mind:
- Only analyzes websites you own or have permission to crawl
- Respects robots.txt files
- Uses reasonable delays between requests
- Includes proper user-agent headers
- Limited to internal link analysis only

## What It Finds

This tool identifies **duplicate internal links on the same page** that point to identical destinations. This is a genuine SEO issue because:

- **Link Equity Dilution**: Multiple links to the same destination from one page split the page's authority
- **User Confusion**: Visitors see multiple ways to reach the same destination
- **Crawler Confusion**: Search engines may interpret this as over-optimization

### Example Output
```
Target URL: https://example.com/blog/seo-tips
├── Destination: https://example.com/services/seo-consultation
│   ├── Anchor: "Get SEO Help"
│   ├── Anchor: "SEO Consultation"
│   └── Anchor: "Contact Our SEO Experts"
└── Destination: https://example.com/blog/keyword-research
    ├── Anchor: "Learn Keyword Research"
    └── Anchor: "Keyword Research Guide"
```

## Output Format

The analysis produces a CSV file with the following columns:
- **Target URL**: The page being analyzed (where duplicate links are found)
- **Destination URL**: Where the duplicate links point to
- **Anchor Text Used**: The anchor text of each duplicate link instance

**Note**: Each row represents an individual duplicate link instance. Multiple rows with the same Target URL + Destination URL indicate the duplicate link problem.

## Content Filtering

The app intelligently filters links to focus on main content only:
- ✅ **Included**: Links from article content, blog post body, main textual content
- ❌ **Excluded**: Navigation menus, footers, sidebars, advertisements, comments, social sharing buttons, breadcrumbs, pagination, and other non-content elements

This ensures the analysis focuses on editorial links that contribute to SEO value rather than navigational or template links.

## Requirements

- Python 3.7+
- Streamlit
- Requests
- BeautifulSoup4
- Pandas
- urllib3
- lxml

## License

This project is provided as-is for educational and legitimate SEO analysis purposes. Users are responsible for complying with website terms of service and applicable laws.

## Disclaimer

This tool is for SEO analysis purposes only. Always ensure you have permission to crawl the websites you analyze. The authors are not responsible for misuse of this tool.