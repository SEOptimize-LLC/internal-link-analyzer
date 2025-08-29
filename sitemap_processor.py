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

            # Try different user agents if we get blocked
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            ]

            content = None
            for i, user_agent in enumerate(user_agents):
                try:
                    headers = {'User-Agent': user_agent}
                    response = requests.get(sitemap_url, headers=headers, timeout=30)
                    response.raise_for_status()
                    content = response.content
                    break
                except requests.HTTPError as e:
                    if e.response.status_code == 403 and i < len(user_agents) - 1:
                        print(f"403 error with user agent {i+1}, trying next...")
                        continue
                    else:
                        raise e
                except Exception:
                    if i < len(user_agents) - 1:
                        continue
                    else:
                        raise

            if content is None:
                raise Exception("Failed to fetch sitemap with all user agents")

            # Handle compressed sitemaps - improved detection
            try:
                # First try to detect if content is gzipped by attempting decompression
                decompressed_content = gzip.decompress(content)
                print("Content was gzipped, decompressed successfully")
                content = decompressed_content
            except gzip.BadGzipFile:
                # Content is not gzipped, use as-is
                print("Content is not gzipped, using raw content")
                pass
            except Exception as e:
                print(f"Gzip detection failed: {str(e)}, using raw content")
                pass

            # Parse XML
            try:
                root = ET.fromstring(content)
            except ET.ParseError as e:
                # Try to clean the content if parsing fails
                content_str = content.decode('utf-8', errors='ignore')
                # Remove any BOM or invisible characters
                content_str = content_str.lstrip('\ufeff').lstrip()
                try:
                    root = ET.fromstring(content_str.encode('utf-8'))
                except:
                    raise Exception(f"Failed to parse XML content: {str(e)}")

            urls = []
            for url_element in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
                url_data = {}

                loc = url_element.find('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc is not None and loc.text:
                    url_data['url'] = loc.text.strip()

                lastmod = url_element.find('.//{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')
                if lastmod is not None and lastmod.text:
                    url_data['lastmod'] = lastmod.text

                changefreq = url_element.find('.//{http://www.sitemaps.org/schemas/sitemap/0.9}changefreq')
                if changefreq is not None and changefreq.text:
                    url_data['changefreq'] = changefreq.text

                priority = url_element.find('.//{http://www.sitemaps.org/schemas/sitemap/0.9}priority')
                if priority is not None and priority.text:
                    try:
                        url_data['priority'] = float(priority.text)
                    except ValueError:
                        pass

                if url_data.get('url'):  # Only add if we have a valid URL
                    urls.append(url_data)

            print(f"Found {len(urls)} URLs in sitemap")
            return urls

        except requests.HTTPError as e:
            if e.response.status_code == 403:
                raise Exception(f"Sitemap access blocked (403 Forbidden). The website may be blocking automated access. Try using a different user agent or accessing manually.")
            else:
                raise Exception(f"HTTP error {e.response.status_code} for sitemap {sitemap_url}: {e.response.reason}")
        except requests.RequestException as e:
            raise Exception(f"Network error accessing sitemap {sitemap_url}: {str(e)}")
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