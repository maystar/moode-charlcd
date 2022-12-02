import logging
import os

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"),
                    format='%(asctime)s: %(levelname)s [%(name)s] %(message)s')
