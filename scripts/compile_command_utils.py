#!/bin/python
import json
import sys
import glob
import argparse

COMPILE_COMMAND_DEFAULT = "compile_commands.json" # In case they may be separated
def find_compilation_databases(rootdir):
    return glob.glob('*/**/' + COMPILE_COMMAND_DEFAULT, recursive=True)

def is_testware_translation_unit(compile_command_entry):
    return ("test" in str(compile_command_entry["directory"]).lower() or 
            "test" in str(compile_command_entry["file"]).lower())

def filter_compile_command(compile_command_path, stripped_compile_commands_path = "compile_commands_filtered.json"):
    with open(compile_command_path, "r") as data:
        ccom = json.load(data)
        ccom_testware = list(filter(is_testware_translation_unit, ccom))
        with open(stripped_compile_commands_path, "w+") as outfile:
            outfile.write(json.dumps(ccom_testware))



if __name__ == "__main__":
    filter_compile_command("compile_commands.json")

