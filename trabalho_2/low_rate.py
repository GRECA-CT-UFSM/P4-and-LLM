#!/usr/bin/env python3
"""
Script para testar tráfego de BAIXA VAZÃO (3 Mb/s)
Expectativa: DSCP deve ser marcado como AF41 (34) = GREEN
"""

import socket
import time
import sys

def send_udp_traffic(target_ip, target_port, rate_mbps, duration_sec):
    """
    Envia tráfego UDP com taxa controlada
    
    Args:
        target_ip: IP de destino
        target_port: Porta UDP de destino
        rate_mbps: Taxa em Megabits por segundo
        duration_sec: Duração do teste em segundos
    """
    # Cria socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Configurações
    packet_size = 1400  # bytes (tamanho do payload UDP)
    rate_bps = rate_mbps * 1_000_000  # Megabits para bits
    rate_Bps = rate_bps / 8  # bits para Bytes
    packets_per_second = rate_Bps / packet_size
    interval = 1.0 / packets_per_second  # Intervalo entre pacotes
    
    # Payload fixo
    payload = b'X' * packet_size
    
    print(f"=== TESTE DE BAIXA VAZÃO ===")
    print(f"Target: {target_ip}:{target_port}")
    print(f"Taxa desejada: {rate_mbps} Mb/s")
    print(f"Tamanho do pacote: {packet_size} bytes")
    print(f"Pacotes/segundo: {packets_per_second:.2f}")
    print(f"Intervalo entre pacotes: {interval*1000:.2f} ms")
    print(f"Duração: {duration_sec} segundos")
    print(f"\nExpectativa: DSCP = AF41 (34) - Canal ALTA\n")
    
    start_time = time.time()
    packets_sent = 0
    bytes_sent = 0
    
    try:
        while time.time() - start_time < duration_sec:
            # Envia pacote
            sock.sendto(payload, (target_ip, target_port))
            packets_sent += 1
            bytes_sent += packet_size
            
            # Aguarda intervalo
            time.sleep(interval)
            
            # Mostra progresso a cada segundo
            elapsed = time.time() - start_time
            if packets_sent % int(packets_per_second) == 0:
                current_rate = (bytes_sent * 8) / (elapsed * 1_000_000)
                print(f"[{elapsed:.1f}s] Pacotes: {packets_sent}, "
                      f"Taxa atual: {current_rate:.2f} Mb/s")
    
    except KeyboardInterrupt:
        print("\n\nInterrompido pelo usuário")
    
    finally:
        elapsed = time.time() - start_time
        avg_rate = (bytes_sent * 8) / (elapsed * 1_000_000)
        
        print(f"\n=== ESTATÍSTICAS FINAIS ===")
        print(f"Duração: {elapsed:.2f} segundos")
        print(f"Pacotes enviados: {packets_sent}")
        print(f"Bytes enviados: {bytes_sent:,}")
        print(f"Taxa média: {avg_rate:.2f} Mb/s")
        print(f"\nVerifique no Wireshark/tcpdump:")
        print(f"  - DSCP deveria ser AF41 (34) ou 0x88 em hexadecimal")
        print(f"  - Pacotes devem sair pela interface s1-p2 (canal ALTA)")
        
        sock.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Uso: {sys.argv[0]} <IP_DESTINO> <PORTA>")
        print(f"Exemplo: {sys.argv[0]} 10.0.2.2 5001")
        sys.exit(1)
    
    target_ip = sys.argv[1]
    target_port = int(sys.argv[2])
    
    # Testa com 3 Mb/s por 15 segundos
    send_udp_traffic(target_ip, target_port, rate_mbps=3, duration_sec=15)