import itertools

from codechecker_interface import *
from codechecker_common.plist_parser import parse_plist_file
import os
import pathlib
import re
from typing import List, Dict, Tuple
from codechecker_common.report import Report


def prettify(dir_name):
    _dir = os.path.basename(dir_name)
    if _dir.startswith("codechecker_ctu"):
        return "CodeChecker (CTU Mode)"
    elif _dir.startswith("codechecker"):
        return "CodeChecker"
    elif _dir.startswith("cppcheck"):
        return "CppCheck"
    elif _dir.startwith("infer"):
        return "FB Infer"
    elif _dir.startswith("spotbugs"):
        return "SpotBugs"
    return "Unrecognized"


def get_plist_reports_tool_pair(plist_result_dir) -> Tuple[Dict[int, str], List[Report]]:
    """
    Extracts the tool name and the reports from a report directory
    """
    dir_name = os.path.basename(plist_result_dir)
    tool_name = re.match("(.*?)_result.*", dir_name).group(1)
    plist_files = [filepath.absolute() for filepath in pathlib.Path(plist_result_dir).glob('./*.plist')]
    plist_reports = list(map(parse_plist_file, plist_files))
    plist_reports_remove_empties = list(filter(lambda e: len(e[1]) > 0, plist_reports))
    return plist_reports_remove_empties, tool_name


def get_potential_report_duplicates(plist_result_directories):
    """
    Given a list of plist report directories
    map it to a (plist reports, tool) pair
    Extract main file name for each report => build a hashset with filename key and parsed reports as values
    """
    plist_reports_tool_map = list(map(get_plist_reports_tool_pair, plist_result_directories))
    reports_key_val_map = {}
    for files_reports_list, tool_run in plist_reports_tool_map:
        # files_reports_list is a list of files, report list pairs
        for files, reports in files_reports_list:
            # And finally, we get access to the report itself.
            # Note, we use the filepath property to get the path to the main file
            # This is not necessarily the file with index 0, so we cannot simply append the entire list :(
            for report in reports:
                report_main_file = report.file_path
                if report_main_file not in reports_key_val_map:
                    reports_key_val_map[report_main_file] = []
                reports_key_val_map[report_main_file].append((report, tool_run))
    return reports_key_val_map


def run_on_project_result(project_report_path):
    result_directories = [filepath.absolute() for filepath in pathlib.Path(project_report_path).glob('./*results*')]
    return get_potential_report_duplicates(result_directories)


if __name__ == "__main__":
    run_on_project_result("./tests/plist")