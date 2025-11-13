#!/usr/bin/env python3
"""
Script para testar HISTERESE
- Fase 1: 15 Mb/s por 5s (vai para RED)
- Fase 2: 0.5 Mb/s por 12s (fica em RED, ainda não recupera)
- Fase 3: Continua 0.5 Mb/s até completar 100 janelas (10s adicionais)

Expectativa: Deve permanecer RED até completar 100 janelas < 1 Mb/s
"""

import socket
import time
import sys

def send_udp_burst(sock, target, rate_mbps, duration_sec, phase_name):
    """
    Envia uma rajada de tráfego com taxa controlada
    """
    packet_size = 1400
    rate_bps = rate_mbps * 1_000_000
    rate_Bps = rate_bps / 8
    packets_per_second = rate_Bps / packet_size
    interval = 1.0 / packets_per_second if packets_per_second > 0 else 1.0
    
    payload = b'Z' * packet_size
    
    print(f"\n{'='*60}")
    print(f"FASE: {phase_name}")
    print(f"Taxa: {rate_mbps} Mb/s por {duration_sec} segundos")
    print(f"Pacotes/segundo: {packets_per_second:.2f}")
    print(f"{'='*60}\n")
    
    start_time = time.time()
    packets_sent = 0
    bytes_sent = 0
    
    while time.time() - start_time < duration_sec:
        sock.sendto(payload, target)
        packets_sent += 1
        bytes_sent += packet_size
        
        time.sleep(interval)
        
        elapsed = time.time() - start_time
        if packets_sent % max(1, int(packets_per_second)) == 0:
            current_rate = (bytes_sent * 8) / (elapsed * 1_000_000)
            windows_elapsed = int(elapsed / 0.1)
            print(f"[{elapsed:.1f}s | Janela ~{windows_elapsed}] "
                  f"Taxa: {current_rate:.2f} Mb/s, Pacotes: {packets_sent}")
    
    return packets_sent, bytes_sent, time.time() - start_time

def test_hysteresis(target_ip, target_port):
    """
    Testa o comportamento de histerese
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = (target_ip, target_port)
    
    print("="*60)
    print("TESTE DE HISTERESE - Transição RED → GREEN")
    print("="*60)
    print(f"\nTarget: {target_ip}:{target_port}")
    print(f"\nCENÁRIO:")
    print(f"  1. Enviar 15 Mb/s por 5s → Deve ir para RED (canal BAIXA)")
    print(f"  2. Reduzir para 0.5 Mb/s por 12s → Permanece RED")
    print(f"  3. Manter 0.5 Mb/s até completar 100 janelas (~10s)")
    print(f"  4. Após 100 janelas < 1 Mb/s → Deve voltar para GREEN")
    print(f"\nLimiar RED: 8 Mb/s (100KB em 100ms)")
    print(f"Limiar RECOVERY: 1 Mb/s (12.5KB em 100ms)")
    print(f"Janelas para recuperar: 100 (10 segundos)\n")
    
    total_packets = 0
    total_bytes = 0
    overall_start = time.time()
    
    try:
        # FASE 1: Alta vazão - vai para RED
        print("\n🔴 FASE 1: ALTA VAZÃO (15 Mb/s)")
        print("   Expectativa: Após 100ms, fluxo vai para RED")
        p, b, d = send_udp_burst(sock, target, 15, 5, "Alta Vazão - Trigger RED")
        total_packets += p
        total_bytes += b
        
        # FASE 2: Baixa vazão - ainda em RED (menos de 100 janelas)
        print("\n🟡 FASE 2: BAIXA VAZÃO (0.5 Mb/s) - 12 segundos")
        print("   Expectativa: Permanece RED (apenas 120 janelas, precisa de 100 consecutivas)")
        p, b, d = send_udp_burst(sock, target, 0.5, 12, "Baixa Vazão - Contando Janelas")
        total_packets += p
        total_bytes += b
        
        # FASE 3: Continua baixa vazão até completar 100 janelas
        print("\n🟢 FASE 3: BAIXA VAZÃO (0.5 Mb/s) - 10 segundos adicionais")
        print("   Expectativa: Completa 100 janelas consecutivas < 1 Mb/s")
        print("   Após ~10s: Deve voltar para GREEN (canal ALTA)")
        p, b, d = send_udp_burst(sock, target, 0.5, 10, "Baixa Vazão - Recuperação")
        total_packets += p
        total_bytes += b
        
    except KeyboardInterrupt:
        print("\n\nInterrompido pelo usuário")
    
    finally:
        total_duration = time.time() - overall_start
        avg_rate = (total_bytes * 8) / (total_duration * 1_000_000)
        
        print(f"\n{'='*60}")
        print("ESTATÍSTICAS FINAIS")
        print(f"{'='*60}")
        print(f"Duração total: {total_duration:.2f} segundos")
        print(f"Janelas totais: ~{int(total_duration / 0.1)}")
        print(f"Pacotes enviados: {total_packets}")
        print(f"Bytes enviados: {total_bytes:,}")
        print(f"Taxa média: {avg_rate:.2f} Mb/s")
        
        print(f"\n{'='*60}")
        print("VERIFICAÇÃO NO WIRESHARK/TCPDUMP:")
        print(f"{'='*60}")
        print("FASE 1 (0-5s):")
        print("  ✓ Primeiros ~100ms: DSCP = AF41 (0x88) - s1-p2")
        print("  ✓ Depois: DSCP = BE (0x00) - s1-p3")
        print("\nFASE 2 (5-17s):")
        print("  ✓ DSCP = BE (0x00) - s1-p3")
        print("  ✓ Permanece no canal BAIXA")
        print("\nFASE 3 (17-27s):")
        print("  ✓ Primeiros ~10s: DSCP = BE (0x00) - s1-p3")
        print("  ✓ Após completar 100 janelas < 1 Mb/s:")
        print("    → DSCP muda para AF41 (0x88) - s1-p2")
        print("\n⚠️  HISTERESE: Transição RED→GREEN é lenta (10s)")
        print("    Transição GREEN→RED é rápida (100ms)")
        
        sock.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Uso: {sys.argv[0]} <IP_DESTINO> <PORTA>")
        print(f"Exemplo: {sys.argv[0]} 10.0.2.2 5001")
        sys.exit(1)
    
    target_ip = sys.argv[1]
    target_port = int(sys.argv[2])
    
    test_hysteresis(target_ip, target_port)