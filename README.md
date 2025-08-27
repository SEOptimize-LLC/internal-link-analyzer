# Internal Link Analyzer

A Streamlit web application that analyzes internal hyperlinks on websites to identify duplicate links pointing to the same destination, helping identify potential SEO issues related to diluted link equity.

## Features

- **URL Input Options**: Manual entry or file upload (CSV/txt)
- **Domain-Aware Analysis**: Analyzes each domain separately for accurate internal link detection
- **Robots.txt Compliance**: Automatically checks and respects robots.txt files
- **Duplicate Detection**: Identifies multiple internal links pointing to the same destination
- **SEO Insights**: Highlights potential link equity dilution issues
- **Export Functionality**: Download results as CSV files
- **Error Handling**: Comprehensive error handling for network issues and invalid URLs
- **Progress Tracking**: Real-time progress indicators during analysis
- **Performance Optimized**: Rate limiting, caching, and timeout handling for Streamlit Cloud

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

## Configuration Options

- **Maximum URLs**: Limit the number of URLs to analyze (default: 10)
- **Request Delay**: Delay between requests to respect server load (default: 1 second)

## Web Scraping Ethics

This tool is designed with responsible web scraping in mind:
- Only analyzes websites you own or have permission to crawl
- Respects robots.txt files
- Uses reasonable delays between requests
- Includes proper user-agent headers
- Limited to internal link analysis only

## Output Format

The analysis produces a CSV file with the following columns:
- **Destination URL**: The URL that multiple links point to
- **Count**: Number of duplicate links found
- **Source URLs**: Comma-separated list of source page URLs
- **Anchors**: Comma-separated list of anchor texts used

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