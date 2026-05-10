#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Inicializador Rápido - Sistema de Análise Operacional com IA
Execute este script para começar
"""

import os
import sys
import subprocess
import webbrowser
from pathlib import Path


def check_dependencies():
    """Verifica se as dependências estão instaladas"""
    print("🔍 Verificando dependências...")
    
    required = ['flask', 'pandas', 'numpy']
    missing = []
    
    for package in required:
        try:
            __import__(package)
            print(f"   ✓ {package}")
        except ImportError:
            print(f"   ✗ {package} (faltando)")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Dependências faltando: {', '.join(missing)}")
        print("   Instalando...")
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'
        ])
        print("   ✓ Instalação concluída!")
    
    print()


def show_menu():
    """Mostra menu inicial"""
    print("\n" + "=" * 60)
    print("SISTEMA DE ANÁLISE OPERACIONAL COM IA".center(60))
    print("FinanceAI v1.0".center(60))
    print("=" * 60)
    print()
    print("Escolha uma opção:")
    print()
    print("  1. Dashboard Simples (http://localhost:5000)")
    print("  2. Dashboard Profissional (http://localhost:5000/advanced)")
    print("  3. Teste do Sistema")
    print("  4. Sair")
    print()


def run_dashboard(advanced=False):
    """Inicia o Flask com o dashboard escolhido"""
    print()
    print("=" * 60)
    print("Iniciando aplicação...".center(60))
    print("=" * 60)
    print()
    
    url = "http://localhost:5000/advanced" if advanced else "http://localhost:5000"
    print(f"✓ Servidor iniciando em http://localhost:5000")
    print(f"✓ Acessar: {url}")
    print(f"✓ Para parar: pressione CTRL+C")
    print()
    print("-" * 60)
    print()
    
    # Abrir navegador
    import time
    time.sleep(2)
    webbrowser.open(url)
    
    # Iniciar Flask
    os.system('python app.py')


def run_tests():
    """Executa testes do sistema"""
    print()
    print("=" * 60)
    print("Executando testes...".center(60))
    print("=" * 60)
    print()
    
    os.system('python test_system.py')
    
    print()
    input("Pressione ENTER para voltar ao menu...")


def main():
    """Loop principal"""
    
    # Verificar dependências
    check_dependencies()
    
    while True:
        show_menu()
        
        choice = input("Sua escolha (1-4): ").strip()
        
        if choice == '1':
            run_dashboard(advanced=False)
        elif choice == '2':
            run_dashboard(advanced=True)
        elif choice == '3':
            run_tests()
        elif choice == '4':
            print("\n👋 Até logo!\n")
            break
        else:
            print("\n❌ Opção inválida!\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Aplicação encerrada pelo usuário.\n")
    except Exception as e:
        print(f"\n❌ Erro: {e}\n")
        import traceback
        traceback.print_exc()
