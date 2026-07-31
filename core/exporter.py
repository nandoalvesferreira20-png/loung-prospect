from pathlib import Path
import os


def export_excel(df, output, log=print):
    """
    Exporta o DataFrame para Excel e retorna o caminho do arquivo.
    """

    output_path = Path(output)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    try:
        df.to_excel(output_path, index=False)

        log(f"📄 Excel salvo em:")
        log(str(output_path.resolve()))

        return output_path

    except Exception as error:

        log(f"❌ Erro ao exportar Excel:")
        log(str(error))

        raise


def open_excel(path):
    """
    Abre o arquivo Excel.
    """

    try:
        os.startfile(Path(path))

    except Exception as error:
        raise RuntimeError(
            f"Não foi possível abrir o Excel.\n{error}"
        )


def open_folder(path):
    """
    Abre a pasta onde o arquivo foi salvo.
    """

    try:
        os.startfile(Path(path).parent)

    except Exception as error:
        raise RuntimeError(
            f"Não foi possível abrir a pasta.\n{error}"
        )