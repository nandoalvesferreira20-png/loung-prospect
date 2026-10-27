"""Explicit backend launcher. Does not implicitly read or change any .env file."""
import argparse
from pathlib import Path
import uvicorn
from dotenv import load_dotenv
from backend.config import Settings


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',type=Path,required=True,help='Explicit server configuration file (never sent to browser)')
    parser.add_argument('--port',type=int,default=8000)
    args=parser.parse_args(argv)
    if not args.env_file.is_file():parser.error('Arquivo de ambiente não encontrado.')
    load_dotenv(args.env_file.resolve(), override=False, interpolate=False)
    try:
        settings = Settings.from_environment()
    except ValueError as error:
        parser.error(str(error))
    if settings.storage_backend == 'sqlite':
        import os
        missing = [key for key in ('GOOGLE_PLACES_API_KEY', 'GROQ_API_KEY') if not os.environ.get(key)]
        if missing:
            print('Integrações ainda não configuradas: ' + ', '.join(missing) + '. CRM local continua disponível.')
    uvicorn.run('backend.main:app',env_file=str(args.env_file.resolve()),host='127.0.0.1',port=args.port,proxy_headers=False)
if __name__=='__main__':main()
