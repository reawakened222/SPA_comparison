#!/bin/python
import json
import pathlib
import subprocess
import sys
import glob
import argparse
from line_of_code_counter import LoCData, CLOC_BIN
COMPILE_COMMAND_DEFAULT = "compile_commands.json"
import argh

def find_compilation_databases(rootdir):
    res = glob.glob(f'{rootdir}/**/' + COMPILE_COMMAND_DEFAULT, recursive=True)
    if __name__ == "__main__":
        for r in res:
            print(r)
    else:
        return res


def is_testware_translation_unit(compile_command_entry):
    return ("test" in str(compile_command_entry["directory"]).lower() or 
            "test" in str(compile_command_entry["file"]).lower())


def filter_compile_command(compile_command_path,
                           filter_func=is_testware_translation_unit,
                           stripped_compile_commands_path="compile_commands_filtered.json"):
    with open(compile_command_path, "r") as data:
        ccom = json.load(data)
        ccom_filtered = list(filter(filter_func, ccom))
        with open(stripped_compile_commands_path, "w+") as outfile:
            outfile.write(json.dumps(ccom_filtered))

def get_files_for_counting(compile_command_filepath, filter=None):
    """
    Given a compile command, returns the number of lines.
    If a filter is provided, the function returns a tuple where the first element are line counts from entries that match the filter
    and second are from entries that do not.
    If no filter is provided, the second entry will always be 0
    """
    filter_true = []
    filter_false = []
    comp_commands = json.load(open(compile_command_filepath, "r"))
    if filter:
        filter_true = [(cc['directory'], cc['file']) for cc in comp_commands if filter(cc)]
        filter_false = [(cc['directory'], cc['file']) for cc in comp_commands if not filter(cc)]
    else:
        filter_true = [(cc['directory'], cc['file']) for cc in comp_commands]
    return filter_true, filter_false

def generate_clocscript_from_comp_command(comp_command, script_output_dir):
    testware, productioncode = get_files_for_counting(comp_command, is_testware_translation_unit)
    production_set = set([f if pathlib.Path(f).exists() else f'{d}/{f}' for d, f in productioncode])
    test_set = set([f if pathlib.Path(f).exists() else f'{d}/{f}' for d, f in testware])
    subprocess.run(['mkdir', '-p', script_output_dir])
    with open(f"{script_output_dir}/cloc_runner.sh", "w") as f:
        f.write(f"#!/bin/bash\n# Generated from file: {comp_command}\n")
        f.write(f'{CLOC_BIN}/cloc --xml --quiet \\\n')
        for file in production_set:
            f.write(f"\t{file} \\\n")
        f.write("\tDUMMY.html > production_LoC.txt\n\n")

        f.write(f'{CLOC_BIN}/cloc --xml --quiet \\\n')
        for file in test_set:
            if pathlib.Path(file).exists():
                f.write(f"\t{file} \\\n")
        f.write("\tDUMMY.html > testware_LoC.txt")


parser = argh.ArghParser()
parser.add_commands([generate_clocscript_from_comp_command, find_compilation_databases])

if __name__ == "__main__":
    argh.dispatch(parser)

