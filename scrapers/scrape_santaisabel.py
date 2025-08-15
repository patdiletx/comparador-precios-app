import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client
from playwright.async_api import async_playwright, TimeoutError

# Cargar variables de entorno
load_dotenv()

# --- Configuración ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPERMARKET_SLUG = "santa-isabel"
TARGET_URL = "https://www.santaisabel.cl/panaderia-y-pasteleria"

# --- Selectores CSS (Confirmados) ---
PRODUCT_CARD_SELECTOR = ".product-card-wrap"
PRODUCT_NAME_SELECTOR = "p.product-card-name"
PRODUCT_PRICE_SELECTOR = "span.prices-main-price"

# --- Parámetros Anti-Bloqueo ---
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
VIEWPORT = {"width": 1920, "height": 1080}


async def main():
    """
    Función principal que orquesta el proceso de scraping con técnicas anti-bloqueo.
    """
    print("🚀 Iniciando scraper para Santa Isabel (Modo Evasión)...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport=VIEWPORT
        )
        page = await context.new_page()
        
        print(f" navegando a: {TARGET_URL}")
        try:
            # Usamos 'load' que es más similar a como un usuario espera que la página cargue.
            await page.goto(TARGET_URL, wait_until="load", timeout=90000)
            print("✅ Página cargada correctamente.")
            
            # Esperamos un poco más después de cargar, simulando un usuario que mira la página.
            await page.wait_for_timeout(5000) 
            
            await page.wait_for_selector(PRODUCT_CARD_SELECTOR, timeout=60000)
            print("📦 Productos encontrados en la página.")

        except TimeoutError:
            print("❌ Error: Timeout esperando que la página o los productos cargaran.")
            screenshot_path = "debug_screenshot.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"📸 Screenshot '{screenshot_path}' guardado para depuración.")
            await browser.close()
            return
        except Exception as e:
            print(f"❌ Error al navegar a la página: {e}")
            await browser.close()
            return

        product_elements = await page.query_selector_all(PRODUCT_CARD_SELECTOR)
        
        print(f"🔎 Encontrados {len(product_elements)} productos. Extrayendo datos...")
        
        try:
            supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
            response = supabase.table("supermarkets").select("id").eq("slug", SUPERMARKET_SLUG).execute()
            supermarket_id = response.data[0]['id']
            print(f"✅ Conexión a Supabase y ID de supermercado ('{supermarket_id}') obtenidos.")
        except Exception as e:
            print(f"❌ Error conectando a Supabase o obteniendo ID: {e}")
            await browser.close()
            return

        products_to_insert = []
        for element in product_elements:
            try:
                name_element = await element.query_selector(PRODUCT_NAME_SELECTOR)
                price_element = await element.query_selector(PRODUCT_PRICE_SELECTOR)
                
                if name_element and price_element:
                    name = await name_element.inner_text()
                    price_text = await price_element.inner_text()
                    price = int(''.join(filter(str.isdigit, price_text)))

                    if price > 0:
                        products_to_insert.append({
                            "supermarket_id": supermarket_id,
                            "price": price, "regular_price": price, "is_available": True,
                            "source": "scraping", "metadata": { "scraped_name": name.strip() } 
                        })
            except Exception as e:
                print(f"⚠️ Error extrayendo un producto: {e}. Continuando.")

        await browser.close()
        
        if products_to_insert:
            print(f"📥 Insertando {len(products_to_insert)} productos en la base de datos...")
            try:
                response = supabase.table("prices").insert(products_to_insert).execute()
                if response.data:
                    print(f"✅ ¡Éxito! {len(response.data)} registros insertados.")
                else:
                    print(f"❌ Error en la inserción: {getattr(response, 'error', 'Error desconocido')}")
            except Exception as e:
                print(f"❌ Error crítico al insertar en Supabase: {e}")
        else:
            print("🤷 No se encontraron productos válidos para insertar.")

if __name__ == "__main__":
    asyncio.run(main())
