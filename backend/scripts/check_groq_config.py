"""Offline configuration report. Never contacts Groq or prints credential values."""
import argparse
import json
import os
from pathlib import Path
import re
from dotenv import dotenv_values


def report(path):
    values=dotenv_values(path,interpolate=False)
    names=('GROQ_API_KEY','GROQ_MODEL','GROQ_TIMEOUT','LOUNG_AUTH_MODE','LOUNG_STORAGE_BACKEND')
    effective={key:os.environ.get(key,values.get(key)) for key in names}
    model=effective['GROQ_MODEL'] or ''
    return {
        'networkUsed':False,
        'keyPresent':bool((effective['GROQ_API_KEY'] or '').strip()),
        'model':model if re.fullmatch(r'(?!gsk_)[a-zA-Z0-9][\w./:-]{0,119}',model) else '(ausente ou formato invalido)',
        'timeoutConfigured':bool(effective['GROQ_TIMEOUT']),
        'modeIsLocal':effective['LOUNG_AUTH_MODE'] in (None,'local'),
        'storageIsSQLite':effective['LOUNG_STORAGE_BACKEND'] in (None,'sqlite'),
        'sources':{key:'process' if key in os.environ else 'env-file' if key in values else 'default/missing' for key in names},
        'processDiffersFromFile':{key:os.environ[key]!=values[key] for key in names if key in os.environ and key in values},
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',required=True,type=Path)
    args=parser.parse_args()
    if not args.env_file.is_file():parser.error('Arquivo de ambiente nao encontrado.')
    print(json.dumps(report(args.env_file),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
