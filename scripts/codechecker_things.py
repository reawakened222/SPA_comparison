import os
import subprocess
USER = os.environ["HOME"]
CODECHECKER_BIN_PATH = f"{USER}/codechecker/build/CodeChecker/bin/"
CODECHECKER_RESULTCONVERTER_PATH = f"${CODECHECKER_BIN_PATH}report-converter"

def store_to_codechecker(analysis_outputpath, codechecker_outputpath, analyzer, project_name, conversion_required=True, store_name_suffix=""):
    if(conversion_required):
        res = subprocess.run([CODECHECKER_RESULTCONVERTER_PATH, "-t", 
        analyzer, "-o", codechecker_outputpath, analysis_outputpath])
    if(conversion_required and res.returncode != 0):
        return False
    return subprocess.run(["CodeChecker", "store", "--name", f'"{project_name}_{analyzer}{store_name_suffix}"']).returncode == 0