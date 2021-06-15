#!/bin/python
import json
import sys
import glob
import argparse

COMPILE_COMMAND_DEFAULT = "compile_commands.json"


def find_compilation_databases(rootdir):
    return glob.glob(f'{rootdir}/**/' + COMPILE_COMMAND_DEFAULT, recursive=True)


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


if __name__ == "__main__":
    filter_compile_command("compile_commands.json")

