#!/bin/python3
import shutil
import logging
import pathlib
import subprocess
import sys
import json
import argparse
from datetime import datetime
import analyzers

# sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from analyzers.cppcheck import CppCheck
from codechecker_interface import *
from testware_functions import *
USER = os.getenv("HOME")
CPPCHECK_PATH = os.getenv("CPPCHECK_PATH", shutil.which("cppcheck"))
INFER_PATH = os.getenv("INFER_PATH", shutil.which("infer"))

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
parser.add_argument('--server-product',
                    help='Set which product collection to upload to within the framework',
                    required=False, default="Default")


def make_filtered_compile_command(compile_command_path, filter_function=is_testware_translation_unit,
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
    return_code = subprocess.call([CPPCHECK_PATH, "--enable=all", "--inconclusive",
                               f"--project={compile_command_database_path}",  # compile commands to use
                               f"--plist-output={result_folder}"])  # output folder
    if return_code == 0:
        analysis_post_process(result_folder, "cppcheck", project_name, args.server_product)


def run_infer_on_compile_command(outdirpath, compile_command_database_path, project_name, is_ctu):
    result_folder = generate_analysis_output_folderpath(outdirpath, "infer")

    return_code = subprocess.call([INFER_PATH, "run",
                               "-o", result_folder,  # output folder
                               "--compilation-database", compile_command_database_path])
    if return_code == 0:
        analysis_post_process(result_folder, "fbinfer", project_name, args.server_product)


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
        store_to_codechecker(result_folder, project_name, args.server_product)
    else:
        logging.debug("Unable to run the following CodeChecker command: " + str(codechecker_command))


def generate_test_compile_commands(original_commands_path):
    compcom_dirpath, compcomname = os.path.split(original_commands_path)
    new_compile_command_file = f"{compcom_dirpath}/testware_{compcomname}"
    make_filtered_compile_command(original_commands_path, is_testware_translation_unit, new_compile_command_file)
    return new_compile_command_file


def run_tools_on_compile_command(compcommand_path, runners_and_ctuflag_pair, project_name, on_testware_only=True):
    """Given a list of (possibly CTU-based) tools, run all tools on @compcommand_path"""
    compcom_dirpath, compcomname = os.path.split(compcommand_path)
    # Do filtering of compile command to only include testware
    # TODO: Fix horrible naming of variables
    command_file_to_use = compcommand_path
    if on_testware_only:
        command_file_to_use = generate_test_compile_commands(compcommand_path)
    for runner, is_ctu in runners_and_ctuflag_pair:
        # Check if it's a CTU analysis, 
        # if so we should include all the build files for the AST generation step
        # Otherwise, run it with the filtered one
        command_file_to_use = compcommand_path if is_ctu else command_file_to_use
        runner(compcom_dirpath, command_file_to_use, project_name, is_ctu)


def run_tools_on_project_oop_style(target_path, analyzers, project_name):
    for analyzer in analyzers:
        final_result_path = ""  # Path to final result (either from analysis or from post-conversion)
        analyzer_invocation_commands, analysis_path = \
            analyzer.gen_analysis_command_wrapper(target_path, project_name)
        # Run analysis
        for invocation in analyzer_invocation_commands:
            subprocess.run(invocation)
        # Figure out conversion
        if analyzer.conversion_required:
            conversion_commands, final_result_path = \
                analyzer.get_conversion_commands(analysis_path)
            subprocess.run(conversion_commands)
        else:
            final_result_path = analysis_path
        if not args.no_upload:
            store_to_codechecker(final_result_path, analyzer.get_analysis_run_name(project_name), args.server_product)






analyzer_mapping = {
    'codechecker': (run_codechecker_on_compile_command, False),
    'codechecker_ctu': (run_codechecker_on_compile_command, True),
    'cppcheck': (run_cppcheck_on_compile_command, False),
    'infer': (run_infer_on_compile_command, False)
}
analyzer_mapping_v2 = {
    'codechecker': (run_codechecker_on_compile_command, False),
    'codechecker_ctu': (run_codechecker_on_compile_command, True),
    'cppcheck': analyzers.cppcheck.CppCheck(),
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
