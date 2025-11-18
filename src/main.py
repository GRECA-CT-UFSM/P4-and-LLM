#!/usr/bin/env python3
"""Entrada principal para rodar a simulação.

Modos:
  - subprocess: usa MininetSimulator para iniciar o script `controller.py` como subprocesso.
  - inprocess: instancia `Controller` em um processo filho (multiprocessing) e o executa.

Exemplos:
  python3 src/main.py --mode subprocess --duration 60
  python3 src/main.py --mode inprocess --duration 60 --provider openai --api-key <KEY>
"""

import argparse
import sys
import time
import os
import multiprocessing
import importlib.util

from mininet_setup import MininetSimulator


def run_subprocess_mode(controller_path: str, duration: int):

    sim = MininetSimulator(controller_path=controller_path, duration=duration)
    sim.run()


def run_inprocess_mode(api_key: str | None, provider: str | None, model: str | None, duration: int):
    # Carrega Controller dinamicamente a partir do arquivo src/class/controller.py

    controller_file = os.path.join(os.path.dirname(__file__), 'class', 'controller.py')
    spec = importlib.util.spec_from_file_location('class_controller', controller_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    Controller = getattr(module, 'Controller')

    def _target(a_key, prov):
        ctrl = Controller(api_key=a_key, provider=prov, model=model)
        ctrl.run_simulated_controller()

    p = multiprocessing.Process(target=_target, args=(api_key, provider), daemon=False)
    p.start()
    try:
        print(f"Executando Controller em processo separado por {duration} segundos...")
        time.sleep(duration)
    finally:
        print("Parando o processo do Controller...")
        p.terminate()
        p.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description="Runner para P4-and-LLM (simulação)")
    parser.add_argument('--mode', choices=['subprocess', 'inprocess'], default='subprocess', help='Modo de execução')
    parser.add_argument('--duration', type=int, default=60, help='Duração da simulação em segundos')
    parser.add_argument('--controller-path', type=str, default=None, help='Caminho para controller.py (apenas subprocess)')
    parser.add_argument('--provider', type=str, default=None, help='Provider LLM (ex: openai) para modo inprocess')
    parser.add_argument('--api-key', type=str, default=None, help='Chave de API para o provider')
    parser.add_argument('--model', type=str, default=None, help='Identificador do modelo dentro da API do provedor requisitado')

    args = parser.parse_args()

    controller_path = args.controller_path or os.path.join(os.path.dirname(__file__), 'controller.py')

    if args.mode == 'subprocess':
        run_subprocess_mode(controller_path=controller_path, duration=args.duration)
    else:
        run_inprocess_mode(api_key=args.api_key, provider=args.provider, duration=args.duration)


if __name__ == '__main__':
    main()
