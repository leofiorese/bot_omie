"""
Bot Omie - Utility Functions Module
====================================

Provides utility functions for file archiving and common operations.
Based on bot_pso architecture.
"""

import os
import shutil
import logging

logger = logging.getLogger(__name__)

# ============================================
# HARDCODED NETWORK PATH - ADJUST AS NEEDED
# ============================================
REDE_DESTINO = r"Z:\3-Corporativo\PMO\0-Gerência do PMO\6-Controles\8-Estruturação PMO\4 - Implementação\2 - Custos\Database"


def arquivar_arquivo(source_path: str, table_name: str) -> bool:
    """
    Move o arquivo processado para o diretório de rede.
    Renomeia o arquivo para o nome da tabela com extensão original.
    
    Args:
        source_path: Caminho do arquivo fonte (ex: app/downloads/A PAGAR.xlsx)
        table_name: Nome da tabela MySQL (usado para renomear o arquivo)
    
    Returns:
        bool: True se arquivado com sucesso, False caso contrário
    """
    try:
        # Get file extension from source
        _, ext = os.path.splitext(source_path)
        
        # Build destination path
        dest_filename = f"{table_name}{ext}"
        dest_path = os.path.join(REDE_DESTINO, dest_filename)
        
        # Create destination directory if it doesn't exist
        if not os.path.exists(REDE_DESTINO):
            os.makedirs(REDE_DESTINO)
            logger.info(f"Created destination directory: {REDE_DESTINO}")
        
        # Move file (overwrites if exists)
        # On Windows, shutil.move might fail if dest exists, so we remove it first
        if os.path.exists(dest_path):
            os.remove(dest_path)
            logger.info(f"Arquivo destino existente removido: {dest_path}")
            
        shutil.move(source_path, dest_path)
        logger.info(f"Arquivo arquivado com sucesso: {source_path} -> {dest_path}")
        
        return True
        
    except FileNotFoundError:
        logger.error(f"Arquivo não encontrado: {source_path}")
        return False
    except PermissionError:
        logger.error(f"Permissão negada ao acessar: {REDE_DESTINO}")
        return False
    except Exception as e:
        logger.error(f"Erro ao arquivar arquivo: {e}")
        return False


def deletar_arquivo_local(file_path: str) -> bool:
    """
    Deleta um arquivo local após processamento.
    
    Args:
        file_path: Caminho do arquivo a ser deletado
    
    Returns:
        bool: True se deletado com sucesso, False caso contrário
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Arquivo local deletado: {file_path}")
            return True
        else:
            logger.warning(f"Arquivo não existe para deletar: {file_path}")
            return False
    except Exception as e:
        logger.error(f"Erro ao deletar arquivo: {e}")
        return False


if __name__ == "__main__":
    # Test function
    print(f"Destination path configured: {REDE_DESTINO}")
