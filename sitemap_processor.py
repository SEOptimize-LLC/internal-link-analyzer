import xml.etree.ElementTree as ET
import requests
from typing import List, Dict
import gzip

class SitemapProcessor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Enhanced Internal Link Analyzer/2.0 '
            '(+https://example.com/bot)'
        })

    def parse_sitemap(self, sitemap_url: str) -> List[Dict]:
        """Parse XML sitemap and return list of URLs with metadata"""
        try:
            print(f"Fetching sitemap: {sitemap_url}")
            response = self.session.get(sitemap_url, timeout=30)
            response.raise_for_status()

            # Handle compressed sitemaps
            if sitemap_url.endswith('.gz') or 'gzip' in response.headers.get('content-encoding', ''):
                content = gzip.decompress(response.content)
            else:
                content = response.content

            # Parse XML
            root = ET.fromstring(content)

            urls = []
            for url_element in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
                url_data = {}

                loc = url_element.find('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc is not None:
                    url_data['url'] = loc.text.strip()

                lastmod = url_element.find('.//{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')
                if lastmod is not None:
                    url_data['lastmod'] = lastmod.text

                changefreq = url_element.find('.//{http://www.sitemaps.org/schemas/sitemap/0.9}changefreq')
                if changefreq is not None:
                    url_data['changefreq'] = changefreq.text

                priority = url_element.find('.//{http://www.sitemaps.org/schemas/sitemap/0.9}priority')
                if priority is not None:
                    url_data['priority'] = float(priority.text)

                urls.append(url_data)

            print(f"Found {len(urls)} URLs in sitemap")
            return urls

        except Exception as e:
            print(f"Error parsing sitemap {sitemap_url}: {str(e)}")
            raise Exception(f"Failed to parse sitemap {sitemap_url}: {str(e)}")

    def parse_sitemap_index(self, index_url: str) -> List[str]:
        """Parse sitemap index and return list of sitemap URLs"""
        try:
            print(f"Fetching sitemap index: {index_url}")
            response = self.session.get(index_url, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.content)

            sitemap_urls = []
            for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
                loc = sitemap.find('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc is not None:
                    sitemap_urls.append(loc.text.strip())

            print(f"Found {len(sitemap_urls)} sitemaps in index")
            return sitemap_urls

        except Exception as e:
            print(f"Error parsing sitemap index {index_url}: {str(e)}")
            raise Exception(f"Failed to parse sitemap index {index_url}: {str(e)}")

    def discover_sitemaps(self, domain: str) -> List[str]:
        """Auto-discover sitemaps from robots.txt and common locations"""
        sitemap_urls = []

        # Check robots.txt
        robots_url = f"https://{domain}/robots.txt"
        try:
            print(f"Checking robots.txt: {robots_url}")
            response = self.session.get(robots_url, timeout=10)
            if response.status_code == 200:
                for line in response.text.split('\n'):
                    line = line.strip()
                    if line.lower().startswith('sitemap:'):
                        sitemap_url = line.split(':', 1)[1].strip()
                        sitemap_urls.append(sitemap_url)
                        print(f"Found sitemap in robots.txt: {sitemap_url}")
        except Exception as e:
            print(f"Could not access robots.txt: {str(e)}")

        # Check common sitemap locations
        common_paths = [
            '/sitemap.xml',
            '/sitemap_index.xml',
            '/sitemap.php',
            '/sitemap.txt',
            '/sitemap.xml.gz'
        ]

        for path in common_paths:
            sitemap_url = f"https://{domain}{path}"
            try:
                print(f"Checking common location: {sitemap_url}")
                response = self.session.head(sitemap_url, timeout=5)
                if response.status_code == 200:
                    sitemap_urls.append(sitemap_url)
                    print(f"Found sitemap at common location: {sitemap_url}")
                    break  # Stop after finding the first one
            except:
                continue

        return list(set(sitemap_urls))  # Remove duplicates

    def extract_urls_from_sitemaps(self, domain: str) -> List[str]:
        """Extract all URLs from discovered sitemaps"""
        all_urls = []

        sitemap_urls = self.discover_sitemaps(domain)

        if not sitemap_urls:
            print(f"No sitemaps found for domain: {domain}")
            return []

        for sitemap_url in sitemap_urls:
            try:
                print(f"Processing sitemap: {sitemap_url}")
                # Check if it's a sitemap index
                response = self.session.get(sitemap_url, timeout=10)
                content = response.content.decode('utf-8', errors='ignore')

                if '<sitemapindex' in content:
                    # It's a sitemap index
                    print("Detected sitemap index, processing child sitemaps...")
                    index_sitemaps = self.parse_sitemap_index(sitemap_url)
                    for index_sitemap in index_sitemaps:
                        try:
                            urls_data = self.parse_sitemap(index_sitemap)
                            urls = [item['url'] for item in urls_data if 'url' in item]
                            all_urls.extend(urls)
                            print(f"Added {len(urls)} URLs from {index_sitemap}")
                        except Exception as e:
                            print(f"Error processing sitemap {index_sitemap}: {str(e)}")
                            continue
                else:
                    # It's a regular sitemap
                    urls_data = self.parse_sitemap(sitemap_url)
                    urls = [item['url'] for item in urls_data if 'url' in item]
                    all_urls.extend(urls)
                    print(f"Added {len(urls)} URLs from {sitemap_url}")

            except Exception as e:
                print(f"Error processing sitemap {sitemap_url}: {str(e)}")
                continue

        # Remove duplicates and filter out non-HTML URLs if needed
        unique_urls = list(set(all_urls))
        print(f"Total unique URLs extracted: {len(unique_urls)}")
        return unique_urls

    def validate_sitemap_url(self, url: str) -> bool:
        """Validate if a URL is a valid sitemap"""
        try:
            response = self.session.head(url, timeout=10)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                return 'xml' in content_type or 'text' in content_type
            return False
        except:
            return False