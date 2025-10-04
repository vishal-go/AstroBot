from src.telegram.bot import run_bot
from src.utils.logger import logger as log

if __name__ == "__main__":
    log.info("Starting AstroBot...")
    run_bot()
    log.info("AstroBot app triggered.")