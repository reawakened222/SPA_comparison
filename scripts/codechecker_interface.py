import os
import subprocess
import sys
from datetime import datetime
from dotenv import load_dotenv
import pathlib
SCRIPT_PATH = pathlib.Path(__file__).parent.absolute()
env_conf = pathlib.Path(f"{SCRIPT_PATH}/.env")
if env_conf.exists() and env_conf.is_file():
    load_dotenv(f"{SCRIPT_PATH}/.env")

USER = os.getenv("HOME")

CODECHECKER_PATH = f"{USER}/codechecker"
CODECHECKER_SCRIPTS_DIR = f"{CODECHECKER_PATH}/codechecker-common"
CODECHECKER_BIN_PATH = f"{CODECHECKER_PATH}/build/CodeChecker/bin/"
CODECHECKER_RESULTCONVERTER_PATH = f"{CODECHECKER_BIN_PATH}report-converter"
CODECHECKER_MAINSCRIPT_PATH = f"{CODECHECKER_BIN_PATH}/CodeChecker"
CODECHECKER_SKIPFILE_PATH = f"{USER}/spa_comparison/C_Cpp/codechecker_skipfile"
sys.path.extend(CODECHECKER_SCRIPTS_DIR)

CODECHECKER_SERVER_ADDRESS = os.getenv("CODECHECKER_SERVER_ADDRESS", "localhost:8001")


def store_to_codechecker(result_path, store_project_name, store_server_product="Default"):
    """Simple wrapper around CodeChecker store command,
    allowing to set name of the run (project name)
    and which product on the server to store results to."""
    return subprocess.run([CODECHECKER_MAINSCRIPT_PATH, "store", result_path,
                           "--name", store_project_name,
                           "--url", f"{CODECHECKER_SERVER_ADDRESS}/{store_server_product}"]).returncode == 0

def gen_convert_to_codechecker_command(analysis_output, analyzer_name, converted_output):
    return [CODECHECKER_RESULTCONVERTER_PATH, "-t",
            analyzer_name, "-o", converted_output, analysis_output]


def convert_and_store_to_codechecker(analysis_outputpath, codechecker_outputpath,
                                     analyzer, project_name, store_name_suffix="", server_product_name="Default"):
    res = subprocess.run(gen_convert_to_codechecker_command(analysis_outputpath, analyzer, codechecker_outputpath))
    if res.returncode != 0:
        return False
    return store_to_codechecker(codechecker_outputpath,
                                f'"{project_name}_{analyzer}{store_name_suffix}"',
                                server_product_name)


def analysis_post_process(result_folder, tool_name, project_name, server_product_name="Default"):
    """For tools that need to do post-processing on results before submitting to the framework"""

    converted_result_folder = os.path.join(result_folder, tool_name + "_results_converted")
    return convert_and_store_to_codechecker(result_folder, converted_result_folder, tool_name,
                                            project_name, server_product_name)


def generate_analysis_output_folderpath(base_path, tool_name, generate_folder=True):
    now = datetime.now()
    analysis_starttime = now.strftime("%Y_%m_%d_%H_%M_%S")
    analysis_output = f"{base_path}/{tool_name}_results_{analysis_starttime}"
    if generate_folder:
        subprocess.call(["mkdir", "-p", analysis_output])
    return analysis_output