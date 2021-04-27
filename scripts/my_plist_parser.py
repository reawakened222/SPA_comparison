import itertools

from codechecker_interface import *
from codechecker_common.plist_parser import parse_plist_file
import os
import pathlib
import re
from typing import List, Dict, Tuple
from codechecker_common.report import Report
from enum import Enum


class DuplicateRelations(Enum):
    NO_DUPLICATE = 0,
    SUBSUMPTION = 1,
    POTENTIAL_DUPLICATE = 2


def is_duplicate(w1: Report, w2: Report, col_distance=0, row_distance=0) -> DuplicateRelations:
    # 1) Warning originates in the same file - done already, remove this check to save effort
    # 1a) Warning/Checker is identical: Duplicate (potential CTU vs non-CTU run)
    # 2) Warning originates on the same line
    if abs(w1.line - w2.line) > row_distance:
        return DuplicateRelations.NO_DUPLICATE
    if w1.check_name == w2.check_name:
        return DuplicateRelations.SUBSUMPTION
    else:
        return DuplicateRelations.NO_DUPLICATE \
            if abs(w1.col - w2.col) > col_distance \
            else DuplicateRelations.POTENTIAL_DUPLICATE


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


def get_plist_reports_tool_pair(plist_result_dir: str) -> Tuple[List[Tuple[Dict[int, str], List[Report]]], str]:
    """
    Extracts the tool name and the reports from a report directory
    """
    dir_name = os.path.basename(plist_result_dir)
    tool_name = re.match("(.*?)_result.*", dir_name).group(1)
    plist_files = [filepath.absolute() for filepath in pathlib.Path(plist_result_dir).glob('./*.plist')]
    plist_reports = list(map(parse_plist_file, plist_files))
    plist_reports_remove_empties = [rep for rep in plist_reports if len(rep[1]) > 0]
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


def get_duplicate_unique_list_pairs(report_tool_list: List[Tuple[Report, str]]) -> \
        Tuple[List[List[Tuple[Report, str]]], List[Tuple[Report, str]]]:
    """Takes a list of reports and groups them as duplicated reports or as a list of unique reports"""


    # Define inner recursive function that does the work

    # TODO: Some optimisation potential. Subsumed tools need not be checked against each other
    #  and if there is only one tool left, we assume it's internally consistent and should not cause duplicates
    def inner(_l: List[Tuple[Report, str]],
              duplicates: List[List[Tuple[Report, str]]],
              uniques: List[Tuple[Report, str]]):

        if not _l:
            return duplicates, uniques

        # List unpacking
        head, *tail = _l

        # Split tail based on duplicate status
        potential_duplicates = [e for e in tail if is_duplicate(head[0], e[0]) != DuplicateRelations.NO_DUPLICATE]
        remainder = [e for e in tail if is_duplicate(head[0], e[0]) == DuplicateRelations.NO_DUPLICATE]

        # If we found duplicates, there are no unique findings, hence uniques is forwarded unchanged
        if len(potential_duplicates) > 0:
            duplicates.append([head] + potential_duplicates)
        # Otherwise, head is a unique report
        else:
            uniques.append(head)
        return inner(remainder,
                     duplicates,
                     uniques)

    return inner(report_tool_list, list(), list())


def get_reports_per_file(plist_result_directories):
    """
    Given a list of plist report directories
    maps it to a file -> Reports per tool and file -> Duplicated/Unique reports tuple
    """
    plist_reports_tool_map = list(map(get_plist_reports_tool_pair, plist_result_directories))
    filename_reports_key_val = {}
    for files_reports_list, tool_run in plist_reports_tool_map:
        # files_reports_list is a list of files, report list pairs
        for files, reports in files_reports_list:
            # And finally, we get access to the report itself.
            # Note, we use the filepath property to get the path to the main file
            # This is not necessarily the file with index 0, so we cannot simply append the entire list
            for report in reports:
                report_main_file = report.file_path
                if report_main_file not in filename_reports_key_val:
                    filename_reports_key_val[report_main_file] = []
                # TODO: This causes many duplications due to several issues appearing in the same file.
                # Consider changing this to a set instead of list
                filename_reports_key_val[report_main_file].append((report, tool_run))

    filename_reports_key_val_duplicates = dict(map(lambda e: (e[0],
                                                              get_duplicate_unique_list_pairs(e[1])
                                                              ),
                                                   filename_reports_key_val.items()))

    collapsed_reports_tool_pair = dict(map(lambda e: (e[0], collapse_reports_toolpair_list(e[1])),
                                           filename_reports_key_val.items()))
    return collapsed_reports_tool_pair, filename_reports_key_val_duplicates


def run_on_project_result(project_report_path):
    result_directories = [filepath.absolute() for filepath in pathlib.Path(project_report_path).glob('./*results*')]
    return get_reports_per_file(result_directories)


if __name__ == "__main__":
    run_on_project_result("./tests/plist")
