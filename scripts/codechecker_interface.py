import os
import subprocess
import sys
HOME = os.environ["HOME"]

CODECHECKER_PATH = f"{HOME}/codechecker"
CODECHECKER_SCRIPTS_DIR = f"{CODECHECKER_PATH}/codechecker-common"
CODECHECKER_BIN_PATH = f"{CODECHECKER_PATH}/build/CodeChecker/bin/"
CODECHECKER_RESULTCONVERTER_PATH = f"{CODECHECKER_BIN_PATH}report-converter"
CODECHECKER_MAINSCRIPT_PATH = f"{CODECHECKER_BIN_PATH}/CodeChecker"
CODECHECKER_SKIPFILE_PATH = f"{HOME}/spa_comparison/C_Cpp/codechecker_skipfile"
sys.path.extend(CODECHECKER_SCRIPTS_DIR)


def store_to_codechecker(result_path, store_project_name):
    return subprocess.run([CODECHECKER_MAINSCRIPT_PATH, "store", result_path, "--name",
                           store_project_name]).returncode == 0


def convert_and_store_to_codechecker(analysis_outputpath, codechecker_outputpath,
                                     analyzer, project_name, store_name_suffix=""):
    res = subprocess.run([CODECHECKER_RESULTCONVERTER_PATH, "-t",
                         analyzer, "-o", codechecker_outputpath, analysis_outputpath])
    if res.returncode != 0:
        return False
    return store_to_codechecker(codechecker_outputpath, f'"{project_name}_{analyzer}{store_name_suffix}"')


def analysis_postprocess(result_folder, tool_name, project_name):
    """For tools that need to do post-processing on results before submitting to the framework"""

    converted_result_folder = os.path.join(result_folder, tool_name + "_results_converted")
    return convert_and_store_to_codechecker(result_folder, converted_result_folder, tool_name, project_name)


def generate_analysis_output_folderpath(base_path, tool_name, generate_folder=True):
    now = datetime.now()
    analysis_starttime = now.strftime("%Y_%m_%d_%H_%M_%S")
    analysis_output = f"{base_path}/{tool_name}_results_{analysis_starttime}"
    if generate_folder:
        subprocess.call(["mkdir", "-p", analysis_output])
    return analysis_output