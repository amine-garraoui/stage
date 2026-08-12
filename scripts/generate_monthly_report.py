from argparse import ArgumentParser
from pathlib import Path
import logging
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import kpi
from core.config import load_config, resolve_path, setup_logging
from core.service import load_dataset
from reports.excel import export_month_excel
from reports.pdf import export_month_pdf


LOGGER = logging.getLogger(__name__)


def main() -> None:
    parser = ArgumentParser(description="Generate monthly RSI KPI reports.")
    parser.add_argument("--month", dest="month", help="Month in YYYY-MM format. Defaults to latest month.")
    args = parser.parse_args()

    setup_logging()
    config = load_config()
    df = load_dataset(config)
    month = args.month or kpi.available_months(df)[-1]
    exports_dir = resolve_path(config.data.exports_dir) or Path("data/exports")

    pdf_path = export_month_pdf(df, month, exports_dir, config.company_name)
    excel_path = export_month_excel(df, month, exports_dir)
    LOGGER.info("Generated PDF: %s", pdf_path)
    LOGGER.info("Generated Excel: %s", excel_path)


if __name__ == "__main__":
    main()
