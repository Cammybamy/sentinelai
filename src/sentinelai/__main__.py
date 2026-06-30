import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

from sentinelai.ui.tray import run

if __name__ == "__main__":
    llm_model = sys.argv[1] if len(sys.argv) > 1 else "llama3:latest"
    run(llm_model=llm_model)
