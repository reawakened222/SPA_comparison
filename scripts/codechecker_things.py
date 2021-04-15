import os
import subprocess
HOME = os.environ["HOME"]
CODECHECKER_BIN_PATH = f"{HOME}/codechecker/build/CodeChecker/bin/"
CODECHECKER_RESULTCONVERTER_PATH = f"${CODECHECKER_BIN_PATH}report-converter"
CODECHECKER_SKIPFILE_PATH = os.environ["CCHECKER_SKIPNONTESTSFILE"]


def store_to_codechecker(result_path, store_project_name):
    return subprocess.run(["CodeChecker", "store", result_path, "--name",
                           store_project_name]).returncode == 0


def convert_and_store_to_codechecker(analysis_outputpath, codechecker_outputpath,
                                     analyzer, project_name, store_name_suffix=""):
    res = subprocess.run([CODECHECKER_RESULTCONVERTER_PATH, "-t",
                         analyzer, "-o", codechecker_outputpath, analysis_outputpath])
    if res.returncode != 0:
        return False
    return store_to_codechecker(codechecker_outputpath, f'"{project_name}_{analyzer}{store_name_suffix}"')