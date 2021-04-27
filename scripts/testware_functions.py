import ntpath
import glob

from enum import Enum


class TestTypes(Enum):
    NO_TEST = 0,
    TESTCASE = 1,
    TESTLIB = 2


def get_test_files(rootdir, recursive=True, ext=""):
    file_ext = "*" if ext == "" else ext
    return glob.glob(f"{rootdir}/**/*test*.{file_ext}", recursive=recursive)


def classify_potential_testfile(compile_command_entry):
    f_dir, name = ntpath.split(str(compile_command_entry["file"]))
    if "test" in name.lower():
        return TestTypes.TESTCASE
    elif "test" in f_dir.lower():
        return TestTypes.TESTLIB
    else:
        return TestTypes.NO_TEST


def is_testware_translation_unit(compile_command_entry):
    return classify_potential_testfile(compile_command_entry) != TestTypes.NO_TEST


def is_testcase_translation_unit_coarse(compile_command_entry):
    return classify_potential_testfile(compile_command_entry) == TestTypes.TESTCASE


def is_test_framework_file_coarse(compile_command_entry):
    return classify_potential_testfile(compile_command_entry) == TestTypes.TESTLIB


def is_testcase_translation_unit_finegrained(compile_command_entry):
    test_strings = ["assert", "equals", "test", "unit"]
    with open(str(compile_command_entry["file"]), "r") as content:
        content_lowercase = content.read()
        for ts in test_strings:
            if ts in content_lowercase:
                return True
    return False
