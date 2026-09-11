"""Manual API smoke test. Importing this module never performs a search."""
import argparse
import os
from pathlib import Path
import sys

# Support direct execution from scripts/ without installing the project.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.providers.google_places import (
    GooglePlacesProvider, GooglePlacesError, GooglePlacesConfigurationError,
    GooglePlacesHTTPError, GooglePlacesResponseError, GooglePlacesTransportError,
)
from core.providers.environment import load_environment

__test__ = False


def limit_value(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("--limit deve ser inteiro de 1 a 20.") from None
    if not 1 <= value <= 20:
        raise argparse.ArgumentTypeError("--limit deve ser inteiro de 1 a 20.")
    return value


def friendly_error(error):
    if isinstance(error, GooglePlacesConfigurationError):
        return "Configuração: defina GOOGLE_PLACES_API_KEY no ambiente ou no .env."
    if isinstance(error, GooglePlacesHTTPError):
        messages = {400: "requisição rejeitada; confira a configuração da API",
                    401: "autenticação rejeitada; confira a chave",
                    403: "acesso negado; confira chave, restrições, API habilitada e faturamento",
                    429: "quota ou limite de requisições atingido"}
        message = f"Erro HTTP {error.status}: " + messages.get(error.status, "falha no serviço Google Places")
        if error.status == 400:
            diagnostic = " | ".join(value for value in (error.api_status, error.api_message) if value)
            if diagnostic:
                message += f" — {diagnostic}"
        return message
    if isinstance(error, GooglePlacesTransportError):
        return "Falha de transporte: timeout ou conexão indisponível."
    if isinstance(error, GooglePlacesResponseError):
        return "Resposta inválida ou erro retornado pela API."
    return "Falha do provider Google Places; busca não concluída."


def main(argv=None):
    parser = argparse.ArgumentParser(description="Teste manual de uma busca Google Places (pode consumir quota).")
    parser.add_argument("--city", default="Taubaté")
    parser.add_argument("--segment", default="dentista")
    parser.add_argument("--limit", type=limit_value, default=5)
    args = parser.parse_args(argv)
    if not args.city.strip() or not args.segment.strip():
        parser.error("Cidade e segmento devem ser preenchidos.")
    provider = None
    try:
        load_environment()
        provider = GooglePlacesProvider(max_requests=1)
        results = provider.search(city=args.city, segment=args.segment, max_results=args.limit)
        key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
        def display(value):
            text = "Não disponível" if value is None or value == "" else str(value)
            return text.replace(key, "[REDACTED]") if key else text
        fields = (("Empresa", "empresa"), ("Segmento", "segmento"), ("Cidade", "cidade"),
                  ("Telefone", "telefone"), ("WhatsApp", "whatsapp"), ("Site", "site"),
                  ("Endereço", "endereco"), ("Avaliação", "avaliacao"), ("Qtd. avaliações", "quantidade_avaliacoes"),
                  ("Google Maps", "google_maps"), ("Place ID", "provider_place_id"),
                  ("Latitude", "latitude"), ("Longitude", "longitude"))
        for result in results:
            print("---")
            for label, field in fields:
                print(f"{label}: {display(getattr(result, field))}")
        print(f"Resultados recebidos: {len(results)}")
        print(f"Requests realizadas: {provider.request_count}")
        return 0
    except GooglePlacesError as error:
        print(friendly_error(error), file=sys.stderr)
    except Exception:
        print("Falha local: confira o ambiente, as dependências de desenvolvimento e o arquivo .env. Nenhum detalhe sensível foi exibido.", file=sys.stderr)
    if provider is not None:
        print(f"Requests realizadas: {provider.request_count}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
