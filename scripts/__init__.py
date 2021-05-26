import pathlib
from typing import List, Dict, Tuple
from dotenv import load_dotenv
SCRIPT_PATH = pathlib.Path(__file__).parent.absolute()
env_conf = pathlib.Path(f"{SCRIPT_PATH}/.env")
if env_conf.exists() and env_conf.is_file():
    load_dotenv(f"{SCRIPT_PATH}/.env")