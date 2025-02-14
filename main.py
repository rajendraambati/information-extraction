import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import pandas as pd
import time
import re
from bs4 import BeautifulSoup
import requests
import io  # Import this module to handle in-memory files

# Function to extract data using XPath
def extract_data(xpath, driver):
    """
    Extract data from the page using the provided XPath.
    If the element exists, return its text; otherwise, return "N/A".
    """
    try:
        element = driver.find_element(By.XPATH, xpath)
        return element.text
    except:
        return "N/A"

# Main function to scrape Google Maps
def scrape_google_maps(search_query, driver):
    try:
        # Open Google Maps
        driver.get("https://www.google.com/maps")
        time.sleep(5)  # Wait for the page to load
        
        # Enter the search query into the search box
        search_box = driver.find_element(By.XPATH, '//input[@id="searchboxinput"]')
        search_box.send_keys(search_query)
        search_box.send_keys(Keys.ENTER)
        time.sleep(5)  # Wait for results to load
        
        # Zoom out globally to ensure all results are loaded
        actions = ActionChains(driver)
        for _ in range(10):  # Zoom out multiple times
            actions.key_down(Keys.CONTROL).send_keys("-").key_up(Keys.CONTROL).perform()
            time.sleep(1)  # Wait for the map to adjust
        
        # Scroll and collect all listings
        all_listings = set()  # Use a set to avoid duplicates
        previous_count = 0
        max_scrolls = 50  # Limit the number of scrolls to prevent infinite loops
        scroll_attempts = 0
        
        while scroll_attempts < max_scrolls:
            # Scroll down to load more results
            scrollable_div = driver.find_element(By.XPATH, '//div[contains(@aria-label, "Results for")]')
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
            time.sleep(3)  # Wait for new results to load
            
            # Collect all visible listings
            current_listings = driver.find_elements(By.XPATH, '//a[contains(@href, "https://www.google.com/maps/place")]')
            current_count = len(current_listings)
            
            # Add new listings to the set
            for listing in current_listings:
                href = listing.get_attribute("href")
                if href:
                    all_listings.add(href)
            
            # Check if no new results were loaded
            if current_count == previous_count:
                break
            
            # Update the previous count
            previous_count = current_count
            scroll_attempts += 1
        
        # Extract details for each unique listing
        results = []
        for i, href in enumerate(all_listings):
            driver.get(href)
            time.sleep(3)  # Wait for the sidebar to load
            
            # Extract details
            name = extract_data('//h1[contains(@class, "DUwDvf lfPIob")]', driver)
            address = extract_data('//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]', driver)
            phone = extract_data('//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]', driver)
            website = extract_data('//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]', driver)
            
            # Append to results
            results.append({
                "Name": name,
                "Address": address,
                "Phone Number": phone,
                "Website": website
            })
        
        # Return results as a DataFrame
        return pd.DataFrame(results)
    
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

# Function to extract emails using regex
def extract_emails_from_text(text):
    return re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)

# Function to scrape a website for emails
def scrape_website_for_emails(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract emails from the homepage
        emails = set(extract_emails_from_text(soup.get_text()))
        
        # Check the footer for emails
        footer = soup.find('footer')
        if footer:
            emails.update(extract_emails_from_text(footer.get_text()))
        
        # Find links to the contact page
        contact_links = [a['href'] for a in soup.find_all('a', href=True) if 'contact' in a['href'].lower()]
        for link in contact_links:
            if not link.startswith("http"):
                link = url.rstrip("/") + "/" + link.lstrip("/")
            try:
                contact_response = requests.get(link, timeout=10)
                contact_soup = BeautifulSoup(contact_response.content, 'html.parser')
                emails.update(extract_emails_from_text(contact_soup.get_text()))
            except Exception:
                continue
        
        return list(emails)
    
    except Exception:
        return []

# Main function to process the workflow
def main():
    st.title("Safron Engine")
    
    # Input for search query
    search_query = st.text_input("Enter the search query (e.g., 'palm oil companies in india'):", "")
    
    # Placeholder for dynamic updates
    placeholder = st.empty()
    
    # Scrape button
    if st.button("Scrap It!"):
        if not search_query.strip():
            st.error("Please enter a valid search query.")
            return
        
        # Show processing message
        placeholder.markdown("**Processing..... Please Wait**")
        
        # Set up Selenium WebDriver
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--headless")  # Run in headless mode
        driver = webdriver.Chrome(options=options)
        
        # Scrape Google Maps
        df = scrape_google_maps(search_query, driver)
        
        # Close the browser
        driver.quit()
        
        if df is not None:
            # Read the websites from the DataFrame
            websites = df["Website"].tolist()
            
            # Scrape emails for each website
            email_results = []
            for website in websites:
                if website != "N/A" and isinstance(website, str) and website.strip():
                    urls_to_try = [f"http://{website}", f"https://{website}"]
                    emails_found = []
                    for url in urls_to_try:
                        emails = scrape_website_for_emails(url)
                        emails_found.extend(emails)
                    email_results.append(", ".join(set(emails_found)) if emails_found else "N/A")
                else:
                    email_results.append("N/A")
            
            # Add emails to the DataFrame
            df["Email"] = email_results
            
            # Save the final results to an Excel file in memory
            output = io.BytesIO()  # Create an in-memory bytes buffer
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, index=False)
            output.seek(0)  # Move the pointer to the beginning of the buffer
            
            # Clear the placeholder
            placeholder.empty()
            
            # Display success message and download button
            st.success("Done! 👇Click Download Button Below")
            st.download_button(
                label="Download Results",
                data=output,
                file_name="final_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

if __name__ == "__main__":
    main()