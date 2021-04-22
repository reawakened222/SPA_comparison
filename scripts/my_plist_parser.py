import itertools

from codechecker_interface import *
from codechecker_common.plist_parser import parse_plist_file
import os
import pathlib
import re
from typing import List, Dict, Tuple
from codechecker_common.report import Report
from enum import Enum


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


def collapse_reports_toolpair_list(reports_tool_list: List[Tuple[Report, str]]) -> List[Tuple[List[Report], str]]:
    """
    Given a list of (report, checktool) pairs, it returns the corresponding (List[Report], checktool) list
    """
    if not reports_tool_list:
        return []
    else:
        current_tool = reports_tool_list[0][1]
        tmp = list(map(lambda e: e[0],
                       filter(lambda res_tool_pair: current_tool == res_tool_pair[1], reports_tool_list)))
        tmp.sort(key=lambda r: r.line)  # Make sure reports are sorted by line
        rest = list(filter(lambda res_tool_pair: current_tool != res_tool_pair[1], reports_tool_list))
        return [(tmp, current_tool)] + collapse_reports_toolpair_list(rest)


def get_reports_per_file(plist_result_directories):
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
            # This is not necessarily the file with index 0, so we cannot simply append the entire list
            for report in reports:
                report_main_file = report.file_path
                if report_main_file not in reports_key_val_map:
                    reports_key_val_map[report_main_file] = []
                reports_key_val_map[report_main_file].append((report, tool_run))

    collapsed_reports_tool_pair = dict(map(lambda e: (e[0], collapse_reports_toolpair_list(e[1])),
                                           reports_key_val_map.items()))

    return collapsed_reports_tool_pair

class DuplicateRelations(Enum):
    NO_DUPLICATE = 0,
    SUBSUMPTION = 1,
    POTENTIAL_DUPLICATE = 2

def is_duplicate(w1 : Report,w2 : Report, col_distance = 0,row_distance = 0) -> DuplicateRelations:
    # 1) Warning originates in the same file - done already, remove this check to save effort
    # 1a) Warning/Checker is identical: Duplicate (potential CTU vs non-CTU run)
    # 2) Warning originates on the same line
    if abs(w1.line - w2.line) > row_distance:
        return DuplicateRelations.NO_DUPLICATE
    if w1.check_name == w2.check_name:
        return DuplicateRelations.SUBSUMPTION
    else:
        return DuplicateRelations.NO_DUPLICATE if abs(w1.col - w2.col) > col_distance else DuplicateRelations.POTENTIAL_DUPLICATE


def mark_potential_duplicates(reports_tool_list):
    """Group potential duplicate reports based on heuristics
    """

    unique_reports = []  # Reports only covered by one tool in the set, e.g. if the incoming list has length 1
    duplicate_reports = []  # This should be a tuple of reports, one tuple for each duplicate
    list_length = len(reports_tool_list)
    if list_length == 1:
        # for this file, only one tool found issues. Tools should not cause duplicates themselves
        return reports_tool_list, []
    else:
        raise NotImplemented  # TODO:



def run_on_project_result(project_report_path):
    result_directories = [filepath.absolute() for filepath in pathlib.Path(project_report_path).glob('./*results*')]
    return get_reports_per_file(result_directories)


if __name__ == "__main__":
    run_on_project_result("./tests/plist")
