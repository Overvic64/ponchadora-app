from pathlib import Path


APP_NAME = "Ponchadora Control"
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "database.db"
OUTPUT_DIR = DATA_DIR / "reportes"
PRIMARY_COLOR = "#00875A"
PRIMARY_HOVER_COLOR = "#006B47"
ACCENT_COLOR = "#4CAF50"
ACCENT_DARK_COLOR = "#2E7D32"
BG_COLOR = "#F8F9FA"
SURFACE_COLOR = "#FFFFFF"
SURFACE_ALT_COLOR = "#F0F7F2"
TEXT_COLOR = "#212121"
MUTED_TEXT_COLOR = "#66736B"
ERROR_COLOR = "#B3261E"
DEDUPLICATION_WINDOW_SECONDS = 300
SCHEDULED_ENTRY_TIME = "08:10"
ENTRY_TOLERANCE_MINUTES = 10
REQUIRED_COLUMNS = (
	"Data e Hora (Logs de Acesso)",
	"Código (Usuário)",
	"Nome (Usuário)",
)


def ensure_directories() -> None:
	DATA_DIR.mkdir(parents=True, exist_ok=True)
	OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
