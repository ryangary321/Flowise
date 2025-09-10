#!/usr/bin/env python3
"""
SAM.gov Opportunity Scraper
Extracts contact emails from SAM.gov opportunity listings
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import csv
import json
from urllib.parse import urljoin, urlparse
import logging
from typing import List, Dict, Optional
import random

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SAMScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.base_url = "https://sam.gov"
        self.opportunities = []
        self.emails = []
        
    def get_search_results(self, url: str) -> List[str]:
        """Extract all opportunity links from the search results page"""
        try:
            logger.info(f"Fetching search results from: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Save the raw HTML for debugging
            with open('sam_search_page.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            logger.info("Saved raw HTML to sam_search_page.html for debugging")
            
            soup = BeautifulSoup(response.content, 'html.parser')
            opportunity_links = []
            
            # Look for opportunity links - SAM.gov uses various patterns
            # Try different selectors that might contain the links
            selectors = [
                'a[href*="/opp/"]',
                'a[href*="/opportunity/"]',
                'a[href*="/entity/"]',
                '.search-result a',
                '.opportunity-link',
                'a[href*="oppId="]',
                'a[href*="opportunityId="]',
                'a[href*="noticeId="]',
                'a[href*="notice_id="]',
                'a[href*="id="]',
                'a[href*="view/"]',
                'a[href*="details/"]'
            ]
            
            for selector in selectors:
                links = soup.select(selector)
                logger.info(f"Selector '{selector}' found {len(links)} links")
                for link in links:
                    href = link.get('href')
                    if href and ('opp' in href.lower() or 'opportunity' in href.lower() or 'notice' in href.lower()):
                        full_url = urljoin(self.base_url, href)
                        if full_url not in opportunity_links:
                            opportunity_links.append(full_url)
                            logger.info(f"Found opportunity link: {full_url}")
            
            # Also look for data attributes or other patterns
            data_links = soup.find_all(attrs={'data-opp-id': True})
            for link in data_links:
                opp_id = link.get('data-opp-id')
                if opp_id:
                    full_url = f"{self.base_url}/opp/{opp_id}"
                    if full_url not in opportunity_links:
                        opportunity_links.append(full_url)
                        logger.info(f"Found opportunity link from data attribute: {full_url}")
            
            # Look for any links that might be opportunities
            all_links = soup.find_all('a', href=True)
            logger.info(f"Total links found on page: {len(all_links)}")
            
            for link in all_links[:20]:  # Check first 20 links for debugging
                href = link.get('href')
                text = link.get_text().strip()
                logger.info(f"Link: {href} | Text: {text[:50]}...")
            
            # Try to find any links with opportunity-related text
            opp_text_links = soup.find_all('a', text=re.compile(r'opportunity|solicitation|notice|award', re.IGNORECASE))
            logger.info(f"Found {len(opp_text_links)} links with opportunity-related text")
            
            for link in opp_text_links:
                href = link.get('href')
                if href:
                    full_url = urljoin(self.base_url, href)
                    if full_url not in opportunity_links:
                        opportunity_links.append(full_url)
                        logger.info(f"Found opportunity link from text: {full_url}")
            
            logger.info(f"Found {len(opportunity_links)} opportunity links total")
            return opportunity_links[:100]  # Limit to 100 as requested
            
        except Exception as e:
            logger.error(f"Error fetching search results: {e}")
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
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract all text content
            text_content = soup.get_text()
            
            # Look for contact information sections
            contact_sections = []
            contact_keywords = [
                'contact', 'point of contact', 'poc', 'contracting officer',
                'procurement', 'acquisition', 'email', 'phone', 'address'
            ]
            
            for keyword in contact_keywords:
                sections = soup.find_all(text=re.compile(keyword, re.IGNORECASE))
                contact_sections.extend(sections)
            
            # Extract emails from the page
            emails = self.extract_emails_from_text(text_content)
            
            # Look for specific contact elements
            contact_info = {
                'url': url,
                'title': '',
                'emails': emails,
                'contact_sections': []
            }
            
            # Try to find the title
            title_selectors = ['h1', 'h2', '.title', '.opportunity-title', '[data-testid="title"]']
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    contact_info['title'] = title_elem.get_text().strip()
                    break
            
            # Look for contact information in specific sections
            contact_divs = soup.find_all(['div', 'section', 'p'], 
                                      text=re.compile('contact|email|phone', re.IGNORECASE))
            
            for div in contact_divs:
                contact_text = div.get_text().strip()
                if len(contact_text) > 10 and len(contact_text) < 500:  # Reasonable length
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
        # Get all opportunity links
        opportunity_links = self.get_search_results(search_url)
        
        if not opportunity_links:
            logger.error("No opportunity links found")
            return []
        
        results = []
        for i, url in enumerate(opportunity_links, 1):
            logger.info(f"Processing opportunity {i}/{len(opportunity_links)}")
            
            opportunity_data = self.scrape_opportunity(url)
            results.append(opportunity_data)
            
            # Add delay to be respectful to the server
            delay = random.uniform(1, 3)
            time.sleep(delay)
            
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
    
    scraper = SAMScraper()
    
    print("Starting SAM.gov opportunity scraping...")
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