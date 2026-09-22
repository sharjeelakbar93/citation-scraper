from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.async_api import async_playwright
import re

app = FastAPI()

class ScrapeRequest(BaseModel):
    url: str

@app.get("/")
def home():
    return {"status": "Scraper Service is Online"}

@app.post("/scrape")
async def scrape_site(data: ScrapeRequest):
    url = data.url
    if not url.startswith("http"):
        url = "https://" + url

    extracted_data = {
        "title": "",
        "description": "",
        "images": [],
        "text_content": []
    }

    async with async_playwright() as p:
        # Launch headless browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            # Navigate to the target page with 30s timeout
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)  # Render JS elements

            # 1. Page Title
            extracted_data["title"] = await page.title()

            # 2. Extract Meta Description
            meta_desc = await page.query_selector('meta[name="description"]')
            if meta_desc:
                extracted_data["description"] = await meta_desc.get_attribute("content") or ""

            # 3. Extract Images (Filtering small icons / logos)
            img_elements = await page.query_selector_all('img')
            images = []
            for img in img_elements:
                src = await img.get_attribute('src') or await img.get_attribute('data-src')
                if src and any(src.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = url.rstrip('/') + src
                    if src not in images and not any(x in src.lower() for x in ['icon', 'logo', 'avatar', 'loader']):
                        images.append(src)
                        if len(images) >= 8:  # Limit to top 8 product images
                            break

            extracted_data["images"] = images

            # 4. Extract Main Headings / Products Text
            headings = await page.query_selector_all('h1, h2, h3, p')
            text_blocks = []
            for h in headings[:15]:
                text = await h.inner_text()
                clean_text = text.strip()
                if len(clean_text) > 10 and clean_text not in text_blocks:
                    text_blocks.append(clean_text)

            extracted_data["text_content"] = text_blocks[:10]

        except Exception as e:
            print(f"Scraping Error: {str(e)}")
            extracted_data["error"] = str(e)

        finally:
            await browser.close()

    return extracted_data
