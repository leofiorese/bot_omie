"""
Bot Omie - Authentication Module
=================================

Handles authentication with Omie ERP using Playwright.
Features:
- First run: Opens visible browser for manual authentication (including 2FA)
- Subsequent runs: Uses saved cookies (auth.json) in headless mode
"""

import os
import logging
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Paths
AUTH_STATE_FILE = os.path.join(os.path.dirname(__file__), '..', 'auth.json')
DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), 'downloads')

# Omie URL
OMIE_URL = os.getenv('OMIE_URL', 'https://app.omie.com.br')


def auth_exists() -> bool:
    """Check if authentication state file exists."""
    return os.path.exists(AUTH_STATE_FILE)


def get_browser_context(playwright, headless: bool = True) -> tuple[Browser, BrowserContext]:
    """
    Creates browser and context with proper configuration.
    
    Args:
        playwright: Playwright instance
        headless: Whether to run in headless mode
    
    Returns:
        tuple: (Browser, BrowserContext)
    """
    browser = playwright.firefox.launch(
        headless=headless,
        slow_mo=100 if not headless else 0  # Slow down for visibility on first run
    )
    
    context_options = {
        'viewport': {'width': 1366, 'height': 768},  # Standard HD resolution, no custom scaling
        'accept_downloads': True,
        'permissions': [],  # Block all permissions (notifications, geo, etc)
    }
    
    # Load saved state if exists (works for both headless and visible browser)
    if auth_exists():
        context_options['storage_state'] = AUTH_STATE_FILE
        logger.info(f"✅ Carregando cookies salvos de: {AUTH_STATE_FILE}")
    else:
        logger.warning(f"⚠️ Arquivo auth.json não encontrado. Execute 'Primeira Configuração'")
    
    context = browser.new_context(**context_options)
    
    # Ensure downloads directory exists
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    
    return browser, context


def save_auth_state(context: BrowserContext) -> None:
    """Save authentication state (cookies) to file."""
    context.storage_state(path=AUTH_STATE_FILE)
    logger.info(f"Authentication state saved to {AUTH_STATE_FILE}")


def primeira_configuracao() -> bool:
    """
    Runs the first-time setup with visible browser.
    User must authenticate manually (including 2FA if required).
    
    Returns:
        bool: True if authentication was successful and saved
    """
    logger.info("Iniciando primeira configuração com browser visível...")
    
    with sync_playwright() as playwright:
        browser, context = get_browser_context(playwright, headless=False)
        page = context.new_page()
        
        try:
            # Navigate to Omie login
            page.goto(OMIE_URL, timeout=60000)
            logger.info(f"Navegou para {OMIE_URL}")
            
            print("\n" + "="*60)
            print("PRIMEIRA CONFIGURAÇÃO - AUTENTICAÇÃO MANUAL")
            print("="*60)
            print("\n1. Faça login no Omie (incluindo 2FA se necessário)")
            print("2. Navegue até a página principal após login")
            print("3. Quando terminar, pressione ENTER neste terminal\n")
            
            input("Pressione ENTER quando terminar o login...")
            
            # Save the authentication state
            save_auth_state(context)
            
            print("\n✅ Autenticação salva com sucesso!")
            print("Próximas execuções usarão os cookies salvos.\n")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro na primeira configuração: {e}")
            return False
        finally:
            browser.close()


def verificar_login(page: Page, timeout: int = 10000) -> bool:
    """
    Verifies if the user is logged in by checking for common elements.
    
    Args:
        page: Playwright page
        timeout: Timeout in milliseconds
    
    Returns:
        bool: True if logged in
    """
    try:
        # Look for common logged-in indicators
        # These selectors might need adjustment based on Omie's actual UI
        logged_in_selectors = [
            'text=Acessar',  # "Acessar" button on home
            '[data-testid="user-menu"]',
            '.user-avatar',
            'text=Dashboard'
        ]
        
        for selector in logged_in_selectors:
            try:
                if page.locator(selector).first.is_visible(timeout=timeout):
                    logger.info("Login verificado com sucesso")
                    return True
            except:
                continue
        
        return False
        
    except Exception as e:
        logger.warning(f"Não foi possível verificar login: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    if auth_exists():
        print(f"✅ Arquivo de autenticação encontrado: {AUTH_STATE_FILE}")
        resposta = input("Deseja reconfigurar? (s/N): ")
        if resposta.lower() == 's':
            primeira_configuracao()
    else:
        print("❌ Arquivo de autenticação não encontrado.")
        primeira_configuracao()
