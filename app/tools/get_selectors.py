"""
Bot Omie - Ferramenta de Descoberta de Seletores
=================================================

Esta ferramenta abre o navegador carregando sua sessão autenticada (auth.json)
e pausa a execução, abrindo o Playwright Inspector.

Como usar:
1. O navegador abrirá logado no Omie.
2. Uma janela "Playwright Inspector" abrirá ao lado.
3. No Inspector, clique no botão "Explore" (ícone de mira/alvo).
4. Passe o mouse sobre os elementos do site (botões, tabelas).
5. O seletor aparecerá abaixo do elemento e na janela do Inspector.
6. Copie o seletor clicando no ícone de cópia ao lado dele no Inspector.
"""

import os
import sys
from playwright.sync_api import sync_playwright

# Add parent path to allow importing from app if needed
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Path to auth.json (in project root)
AUTH_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'auth.json')

def main():
    if not os.path.exists(AUTH_FILE):
        print(f"ERRO: Arquivo de autenticação não encontrado em: {AUTH_FILE}")
        print("Execute 'python app/gui.py' e faça a 'Primeira Configuração' antes.")
        return

    print("="*60)
    print("MODO DE INSPEÇÃO DE SELETORES")
    print("="*60)
    print(f"Carregando sessão de: {AUTH_FILE}")
    print("O navegador abrirá. Use o 'Playwright Inspector' para pegar os seletores.")
    print("1. Clique em 'Pick Locator' (ícone de mira) na janela do Inspector")
    print("2. Clique no elemento desejado na página")
    print("3. Copie o texto do campo 'Locator' na janela do Inspector")
    print("="*60)

    with sync_playwright() as p:
        # Launch visible browser
        browser = p.firefox.launch(headless=False)
        
        # Load auth state
        context = browser.new_context(storage_state=AUTH_FILE)
        
        page = context.new_page()
        
        # Go to Omie home
        print("Navegando para https://app.omie.com.br ...")
        page.goto("https://app.omie.com.br")
        
        # Pause execution to allow inspection
        # This opens the Playwright Inspector UI
        print("\nSISTEMA PAUSADO PARA INSPEÇÃO.")
        print("Pressione 'Resume' no Inspector ou feche as janelas para sair.")
        page.pause()
        
        browser.close()

if __name__ == "__main__":
    main()
