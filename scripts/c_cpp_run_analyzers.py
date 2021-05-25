#!/bin/python3
import glob
import logging
import pathlib
import sys
import json
import argparse
from datetime import datetime
from dotenv import load_dotenv

# sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from codechecker_interface import *
from testware_functions import *
SCRIPT_PATH = pathlib.Path(__file__).parent.absolute()
load_dotenv(f"{SCRIPT_PATH}/.env")
USER = os.getenv("HOME")
CPPCHECK_INSTALL_PATH = os.getenv("CPPCHECK_PATH")
INFER_INSTALL_PATH = os.getenv("INFER_PATH")

logging.basicConfig(filename='C_CPP.log', filemode='w', format='%(asctime)s %(message)s')
LOG = logging.getLogger("C_CPP")


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


parser = argparse.ArgumentParser(description='Run analysers')
parser.add_argument('--path', '-p', help='Path to run script on')
parser.add_argument('--recursive', '-r', help='run script on all folders in path',
                    type=str2bool, required=False, default=False)
parser.add_argument('--project-name', '-out',
                    help='If set, this is the base name used to store the runs in the framework',
                    required=False, default='')
parser.add_argument('--tools', '-t', help='A semicolon-separated list of the following analysis tools to run: ' +
                                          '{all, codechecker, codechecker_ctu, cppcheck, infer}',
                    required=False, default='all')
parser.add_argument('--only-tests', '-at', help='Whether analysis should only be run on tests',
                    type=str2bool, required=False, default=False)
parser.add_argument('--no-upload',
                    help='Set to true if you do not want to upload to framework (e.g. debugging of toolchain)',
                    type=str2bool, required=False, default=False)


def filter_compile_command(compile_command_path, filter_function=is_testware_translation_unit,
                           filtered_commands_path="compile_commands_filtered.json"):
    with open(compile_command_path, "r") as data:
        compile_commands = json.load(data)
        compile_commands_filtered = [comp for comp in compile_commands if filter_function(comp)]
        with open(filtered_commands_path, "w+") as outfile:
            outfile.write(json.dumps(compile_commands_filtered))


def run_cppcheck_on_compile_command(outdirpath, compile_command_database_path, project_name, is_ctu):
    result_folder = generate_analysis_output_folderpath(outdirpath, "cppcheck")
    # Since CppCheck does not create output folders automatically, we must make sure it exists
    subprocess.call(["mkdir", "-p", result_folder])
    return_code = subprocess.call([f"{CPPCHECK_INSTALL_PATH}/cppcheck", "--enable=all", "--inconclusive",
                               f"--project={compile_command_database_path}",  # compile commands to use
                               f"--plist-output={result_folder}"])  # output folder
    if return_code == 0:
        analysis_post_process(result_folder, "cppcheck", project_name)


def run_infer_on_compile_command(outdirpath, compile_command_database_path, project_name, is_ctu):
    result_folder = generate_analysis_output_folderpath(outdirpath, "infer")

    return_code = subprocess.call([f"{INFER_INSTALL_PATH}/infer", "run",
                               "-o", result_folder,  # output folder
                               "--compilation-database", compile_command_database_path])
    if return_code == 0:
        analysis_post_process(result_folder, "fbinfer", project_name)


def run_codechecker_on_compile_command(outdirpath, compile_command_database_path, project_name, is_ctu):
    result_folder_suffix = "_ctu" if is_ctu else ""
    result_folder = generate_analysis_output_folderpath(outdirpath, f"codechecker{result_folder_suffix}")
    codechecker_command = [CODECHECKER_MAINSCRIPT_PATH, "analyze", "-o", result_folder]

    # If we've defined a skipfile to use
    if CODECHECKER_SKIPFILE_PATH:
        codechecker_command.extend(["-i", CODECHECKER_SKIPFILE_PATH])
    if is_ctu:
        codechecker_command.append("--ctu-all")
    codechecker_command.append(compile_command_database_path)
    return_code = subprocess.call(codechecker_command)
    if return_code == 0:
        print("CodeChecker run completed\n")
        if is_ctu:
            print("Ran in CTU mode\n")
        store_to_codechecker(result_folder, project_name)
    else:
        logging.debug("Unable to run the following CodeChecker command: " + str(codechecker_command))


def run_tools_on_compile_command(compcommand_path, runners_and_ctuflag_pair, project_name, on_testware_only=True):
    """Given a list of (possibly CTU-based) tools, run all tools on @compcommand_path"""
    # Do filtering of compile command to only include testware
    compcom_dirpath, compcomname = os.path.split(compcommand_path)
    new_compile_command_file = f"{compcom_dirpath}/testware_{compcomname}"
    filter_compile_command(compcommand_path, is_testware_translation_unit, new_compile_command_file)

    for runner, is_ctu in runners_and_ctuflag_pair:
        # Check if it's a CTU analysis, 
        # if so we should include all the build files for the AST generation step
        # Otherwise, run it with the filtered one
        command_file_to_use = compcommand_path if (is_ctu or not on_testware_only) else new_compile_command_file
        runner(compcom_dirpath, command_file_to_use, project_name, is_ctu)


analyzer_mapping = {
    'codechecker': (run_codechecker_on_compile_command, False),
    'codechecker_ctu': (run_codechecker_on_compile_command, True),
    'cppcheck': (run_cppcheck_on_compile_command, False),
    'infer': (run_infer_on_compile_command, False)
}


def get_all_c_cpp_analyzers():
    return [analyzer for name, analyzer in analyzer_mapping.items()]


def get_analyzers_to_run(analyzer_string_list):
    def analyze_map(analyzer):
        return analyzer_mapping.get(analyzer, None)

    # Figure out from the passed list of strings what tools we want to run
    res_list = []
    if not analyzer_string_list or analyzer_string_list[0] == "all":
        return get_all_c_cpp_analyzers()
    else:
        res_list = analyzer_string_list
    return [analyze_map(f) for f in res_list]


# Assumes that there is a file with compile commands somewhere in the project
def run_analyzers_on_project(proj_path, analyzers_to_run):
    # If script user has set specific project name, override the one grabbed from path
    project_name = args.project_name if bool(args.project_name) else os.path.basename(proj_path)

    # prefer the manually generated compile command file to the one autogenerated by e.g. CMake
    # Reasonably, if both exist, something was lacking in the first one
    autogenerated_build_commands = glob.glob(f"{proj_path}/**/compile_commands.json", recursive=True)
    logged_build_commands = glob.glob(f"{proj_path}/**/com.json", recursive=True)
    run_commands = logged_build_commands if logged_build_commands else autogenerated_build_commands

    if run_commands:
        for logs in run_commands:
            run_tools_on_compile_command(logs, analyzers_to_run, project_name, args.only_tests)
    else:
        print(f"No build commands found by runner script for project {proj_path}.")


if __name__ == "__main__":
    args = parser.parse_args()
    os.chdir(args.path)
    tools_list = args.tools.split(";")
    tools = [t for t in get_analyzers_to_run(tools_list) if t is not None]
    dirs = [args.path]
    if args.recursive:
        dirs = [os.path.abspath(d) for d in next(os.walk(args.path))[1]]
    for d in dirs:
        print("Running analyzers on " + d)
        run_analyzers_on_project(d, tools)
