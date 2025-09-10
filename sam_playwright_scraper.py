#!/usr/bin/env python3
"""
SAM.gov Opportunity Scraper with Playwright
Extracts contact emails from SAM.gov opportunity listings using Playwright for JavaScript handling
"""

import time
import re
import csv
import json
import logging
from typing import List, Dict, Optional
import random
from urllib.parse import urljoin, urlparse

# Playwright imports
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SAMPlaywrightScraper:
    def __init__(self):
        self.base_url = "https://sam.gov"
        self.opportunities = []
        self.emails = []
        
    def get_search_results(self, url: str) -> List[str]:
        """Extract all opportunity links from the search results page using Playwright"""
        with sync_playwright() as p:
            try:
                # Launch browser
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                )
                page = context.new_page()
                
                logger.info(f"Loading search results page: {url}")
                page.goto(url, wait_until='networkidle')
                
                # Wait for content to load
                logger.info("Waiting for search results to load...")
                try:
                    # Wait for any opportunity links to appear
                    page.wait_for_selector('a[href*="opp"], a[href*="opportunity"], a[href*="notice"]', timeout=30000)
                except PlaywrightTimeoutError:
                    logger.warning("Timeout waiting for opportunity links, proceeding anyway")
                
                # Additional wait to ensure all content is loaded
                page.wait_for_timeout(5000)
                
                # Save the rendered HTML for debugging
                content = page.content()
                with open('sam_rendered_page.html', 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info("Saved rendered HTML to sam_rendered_page.html for debugging")
                
                opportunity_links = []
                
                # Look for opportunity links with various selectors
                selectors = [
                    'a[href*="/opp/"]',
                    'a[href*="/opportunity/"]',
                    'a[href*="oppId="]',
                    'a[href*="opportunityId="]',
                    'a[href*="noticeId="]',
                    'a[href*="notice_id="]',
                    'a[href*="id="]',
                    'a[href*="view/"]',
                    'a[href*="details/"]',
                    '[data-testid*="opportunity"] a',
                    '[data-testid*="result"] a',
                    '.search-result a',
                    '.opportunity-link',
                    '[class*="result"] a',
                    '[class*="opportunity"] a'
                ]
                
                for selector in selectors:
                    try:
                        links = page.query_selector_all(selector)
                        logger.info(f"Selector '{selector}' found {len(links)} links")
                        for link in links:
                            href = link.get_attribute('href')
                            if href and ('opp' in href.lower() or 'opportunity' in href.lower() or 'notice' in href.lower()):
                                full_url = urljoin(self.base_url, href)
                                if full_url not in opportunity_links:
                                    opportunity_links.append(full_url)
                                    logger.info(f"Found opportunity link: {full_url}")
                    except Exception as e:
                        logger.warning(f"Error with selector {selector}: {e}")
                
                # Also look for any links that might contain opportunity IDs
                all_links = page.query_selector_all('a')
                logger.info(f"Total links found on page: {len(all_links)}")
                
                for link in all_links[:50]:  # Check first 50 links
                    try:
                        href = link.get_attribute('href')
                        text = link.text_content() or ''
                        if href and ('opp' in href.lower() or 'opportunity' in href.lower() or 'notice' in href.lower() or 'solicitation' in text.lower()):
                            full_url = urljoin(self.base_url, href)
                            if full_url not in opportunity_links:
                                opportunity_links.append(full_url)
                                logger.info(f"Found opportunity link from text: {full_url}")
                    except Exception as e:
                        continue
                
                browser.close()
                
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
        with sync_playwright() as p:
            try:
                # Launch browser
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                )
                page = context.new_page()
                
                logger.info(f"Scraping opportunity: {url}")
                page.goto(url, wait_until='networkidle')
                
                # Wait for content to load
                page.wait_for_timeout(3000)
                
                # Extract all text content
                text_content = page.text_content('body')
                
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
                    try:
                        title_elem = page.query_selector(selector)
                        if title_elem:
                            contact_info['title'] = title_elem.text_content().strip()
                            break
                    except Exception:
                        continue
                
                # Look for contact information in specific sections
                contact_keywords = ['contact', 'point of contact', 'poc', 'contracting officer', 'procurement', 'acquisition']
                
                for keyword in contact_keywords:
                    try:
                        # Find elements containing contact keywords
                        elements = page.query_selector_all(f'text={keyword}')
                        for elem in elements:
                            try:
                                parent = elem.evaluate('el => el.parentElement')
                                if parent:
                                    contact_text = parent.text_content().strip()
                                    if len(contact_text) > 10 and len(contact_text) < 1000:
                                        contact_info['contact_sections'].append(contact_text)
                            except Exception:
                                continue
                    except Exception:
                        continue
                
                # Also look for specific contact divs/sections
                try:
                    contact_divs = page.query_selector_all('div, section, p')
                    for div in contact_divs:
                        try:
                            contact_text = div.text_content().strip()
                            if len(contact_text) > 10 and len(contact_text) < 1000:
                                if any(keyword in contact_text.lower() for keyword in ['contact', 'email', 'phone']):
                                    contact_info['contact_sections'].append(contact_text)
                        except Exception:
                            continue
                except Exception:
                    pass
                
                browser.close()
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
            delay = random.uniform(2, 5)
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
    
    scraper = SAMPlaywrightScraper()
    
    print("Starting SAM.gov opportunity scraping with Playwright...")
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