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
from framework_utils import *
from compile_command_utils import *
logging.basicConfig(filename='PYTHON.log', filemode='w', format='%(asctime)s %(message)s')
LOG = logging.getLogger("PYTHON")

PYTHON_VENV_BASE_NAME = "venv"

parser = get_framework_args('python')


def run_pylama_on_project(outdirpath, project_path, project_name):
    result_folder = generate_analysis_output_folderpath(outdirpath, "pylama")
    pylama_invocation = ["pylama", "--format", "pylint",
                         "--force", "--report", f"{result_folder}/pylama_results"
                                                "--abspath", project_path]
    result = time_invocation_log('python', 'pylama', pylama_invocation)  # output folder
    if result.returncode == 0:
        # We use pylint output format, which framework can already parse
        analysis_post_process(result_folder, "pylint", project_name)
    else:
        LOG.error()


def run_pyre_on_project(outdir_path, project_path, project_name):
    result_folder = generate_analysis_output_folderpath(outdir_path, "pyre")
    pyre_invocation = ["pyre", "--source-directory", project_path]
    venv_dir = glob.glob(f"**/{PYTHON_VENV_BASE_NAME}", recursive=True)
    # Include local virtual environment for module includes
    if venv_dir and len(venv_dir) == 1:
        pyre_invocation.extend(["--search-path", pathlib.Path(venv_dir[0]).absolute()])
    pyre_invocation.extend(["--output", "json", "--noninteractive", "check"])
    result = time_invocation_log('python', 'pyre', pyre_invocation)

    if result.returncode == 0:
        analysis_post_process(result_folder, "pyre", project_name)
    else:
        LOG.error("Pyre had an error for project " + project_name)
        LOG.error(result.stderr.decode('utf-8'))


# Assumes that there is a file with compile commands somewhere in the project
def run_analyzers_on_project(proj_path):
    project_name = os.path.basename(proj_path)
    run_pylama_on_project(proj_path, proj_path, project_name)
    run_pyre_on_project(proj_path, proj_path, project_name)


if __name__ == "__main__":
    args = parser.parse_args()
    if not os.path.isdir(args.path):
        print(f"Invalid project path {args.path}.")
        exit(1)
    os.chdir(args.path)
    # Run tools on all projects
    # 1) Loop through all directories in current working directory
    # 2) get their basename, will be needed for CodeChecker storing later
    # 3) invoke run_* on project
    if not args.recursive:
        run_analyzers_on_project(os.path.abspath(args.path))
    else:
        dirs = next(os.walk(args.path))[1]
        for d in dirs:
            run_analyzers_on_project(os.path.abspath(d))
