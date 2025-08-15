import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client
from playwright.async_api import async_playwright, TimeoutError

# --- MODO DE DEPURACIÓN ---
# Poner en True para imprimir el HTML de un producto y detenerse.
# Poner en False para ejecutar el scraper normalmente.
DEBUG_MODE = False

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# --- Configuración ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPERMARKET_SLUG = "santa-isabel"
TARGET_URL = "https://www.santaisabel.cl/panaderia-y-pasteleria"

# --- Selectores CSS (VERSIÓN DEFINITIVA BASADA EN DEBUG) ---
PRODUCT_CARD_SELECTOR = ".product-card-wrap"
PRODUCT_NAME_SELECTOR = "p.product-card-name"
PRODUCT_PRICE_SELECTOR = "span.prices-main-price"


async def main():
    """
    Función principal que orquesta el proceso de scraping.
    """
    print("🚀 Iniciando scraper para Santa Isabel...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print(f" navegando a: {TARGET_URL}")
        try:
            # Aumentamos el timeout general a 90 segundos
            await page.goto(TARGET_URL, wait_until="networkidle", timeout=190000)
            print("✅ Página cargada correctamente.")
            
            # Aumentamos el timeout para esperar el selector a 90 segundos
            await page.wait_for_selector(PRODUCT_CARD_SELECTOR, timeout=190000)
            print("📦 Productos encontrados en la página.")

        except TimeoutError:
            print("❌ Error: Timeout esperando que la página o los productos cargaran.")
            await browser.close()
            return
        except Exception as e:
            print(f"❌ Error al navegar a la página: {e}")
            await browser.close()
            return

        product_elements = await page.query_selector_all(PRODUCT_CARD_SELECTOR)
        
        if DEBUG_MODE:
            print("\n--- 🕵️ MODO DEPURACIÓN ACTIVADO 🕵️ ---")
            if product_elements:
                first_product_html = await product_elements[0].inner_html()
                print("HTML del primer producto encontrado:")
                print("-----------------------------------------")
                print(first_product_html)
                print("-----------------------------------------")
                print("Copia el bloque de HTML de arriba y pégalo en el chat.")
            else:
                print("No se encontraron elementos con el selector de tarjeta de producto.")
            await browser.close()
            return

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
            print("🤷 No se encontraron productos válidos para insertar. Revisa los selectores.")

if __name__ == "__main__":
    asyncio.run(main())
