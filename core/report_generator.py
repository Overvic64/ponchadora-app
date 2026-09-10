from pathlib import Path

from .attendance_engine import CleaningResult


def export_reports(result: CleaningResult, output_directory: str | Path, base_name: str) -> tuple[Path, Path]:
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    cleaned_path = directory / f"{base_name}_Ponchadas_Depuradas.xlsx"
    summary_path = directory / f"{base_name}_Entradas_y_Salidas.xlsx"
    result.cleaned[["codigo", "nombre", "fecha_hora"]].to_excel(cleaned_path, index=False)
    result.daily_summary.to_excel(summary_path, index=False)
    return cleaned_path, summary_path