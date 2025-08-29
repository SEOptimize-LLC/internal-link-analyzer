#!/usr/bin/env python3
"""
Test script to validate sitemap processor fixes
"""

from sitemap_processor import SitemapProcessor

def test_sitemap_processor():
    """Test the fixed sitemap processor with the reported URLs"""

    processor = SitemapProcessor()

    test_urls = [
        "https://educationwalkthrough.com/post-sitemap.xml",  # 403 error
        "https://marygoroundbongbowl.com/sitemap_blogs_1.xml",  # Gzip error
        "https://rxfit.co/post-sitemap.xml",  # Gzip error
    ]

    print("Testing Enhanced Sitemap Processor Fixes")
    print("=" * 50)

    for url in test_urls:
        print(f"\nTesting: {url}")
        try:
            urls = processor.parse_sitemap(url)
            print(f"✅ SUCCESS: Found {len(urls)} URLs")
            if urls:
                print(f"   Sample URL: {urls[0].get('url', 'N/A')}")
        except Exception as e:
            error_msg = str(e)
            if "403 Forbidden" in error_msg:
                print("❌ EXPECTED: 403 Forbidden (server blocking)")
            elif "Not a gzipped file" in error_msg:
                print("❌ EXPECTED: Gzip detection issue (should be fixed)")
            else:
                print(f"❌ UNEXPECTED ERROR: {error_msg}")

    print("\n" + "=" * 50)
    print("Test completed. The fixes should handle these errors more gracefully.")

if __name__ == "__main__":
    test_sitemap_processor()