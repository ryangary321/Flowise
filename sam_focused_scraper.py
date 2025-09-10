#!/usr/bin/env python3
"""
SAM.gov Focused Opportunity Scraper
Focused approach to find actual opportunity URLs from SAM.gov
"""

import requests
import json
import csv
import re
import time
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SAMFocusedScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.base_url = "https://sam.gov"
        self.opportunities = []
        self.emails = []
        
    def find_opportunity_urls_from_search(self, search_url: str) -> List[str]:
        """Try to find opportunity URLs by examining the search page more carefully"""
        try:
            logger.info(f"Loading search page: {search_url}")
            response = self.session.get(search_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for any data attributes or hidden fields that might contain opportunity IDs
            opportunity_urls = []
            
            # Look for data attributes
            data_elements = soup.find_all(attrs={'data-opportunity-id': True})
            for elem in data_elements:
                opp_id = elem.get('data-opportunity-id')
                if opp_id:
                    url = f"{self.base_url}/opp/{opp_id}"
                    opportunity_urls.append(url)
                    logger.info(f"Found opportunity ID from data attribute: {opp_id}")
            
            # Look for any script tags that might contain opportunity data
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string:
                    # Look for opportunity IDs in JavaScript
                    opp_id_patterns = [
                        r'opportunityId["\']?\s*:\s*["\']([^"\']+)["\']',
                        r'oppId["\']?\s*:\s*["\']([^"\']+)["\']',
                        r'noticeId["\']?\s*:\s*["\']([^"\']+)["\']',
                        r'id["\']?\s*:\s*["\']([A-Z0-9]+)["\']',
                    ]
                    
                    for pattern in opp_id_patterns:
                        matches = re.findall(pattern, script.string)
                        for match in matches:
                            if len(match) > 5:  # Reasonable ID length
                                url = f"{self.base_url}/opp/{match}"
                                opportunity_urls.append(url)
                                logger.info(f"Found opportunity ID from script: {match}")
            
            # Look for any links that might be opportunities
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href')
                if href and ('opp' in href.lower() or 'opportunity' in href.lower()):
                    full_url = urljoin(self.base_url, href)
                    opportunity_urls.append(full_url)
                    logger.info(f"Found opportunity link: {full_url}")
            
            # Look for any form data or hidden inputs
            forms = soup.find_all('form')
            for form in forms:
                inputs = form.find_all('input', type='hidden')
                for input_elem in inputs:
                    name = input_elem.get('name', '')
                    value = input_elem.get('value', '')
                    if 'opp' in name.lower() or 'opportunity' in name.lower():
                        if value and len(value) > 5:
                            url = f"{self.base_url}/opp/{value}"
                            opportunity_urls.append(url)
                            logger.info(f"Found opportunity ID from form: {value}")
            
            # Look for any JSON data in the page
            json_pattern = r'\{[^{}]*"opportunityId"[^{}]*\}'
            page_text = response.text
            json_matches = re.findall(json_pattern, page_text)
            for json_str in json_matches:
                try:
                    data = json.loads(json_str)
                    if 'opportunityId' in data:
                        opp_id = data['opportunityId']
                        url = f"{self.base_url}/opp/{opp_id}"
                        opportunity_urls.append(url)
                        logger.info(f"Found opportunity ID from JSON: {opp_id}")
                except json.JSONDecodeError:
                    continue
            
            # Remove duplicates
            opportunity_urls = list(set(opportunity_urls))
            logger.info(f"Found {len(opportunity_urls)} opportunity URLs")
            
            return opportunity_urls
            
        except Exception as e:
            logger.error(f"Error finding opportunity URLs: {e}")
            return []
    
    def try_real_opportunity_ids(self) -> List[str]:
        """Try some real-looking opportunity IDs based on common patterns"""
        opportunity_urls = []
        
        # These are more realistic opportunity ID patterns
        # Based on actual SAM.gov opportunity ID formats
        real_looking_ids = [
            '140F4524Q0001', '140F4524Q0002', '140F4524Q0003', '140F4524Q0004', '140F4524Q0005',
            'W9124Q24R0001', 'W9124Q24R0002', 'W9124Q24R0003', 'W9124Q24R0004', 'W9124Q24R0005',
            'N0018924Q0001', 'N0018924Q0002', 'N0018924Q0003', 'N0018924Q0004', 'N0018924Q0005',
            'W91CRQ24R0001', 'W91CRQ24R0002', 'W91CRQ24R0003', 'W91CRQ24R0004', 'W91CRQ24R0005',
            'W912DY24R0001', 'W912DY24R0002', 'W912DY24R0003', 'W912DY24R0004', 'W912DY24R0005',
            'W9124Q24S0001', 'W9124Q24S0002', 'W9124Q24S0003', 'W9124Q24S0004', 'W9124Q24S0005',
            'W9124Q24T0001', 'W9124Q24T0002', 'W9124Q24T0003', 'W9124Q24T0004', 'W9124Q24T0005',
            'W9124Q24U0001', 'W9124Q24U0002', 'W9124Q24U0003', 'W9124Q24U0004', 'W9124Q24U0005',
            'W9124Q24V0001', 'W9124Q24V0002', 'W9124Q24V0003', 'W9124Q24V0004', 'W9124Q24V0005',
            'W9124Q24W0001', 'W9124Q24W0002', 'W9124Q24W0003', 'W9124Q24W0004', 'W9124Q24W0005',
            'W9124Q24X0001', 'W9124Q24X0002', 'W9124Q24X0003', 'W9124Q24X0004', 'W9124Q24X0005',
            'W9124Q24Y0001', 'W9124Q24Y0002', 'W9124Q24Y0003', 'W9124Q24Y0004', 'W9124Q24Y0005',
            'W9124Q24Z0001', 'W9124Q24Z0002', 'W9124Q24Z0003', 'W9124Q24Z0004', 'W9124Q24Z0005',
            'W9125Q24R0001', 'W9125Q24R0002', 'W9125Q24R0003', 'W9125Q24R0004', 'W9125Q24R0005',
            'W9126Q24R0001', 'W9126Q24R0002', 'W9126Q24R0003', 'W9126Q24R0004', 'W9126Q24R0005',
            'W9127Q24R0001', 'W9127Q24R0002', 'W9127Q24R0003', 'W9127Q24R0004', 'W9127Q24R0005',
            'W9128Q24R0001', 'W9128Q24R0002', 'W9128Q24R0003', 'W9128Q24R0004', 'W9128Q24R0005',
            'W9129Q24R0001', 'W9129Q24R0002', 'W9129Q24R0003', 'W9129Q24R0004', 'W9129Q24R0005',
            'W9130Q24R0001', 'W9130Q24R0002', 'W9130Q24R0003', 'W9130Q24R0004', 'W9130Q24R0005',
        ]
        
        for opp_id in real_looking_ids:
            url = f"{self.base_url}/opp/{opp_id}"
            opportunity_urls.append(url)
        
        logger.info(f"Generated {len(opportunity_urls)} realistic opportunity URLs")
        return opportunity_urls
    
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
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract all text content
            text_content = soup.get_text()
            
            # Extract emails from the page
            emails = self.extract_emails_from_text(text_content)
            
            # Look for contact information sections
            contact_info = {
                'url': url,
                'title': '',
                'emails': emails,
                'contact_sections': []
            }
            
            # Try to find the title
            title_selectors = ['h1', 'h2', '.title', '.opportunity-title', '[data-testid="title"]', '.page-title']
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    contact_info['title'] = title_elem.get_text().strip()
                    break
            
            # Look for contact information in specific sections
            contact_keywords = ['contact', 'point of contact', 'poc', 'contracting officer', 'procurement', 'acquisition']
            
            for keyword in contact_keywords:
                # Find elements containing contact keywords
                contact_elements = soup.find_all(text=re.compile(keyword, re.IGNORECASE))
                for elem in contact_elements:
                    parent = elem.parent
                    if parent:
                        contact_text = parent.get_text().strip()
                        if len(contact_text) > 10 and len(contact_text) < 1000:
                            contact_info['contact_sections'].append(contact_text)
            
            # Also look for specific contact divs/sections
            contact_divs = soup.find_all(['div', 'section', 'p'], 
                                      text=re.compile('contact|email|phone', re.IGNORECASE))
            
            for div in contact_divs:
                contact_text = div.get_text().strip()
                if len(contact_text) > 10 and len(contact_text) < 1000:
                    contact_info['contact_sections'].append(contact_text)
            
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
        # First try to find actual opportunity URLs
        opportunity_links = self.find_opportunity_urls_from_search(search_url)
        
        # If no URLs found, try realistic patterns
        if not opportunity_links:
            logger.warning("No opportunity URLs found from search page, trying realistic patterns")
            opportunity_links = self.try_real_opportunity_ids()
        
        if not opportunity_links:
            logger.error("No opportunity links found")
            return []
        
        # Limit to first 20 for testing
        opportunity_links = opportunity_links[:20]
        logger.info(f"Processing {len(opportunity_links)} opportunity URLs")
        
        results = []
        for i, url in enumerate(opportunity_links, 1):
            logger.info(f"Processing opportunity {i}/{len(opportunity_links)}")
            
            opportunity_data = self.scrape_opportunity(url)
            results.append(opportunity_data)
            
            # Add delay to be respectful to the server
            time.sleep(2)
            
            # Save progress every 5 opportunities
            if i % 5 == 0:
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
    
    scraper = SAMFocusedScraper()
    
    print("Starting SAM.gov opportunity scraping using focused approach...")
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