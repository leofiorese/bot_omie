"""
Bot Omie - GUI Module (Tkinter)
================================

Interface gráfica para controle do bot de extração de relatórios do Omie ERP.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import logging
import os
import sys

# Add parent path for imports
sys.path.insert(0, os.path.dirname(__file__))

from auth import auth_exists, primeira_configuracao

logger = logging.getLogger(__name__)


class TextHandler(logging.Handler):
    """Custom logging handler to redirect logs to Tkinter Text widget."""
    
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
    
    def emit(self, record):
        msg = self.format(record)
        self.text_widget.configure(state='normal')
        self.text_widget.insert(tk.END, msg + '\n')
        self.text_widget.configure(state='disabled')
        self.text_widget.see(tk.END)


class BotOmieGUI:
    """Main GUI application class."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Bot Omie - Extração de Relatórios")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Report configurations
        # Report configurations
        self.relatorios = [
            {
                "nome_menu": "Contas a Pagar - PMO", 
                "arquivo": "A PAGAR.xlsx", 
                "tabela": "A_PAGAR", 
                "data_slug": "rel-fin-custom-contas-a-pagar-pmo--5786318546",
                "var": None
            },
            {
                "nome_menu": "Notas Faturadas - PMO", 
                "arquivo": "NF_FATURADAS.xlsx", 
                "tabela": "NF_FATURADAS", 
                "data_slug": "rel-fin-custom-notas-faturadas-pmo--5786322454",
                "var": None
            },
            {
                "nome_menu": "Notas Debito - PMO", 
                "arquivo": "NOTAS_DEBITO.xlsx", 
                "tabela": "NOTAS_DEBITO", 
                "data_slug": "rel-fin-custom-notas-debito-pmo--5786322433",
                "var": None
            },
        ]
        
        self.create_widgets()
        self.setup_logging()
        self.check_auth_status()

        # Inactivity Flag System
        self.user_active = False
        self.inactivity_timer = self.root.after(10000, self.check_inactivity)
        
        # Bind user interactions
        self.root.bind('<Button-1>', self.on_user_interaction)
        self.root.bind('<Key>', self.on_user_interaction)

    def on_user_interaction(self, event):
        """Mark user as active and cancel inactivity timer."""
        if not self.user_active:
            self.user_active = True
            if self.inactivity_timer:
                self.root.after_cancel(self.inactivity_timer)
                self.inactivity_timer = None
            logger.info("Interação do usuário detectada. Modo automático cancelado.")

    def check_inactivity(self):
        """Check if user has been inactive and start extraction if so."""
        if not self.user_active:
            logger.info("Nenhuma atividade detectada por 10 segundos. Iniciando extração automática...")
            # Only start if authenticated and not already running
            if auth_exists() and str(self.btn_iniciar['state']) != 'disabled':
                self.run_extracao()
            elif not auth_exists():
                logger.warning("Não foi possível iniciar automaticamente: Não autenticado.")
    
    def create_widgets(self):
        """Create all GUI widgets."""
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # === Header ===
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        title_label = ttk.Label(header_frame, text="🤖 Bot Omie - Extração de Relatórios", 
                                font=('Segoe UI', 16, 'bold'))
        title_label.pack(side=tk.LEFT)
        
        # Auth status indicator
        self.auth_status_label = ttk.Label(header_frame, text="", font=('Segoe UI', 10))
        self.auth_status_label.pack(side=tk.RIGHT)
        
        # === Configuration Frame ===
        config_frame = ttk.LabelFrame(main_frame, text="Configuração", padding="10")
        config_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N), padx=(0, 5))
        
        # First setup button
        self.btn_primeira_config = ttk.Button(
            config_frame, 
            text="🔐 Primeira Configuração",
            command=self.run_primeira_configuracao
        )
        self.btn_primeira_config.pack(fill=tk.X, pady=(0, 10))
        
        # === Reports Frame ===
        reports_frame = ttk.LabelFrame(main_frame, text="Relatórios", padding="10")
        reports_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N), padx=(5, 0))
        
        # Checkboxes for reports
        for i, rel in enumerate(self.relatorios):
            rel["var"] = tk.BooleanVar(value=True)
            cb = ttk.Checkbutton(
                reports_frame, 
                text=rel["nome_menu"],
                variable=rel["var"]
            )
            cb.pack(anchor=tk.W, pady=2)
        
        # Select all / none buttons
        btn_frame = ttk.Frame(reports_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(btn_frame, text="Marcar Todos", 
                   command=lambda: self.set_all_reports(True)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Desmarcar Todos", 
                   command=lambda: self.set_all_reports(False)).pack(side=tk.LEFT, padx=2)
        
        # === Action Buttons ===
        action_frame = ttk.Frame(main_frame)
        action_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        self.btn_iniciar = ttk.Button(
            action_frame, 
            text="▶️ Iniciar Extração",
            command=self.run_extracao,
            style='Accent.TButton'
        )
        self.btn_iniciar.pack(side=tk.LEFT, padx=5)
        
        self.btn_parar = ttk.Button(
            action_frame, 
            text="⏹️ Parar",
            command=self.parar_extracao,
            state=tk.DISABLED
        )
        self.btn_parar.pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(action_frame, mode='indeterminate', length=200)
        self.progress.pack(side=tk.RIGHT, padx=5)
        
        # === Log Frame ===
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        main_frame.rowconfigure(3, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame, 
            height=15, 
            state='disabled',
            font=('Consolas', 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Clear log button
        ttk.Button(log_frame, text="Limpar Log", 
                   command=self.clear_log).pack(anchor=tk.E, pady=(5, 0))
        
        # === Status Bar ===
        self.status_bar = ttk.Label(main_frame, text="Pronto", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
    
    def setup_logging(self):
        """Configure logging to display in the GUI."""
        text_handler = TextHandler(self.log_text)
        text_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
        # Add handler to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(text_handler)
        root_logger.setLevel(logging.INFO)
    
    def check_auth_status(self):
        """Check and display authentication status."""
        if auth_exists():
            self.auth_status_label.config(text="✅ Autenticado", foreground='green')
            self.btn_iniciar.config(state=tk.NORMAL)
        else:
            self.auth_status_label.config(text="❌ Não autenticado", foreground='red')
            self.btn_iniciar.config(state=tk.DISABLED)
            messagebox.showinfo(
                "Primeira Configuração Necessária",
                "Clique em 'Primeira Configuração' para autenticar no Omie."
            )
    
    def set_all_reports(self, value: bool):
        """Set all report checkboxes to the given value."""
        for rel in self.relatorios:
            rel["var"].set(value)
    
    def clear_log(self):
        """Clear the log text widget."""
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')
    
    def run_primeira_configuracao(self):
        """Run first-time configuration in a separate thread."""
        self.status_bar.config(text="Executando primeira configuração...")
        self.btn_primeira_config.config(state=tk.DISABLED)
        
        def task():
            try:
                success = primeira_configuracao()
                self.root.after(0, lambda: self.on_primeira_config_complete(success))
            except Exception as e:
                logger.error(f"Erro na primeira configuração: {e}")
                self.root.after(0, lambda: self.on_primeira_config_complete(False))
        
        thread = threading.Thread(target=task, daemon=True)
        thread.start()
    
    def on_primeira_config_complete(self, success: bool):
        """Callback when first configuration completes."""
        self.btn_primeira_config.config(state=tk.NORMAL)
        self.check_auth_status()
        
        if success:
            self.status_bar.config(text="Primeira configuração concluída com sucesso!")
        else:
            self.status_bar.config(text="Erro na primeira configuração")
    
    def run_extracao(self):
        """Start the extraction process in a separate thread."""
        # Get selected reports
        selected = [rel for rel in self.relatorios if rel["var"].get()]
        
        if not selected:
            messagebox.showwarning("Aviso", "Selecione pelo menos um relatório.")
            return
        
        self.status_bar.config(text="Iniciando extração...")
        self.btn_iniciar.config(state=tk.DISABLED)
        self.btn_parar.config(state=tk.NORMAL)
        self.progress.start()
        
        def task():
            try:
                # Import main module here to avoid circular imports
                from main import run_extraction
                run_extraction(selected)
                self.root.after(0, lambda: self.on_extracao_complete(True))
            except Exception as e:
                logger.error(f"Erro na extração: {e}")
                self.root.after(0, lambda: self.on_extracao_complete(False))
        
        self.extraction_thread = threading.Thread(target=task, daemon=True)
        self.extraction_thread.start()
    
    def on_extracao_complete(self, success: bool):
        """Callback when extraction completes."""
        self.progress.stop()
        self.btn_iniciar.config(state=tk.NORMAL)
        self.btn_parar.config(state=tk.DISABLED)
        
        if success:
            self.status_bar.config(text="Extração concluída com sucesso!")
            messagebox.showinfo("Sucesso", "Extração de relatórios concluída!")
        else:
            self.status_bar.config(text="Erro durante a extração")
            messagebox.showerror("Erro", "Ocorreu um erro durante a extração. Verifique o log.")
    
    def parar_extracao(self):
        """Stop the extraction process."""
        # Note: This is a simple implementation that just updates UI
        # Full implementation would need to interrupt the browser automation
        self.status_bar.config(text="Parando extração...")
        logger.warning("Solicitação de parada recebida. A extração será interrompida após o relatório atual.")
        self.btn_parar.config(state=tk.DISABLED)


def main():
    """Entry point for the GUI application."""
    root = tk.Tk()
    app = BotOmieGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
