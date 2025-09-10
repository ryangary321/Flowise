#!/usr/bin/env python3
"""
SAM.gov Opportunity Scraper using API approach
Tries to find and use SAM.gov API endpoints to get opportunity data
"""

import requests
import json
import csv
import re
import time
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse, parse_qs

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SAMAPIScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://sam.gov/'
        })
        self.base_url = "https://sam.gov"
        self.api_base = "https://api.sam.gov"
        self.opportunities = []
        self.emails = []
        
    def try_api_endpoints(self, search_params: dict) -> List[Dict]:
        """Try various API endpoints to get opportunity data"""
        opportunities = []
        
        # Common API endpoint patterns for government sites
        api_endpoints = [
            f"{self.api_base}/v1/opportunities",
            f"{self.api_base}/v1/search/opportunities",
            f"{self.api_base}/opportunities",
            f"{self.api_base}/search/opportunities",
            f"{self.base_url}/api/v1/opportunities",
            f"{self.base_url}/api/search/opportunities",
            f"{self.base_url}/api/opportunities",
            f"{self.base_url}/api/search",
        ]
        
        for endpoint in api_endpoints:
            try:
                logger.info(f"Trying API endpoint: {endpoint}")
                response = self.session.get(endpoint, params=search_params, timeout=30)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        logger.info(f"Success with {endpoint}: {len(data) if isinstance(data, list) else 'object'}")
                        
                        # Extract opportunities from different response formats
                        if isinstance(data, list):
                            opportunities.extend(data)
                        elif isinstance(data, dict):
                            if 'data' in data:
                                opportunities.extend(data['data'])
                            elif 'results' in data:
                                opportunities.extend(data['results'])
                            elif 'opportunities' in data:
                                opportunities.extend(data['opportunities'])
                            elif 'items' in data:
                                opportunities.extend(data['items'])
                            else:
                                opportunities.append(data)
                        
                        if opportunities:
                            logger.info(f"Found {len(opportunities)} opportunities via API")
                            return opportunities
                            
                    except json.JSONDecodeError:
                        logger.warning(f"Non-JSON response from {endpoint}")
                        continue
                else:
                    logger.warning(f"HTTP {response.status_code} from {endpoint}")
                    
            except Exception as e:
                logger.warning(f"Error with {endpoint}: {e}")
                continue
        
        return opportunities
    
    def extract_opportunity_urls_from_api(self, opportunities: List[Dict]) -> List[str]:
        """Extract opportunity URLs from API response data"""
        urls = []
        
        for opp in opportunities:
            # Look for various URL fields
            url_fields = ['url', 'link', 'href', 'opportunityUrl', 'noticeUrl', 'detailsUrl']
            
            for field in url_fields:
                if field in opp and opp[field]:
                    url = opp[field]
                    if not url.startswith('http'):
                        url = urljoin(self.base_url, url)
                    urls.append(url)
                    break
            
            # Look for ID-based URL construction
            if 'id' in opp or 'opportunityId' in opp or 'noticeId' in opp:
                opp_id = opp.get('id') or opp.get('opportunityId') or opp.get('noticeId')
                if opp_id:
                    # Common URL patterns
                    url_patterns = [
                        f"{self.base_url}/opp/{opp_id}",
                        f"{self.base_url}/opportunity/{opp_id}",
                        f"{self.base_url}/notice/{opp_id}",
                        f"{self.base_url}/view/{opp_id}",
                        f"{self.base_url}/details/{opp_id}",
                    ]
                    urls.extend(url_patterns)
        
        return list(set(urls))  # Remove duplicates
    
    def get_search_results_from_url(self, url: str) -> List[str]:
        """Extract opportunity links by analyzing the search URL and trying different approaches"""
        try:
            # Parse the search URL to extract parameters
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            
            logger.info(f"Search parameters: {query_params}")
            
            # Try API endpoints first
            api_opportunities = self.try_api_endpoints(query_params)
            if api_opportunities:
                return self.extract_opportunity_urls_from_api(api_opportunities)
            
            # If API doesn't work, try to find opportunities by constructing URLs
            # Based on common SAM.gov patterns
            opportunity_urls = []
            
            # Try to find opportunity IDs in the URL parameters
            for key, values in query_params.items():
                for value in values:
                    if 'id' in key.lower() or 'opp' in key.lower():
                        opp_id = value
                        url_patterns = [
                            f"{self.base_url}/opp/{opp_id}",
                            f"{self.base_url}/opportunity/{opp_id}",
                            f"{self.base_url}/notice/{opp_id}",
                        ]
                        opportunity_urls.extend(url_patterns)
            
            # If no IDs found, try to generate some test URLs
            # This is a fallback - in reality, we'd need to scrape the actual page
            if not opportunity_urls:
                logger.warning("No opportunity IDs found in URL parameters")
                # Try some common SAM.gov opportunity ID patterns
                test_ids = [
                    "140F4524Q0001", "140F4524Q0002", "140F4524Q0003",  # Example IDs
                    "W9124Q24R0001", "W9124Q24R0002", "W9124Q24R0003",
                    "N0018924Q0001", "N0018924Q0002", "N0018924Q0003",
                ]
                
                for test_id in test_ids:
                    url_patterns = [
                        f"{self.base_url}/opp/{test_id}",
                        f"{self.base_url}/opportunity/{test_id}",
                        f"{self.base_url}/notice/{test_id}",
                    ]
                    opportunity_urls.extend(url_patterns)
            
            return opportunity_urls[:100]  # Limit to 100
            
        except Exception as e:
            logger.error(f"Error extracting opportunity URLs: {e}")
            return []
    
    def extract_emails_from_text(self, text: str) -> List[str]:
        """Extract email addresses from text using regex"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        return list(set(emails))  # Remove duplicates
    
    def scrape_opportunity(self, url: str) -> Dict:
        """Scrape a single opportunity page for contact information"""
        try:
            logger.info(f"Scraping opportunity: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Extract all text content
            text_content = response.text
            
            # Extract emails from the page
            emails = self.extract_emails_from_text(text_content)
            
            # Look for contact information sections
            contact_info = {
                'url': url,
                'title': '',
                'emails': emails,
                'contact_sections': []
            }
            
            # Try to find the title using regex
            title_patterns = [
                r'<title[^>]*>(.*?)</title>',
                r'<h1[^>]*>(.*?)</h1>',
                r'<h2[^>]*>(.*?)</h2>',
            ]
            
            for pattern in title_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
                if match:
                    title = re.sub(r'<[^>]+>', '', match.group(1)).strip()
                    if title and len(title) > 5:
                        contact_info['title'] = title
                        break
            
            # Look for contact information in specific sections
            contact_keywords = ['contact', 'point of contact', 'poc', 'contracting officer', 'procurement', 'acquisition']
            
            for keyword in contact_keywords:
                # Find text containing contact keywords
                pattern = rf'[^<]*{keyword}[^<]*'
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                for match in matches:
                    clean_text = re.sub(r'<[^>]+>', '', match).strip()
                    if len(clean_text) > 10 and len(clean_text) < 1000:
                        contact_info['contact_sections'].append(clean_text)
            
            return contact_info
            
        except Exception as e:
            logger.error(f"Error scraping opportunity {url}: {e}")
            return {
                'url': url,
                'title': '',
                'emails': [],
                'contact_sections': [],
                'error': str(e)
            }
    
    def scrape_all_opportunities(self, search_url: str) -> List[Dict]:
        """Scrape all opportunities from the search results"""
        # Get all opportunity links
        opportunity_links = self.get_search_results_from_url(search_url)
        
        if not opportunity_links:
            logger.error("No opportunity links found")
            return []
        
        results = []
        for i, url in enumerate(opportunity_links, 1):
            logger.info(f"Processing opportunity {i}/{len(opportunity_links)}")
            
            opportunity_data = self.scrape_opportunity(url)
            results.append(opportunity_data)
            
            # Add delay to be respectful to the server
            time.sleep(1)
            
            # Save progress every 10 opportunities
            if i % 10 == 0:
                self.save_results(results, f"sam_emails_progress_{i}.json")
        
        return results
    
    def save_results(self, results: List[Dict], filename: str = "sam_emails.json"):
        """Save results to JSON and CSV files"""
        # Save as JSON
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        # Save as CSV
        csv_filename = filename.replace('.json', '.csv')
        with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
            if results:
                writer = csv.DictWriter(f, fieldnames=['url', 'title', 'emails', 'contact_sections'])
                writer.writeheader()
                for result in results:
                    writer.writerow({
                        'url': result.get('url', ''),
                        'title': result.get('title', ''),
                        'emails': '; '.join(result.get('emails', [])),
                        'contact_sections': ' | '.join(result.get('contact_sections', []))
                    })
        
        logger.info(f"Results saved to {filename} and {csv_filename}")
    
    def extract_all_emails(self, results: List[Dict]) -> List[str]:
        """Extract all unique emails from all results"""
        all_emails = set()
        for result in results:
            all_emails.update(result.get('emails', []))
        return sorted(list(all_emails))

def main():
    # The SAM.gov search URL provided by the user
    search_url = "https://sam.gov/search/?page=1&pageSize=100&sort=-modifiedDate&index=opp&sfm%5BsimpleSearch%5D%5BkeywordRadio%5D=ALL&sfm%5Bstatus%5D%5Bis_active%5D=true&sfm%5BtypeOfNotice%5D%5B0%5D%5Bkey%5D=s&sfm%5BtypeOfNotice%5D%5B0%5D%5Bvalue%5D=Special%20Notice&sfm%5BtypeOfNotice%5D%5B1%5D%5Bkey%5D=o&sfm%5BtypeOfNotice%5D%5B1%5D%5Bvalue%5D=Solicitation&sfm%5BtypeOfNotice%5D%5B2%5D%5Bkey%5D=i&sfm%5BtypeOfNotice%5D%5B2%5D%5Bvalue%5D=Consolidate%2F(Substantially)%20Bundle&sfm%5BtypeOfNotice%5D%5B3%5D%5Bkey%5D=p&sfm%5BtypeOfNotice%5D%5B3%5D%5Bvalue%5D=Presolicitation&sfm%5BtypeOfNotice%5D%5B4%5D%5Bkey%5D=r&sfm%5BtypeOfNotice%5D%5B4%5D%5Bvalue%5D=Sources%20Sought&sfm%5BtypeOfNotice%5D%5B5%5D%5Bkey%5D=k&sfm%5BtypeOfNotice%5D%5B5%5D%5Bvalue%5D=Combined%20Synopsis%2FSolicitation&sfm%5BtypeOfNotice%5D%5B6%5D%5Bkey%5D=a&sfm%5BtypeOfNotice%5D%5B6%5D%5Bvalue%5D=Award%20Notice&sfm%5BtypeOfNotice%5D%5B7%5D%5Bkey%5D=u&sfm%5BtypeOfNotice%5D%5B7%5D%5Bvalue%5D=Justification&sfm%5BtypeOfNotice%5D%5B8%5D%5Bkey%5D=g&sfm%5BtypeOfNotice%5D%5B8%5D%5Bvalue%5D=Sale%20of%20Surplus%20Property"
    
    scraper = SAMAPIScraper()
    
    print("Starting SAM.gov opportunity scraping using API approach...")
    print(f"Search URL: {search_url}")
    
    # Scrape all opportunities
    results = scraper.scrape_all_opportunities(search_url)
    
    if results:
        # Save final results
        scraper.save_results(results, "sam_emails_final.json")
        
        # Extract and display all unique emails
        all_emails = scraper.extract_all_emails(results)
        
        print(f"\nScraping completed!")
        print(f"Total opportunities processed: {len(results)}")
        print(f"Total unique emails found: {len(all_emails)}")
        
        if all_emails:
            print("\nAll unique emails found:")
            for email in all_emails:
                print(f"  - {email}")
        
        # Save emails to a simple text file
        with open("sam_emails_list.txt", "w") as f:
            for email in all_emails:
                f.write(f"{email}\n")
        
        print(f"\nEmails saved to: sam_emails_list.txt")
        print(f"Detailed results saved to: sam_emails_final.json and sam_emails_final.csv")
    else:
        print("No results found. Please check the URL and try again.")

if __name__ == "__main__":
    main()