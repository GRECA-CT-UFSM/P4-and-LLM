import requests
import os
import time
import random
import json
from typing import Any, Optional
import ollama

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore


class Controller:
    """Controlador simulado que usa uma LLM para detectar anomalias em fluxos de rede.

    O Controller recebe um provider, que é o nome de um cliente suportado. 
    Na implementação atual, "openai" e "ollama" são clientes válidos.

    Em caso de cliente com uso de chave de API, essa deve ser passada em api_key

    Para especificar o modelo, passe seu identificador em model.
    Se não for especificado, será usado um modelo default.
    """

    def __init__(self, provider: Optional[str] = None, api_key: Optional[str] = None, model: Optional[str] = None):
        self.provider = provider
        self.model = model

        # Tenta inicializar automaticamente o cliente OpenAI se solicitado
        if provider == 'openai':
            try:
                if api_key is None:
                    raise Exception("Chave de API não inserida.")
                
                if OpenAI is None:
                    raise Exception("Erro ao importar biblioteca.")
                
                self.client = OpenAI(api_key=api_key)
                print("Cliente OpenAI inicializado.")
                return
            
            except Exception as e:
                print(f"Erro ao inicializar OpenAI client: {e}")
                exit(0)

        # Tenta inicializar automaticamente o cliente Ollama se solicitado
        if provider == "ollama":
            try:
                ollama.list()
                print("Ollama está disponível.")
                return
            
            except Exception as e:
                print(f"Erro ao se conectar com a Ollama: {e}")
                exit(0)

        print("Cliente desconhecido. Verifique os clientes válidos.")
        exit(0)


    def call_llm_for_anomaly_detection(self, flow_data: dict) -> Optional[str]:
        """Gera o prompt a partir de `flow_data` e chama o cliente LLM configurado.

        Retorna uma string JSON (preferível) ou None em caso de erro.
        """

        # tune and edit messages in prompts.json
        with open("src/prompts.json", encoding="utf8") as file:
            messages = json.load(file)["prompts"]

        try:
            # 1) Chamada OpenAI
            if self.provider == "openai":
                fn = self.client.chat.completions.create
                resp = fn(
                    model=self.model if self.model else "gpt-3.5-turbo",
                    messages=[
                        {"role": messages[0]["role"], "content": messages[0]["content"]},
                        {"role": messages[1]["role"], "content": messages[1]["content"]},
                        {"role": "user", "content": f"{flow_data}"},
                        {"role": messages[2]["role"], "content": messages[2]["content"]},
                        {"role": messages[3]["role"], "content": messages[3]["content"]},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )
                # normaliza a resposta
                if isinstance(resp, dict):
                    return json.dumps(resp)
                if hasattr(resp, 'choices'):
                    try:
                        return resp.choices[0].message.content
                    except Exception:
                        return str(resp)

            # 2) Estilo Ollama
            if self.provider == "ollama":
                resp = ollama.chat(
                    model=self.model if self.model else "llama3",
                    messages=[
                        {"role": messages[0]["role"], "content": messages[0]["content"]},
                        {"role": messages[1]["role"], "content": messages[1]["content"]},
                        {"role": "user", "content": f"{flow_data}"},
                        {"role": messages[2]["role"], "content": messages[2]["content"]},
                        {"role": messages[3]["role"], "content": messages[3]["content"]},
                    ],
                    options={
                        'temperature': 0.2,
                        }
                    )
                
                if isinstance(resp, dict):
                    return json.dumps(resp)
                print(resp["message"]["content"])
                return resp["message"]["content"]


            print("Formato de cliente desconhecido — não foi possível chamar o LLM.")
            return None
        
        except Exception as e:
            print(f"Erro ao chamar o cliente LLM: {e}")
            return None

    def clean_llm_formatting_mishaps(self, text: str) -> str:
        text = text.removeprefix("```json")
        text = text.removesuffix("```")
        text = text.replace("\n", "")
        text = text.strip()

        return text

    def simulate_llm_anomaly_detection(self, flow_data: dict) -> dict:
        """Chama a LLM (real ou simulada) e normaliza a resposta para {'action': ..., 'src_ip': ...}.
        """
        print(f"[LLM] Enviando dados de fluxo para análise: {flow_data}")
        llm_response = self.call_llm_for_anomaly_detection(flow_data)

        if llm_response:
            try:
                cleaned_response = self.clean_llm_formatting_mishaps(llm_response)
                parsed_response = json.loads(cleaned_response) if isinstance(cleaned_response, str) else cleaned_response
                print(f"[LLM] Resposta: {parsed_response}")
                if parsed_response.get("anomaly_detected") and parsed_response.get("action") == "drop":
                    return {"action": "drop", "src_ip": parsed_response.get("target_ip")}
                else:
                    return {"action": "none"}
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Erro ao decodificar JSON da resposta da LLM: {e}")
                return {"action": "none"}
        return {"action": "none"}

    def simulate_p4_rule_application(self, table_name: str, match_fields: dict, action_name: str, action_params: Optional[dict] = None) -> None:
        if action_params is None:
            action_params = {}
        print(f"[P4Runtime Simulado] Aplicando regra na tabela '{table_name}':")
        print(f"  Match: {match_fields}")
        print(f"  Action: {action_name} com parâmetros {action_params}")
        print("[P4Runtime Simulado] Regra aplicada com sucesso (simulado).")

    def run_simulated_controller(self) -> None:
        print("Controlador simulado iniciado. Gerando e analisando dados de fluxo...")
        print("[Controlador Simulado] Pipeline P4 configurado (simulado).")
        print("[Controlador Simulado] Digest configurado (simulado).")

        flow_id = 0
        while True:
            flow_id += 1
            src_ip_prefix = "10.0.0."
            dst_ip_prefix = "10.0.0."

            if random.random() < 0.3:
                src_ip = "10.0.0.1"
                packet_count = random.randint(6, 20)
            else:
                src_ip = src_ip_prefix + str(random.randint(2, 254))
                packet_count = random.randint(1, 5)

            dst_ip = dst_ip_prefix + str(random.randint(2, 254))
            src_port = random.randint(1024, 65535)
            dst_port = random.choice([80, 443, 22, 23, 53, 8080])
            protocol = random.choice([6, 17])
            byte_count = packet_count * random.randint(64, 1500)

            simulated_flow_data = {
                "flow_id": flow_id,
                "src_ip": src_ip,
                "dst_ip": dst_ip,
                "src_port": src_port,
                "dst_port": dst_port,
                "protocol": protocol,
                "packet_count": packet_count,
                "byte_count": byte_count,
            }

            print(f"\n[Controlador Simulado] Gerado dados de fluxo: {simulated_flow_data}")

            llm_response = self.simulate_llm_anomaly_detection(simulated_flow_data)

            if llm_response.get("action") == "drop":
                print(f"[Controlador Simulado] LLM recomendou DROPAR tráfego do IP: {llm_response['src_ip']}")
                self.simulate_p4_rule_application("acl_table", {"hdr.ipv4.srcAddr": llm_response['src_ip']}, "_drop")

            time.sleep(2)


def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    # gemma3:4b is a light model from google. runs easily on a single gpu
    ctrl = Controller(api_key=api_key, provider='ollama', model="gemma3:4b")
    ctrl.run_simulated_controller()

if __name__ == "__main__":
    main()