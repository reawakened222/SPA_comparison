import glob
import logging
import os
import pathlib
import subprocess
import sys
import json
import argparse
from datetime import datetime

# sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from codechecker_interface import *
from testware_functions import *

logging.basicConfig(filename='PYTHON.log', filemode='w', format='%(asctime)s %(message)s')
LOG = logging.getLogger("PYTHON")

ON_TESTCODE_ONLY = False
PYTHON_VENV_BASE_NAME = "venv"


def filter_compile_command(compile_command_path, filtered_commands_path="compile_commands_filtered.json"):
    with open(compile_command_path, "r") as data:
        compile_commands = json.load(data)
        compile_commands_filtered = list(filter(is_testware_translation_unit, compile_commands))
        with open(filtered_commands_path, "w+") as outfile:
            outfile.write(json.dumps(compile_commands_filtered))





def run_pylama_on_project(outdirpath, project_path, project_name):
    result_folder = generate_analysis_output_folderpath(outdirpath, "pylama")
    pylama_invocation = ["pylama", "--format", "pylint",
                         "--force", "--report", f"{result_folder}/pylama_results"
                                                "--abspath", project_path]
    retcode = subprocess.call(pylama_invocation)  # output folder
    if retcode == 0:
        # We use pylint output format, which framework can already parse
        analysis_postprocess(result_folder, "pylint", project_name)


def run_pyre_on_project(outdir_path, project_path, project_name):
    result_folder = generate_analysis_output_folderpath(outdir_path, "pyre")
    pyre_invocation = ["pyre", "--source-directory", project_path]
    venv_dir = glob.glob(f"**/{PYTHON_VENV_BASE_NAME}", recursive=True)
    # Include local virtual environment for module includes
    if venv_dir and len(venv_dir) == 1:
        pyre_invocation.extend(["--search-path", pathlib.Path(venv_dir[0]).absolute()])
    pyre_invocation.extend(["--output", "json", "--noninteractive", "check"])
    retcode = subprocess.call(pyre_invocation, capture_output=True)

    if retcode == 0:
        analysis_postprocess(result_folder, "pyre", project_name)

    else:
        LOG.error("Pyre had an error for project " + project_name)
        LOG.error(str(retcode.stderr))


# Assumes that there is a file with compile commands somewhere in the project
def run_analyzers_on_project(proj_path):
    project_name = os.path.basename(proj_path)
    run_pylama_on_project(proj_path, proj_path, project_name)
    run_pyre_on_project(proj_path, proj_path, project_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run analysers')
    parser.add_argument('--projpath', '-p', help='Project to run script on')
    parser.add_argument('--single-project', '-sp', help='run toolchain in single project mode', required=False,
                        default=True)
    parser.add_argument('--analyse-only-tests', '-at', help='Whether analysis should only be run on tests',
                        required=False, default=False)

    args = parser.parse_args()
    ON_TESTCODE_ONLY = args.analyse_only_tests
    os.chdir(args.projpath)
    # Run tools on all projects
    # 1) Loop through all directories in current working directory
    # 2) get their basename, will be needed for CodeChecker storing later
    # 3) invoke run_* on project
    if args.single_project:
        run_analyzers_on_project(os.path.abspath(args.projpath))
    else:
        dirs = next(os.walk(args.projpath))[1]
        for d in dirs:
            run_analyzers_on_project(os.path.abspath(d))
