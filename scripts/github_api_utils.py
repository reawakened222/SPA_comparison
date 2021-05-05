import logging

from pathlib import Path
from collections import namedtuple
from github import Github
import os
import re
import xml.etree.ElementTree as ET
import enum
import argparse
import json  # For serializing
import requests  # For Rest API calls
import copy
from enum import IntEnum
import random
import itertools
from datetime import datetime
from functools import partial
import subprocess
from dotenv import load_dotenv

load_dotenv(".env")
token = os.getenv('GITHUB_TOKEN', '...')
CLOC_BIN = os.getenv("CLOC_BIN", '/usr/bin/cloc')

logging.basicConfig(filename="GITHUB_LOG.log", format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')


class APIException(BaseException):
    # TODO: implement some exception stuff
    def __init__(self, expression, message):
        self.expression = expression
        self.message = message

class SearchParameter:
    value = 0
    operator = "op"
    tag = ""

    def __init__(self, tag, value, op=">"):
        self.value = value
        self.operator = op
        self.tag = tag

    def __str__(self):
        return f"{self.tag}:{self.operator}{self.value}"


class SearchData:
    """Collection of search data, with pretty printing"""
    size_in_kb = 20000
    stars = 1000
    forks = 1000
    search_string = "test"
    languages = ["C", "C++"]

    def __init__(self, stars, forks, size_in_kb, search_string, language_list):
        self.stars = SearchParameter(tag="stars", value=stars)
        self.forks = SearchParameter(tag="forks", value=forks)
        self.size_in_kb = SearchParameter(tag="size", value=size_in_kb)
        self.languages = language_list
        self.search_string = search_string + " in:readme"

    def to_search_string(self):
        language_string = ""
        for lang in self.languages:
            language_string += f"language:{lang} "
        return f"{self.stars} {self.forks} {self.size_in_kb} {language_string} {self.search_string}"


def is_list_empty(_list: list):
    # Note: Empty list should convert to false in statement below
    return bool(_list)


def git_is_directory_name_substring_in_repo(pygit, repo_name, folder_name, recursive=False):
    """Returns path to folder if it exists"""
    # https://pygithub.readthedocs.io/en/latest/examples/Repository.html#get-all-of-the-contents-of-the-root-directory-of-the-repository
    repo = pygit.get_repo(repo_name)
    contents = repo.get_contents("")
    root_contents = copy.copy(contents)
    dirs = []
    # Add all directories to dirs list
    if recursive:
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                contents.extend(repo.get_contents(file_content.path))
                dirs.append((file_content.path.lower(), True))
    else:
        dirs = list(map(lambda x: (x.path.lower(), x.type == "dir"), contents))
    # dirs should contain all directories of interest, traverse and check for folderName
    dirs_matching_search = [i for (i, isDir) in dirs if folder_name in i and isDir]

    # for now, will hack in a check for CMake here, to reduce API calls
    # TODO: Extend to determine additional build systems
    return is_list_empty(dirs_matching_search), is_list_empty(git_is_cmake_project(pygit, root_contents))
    # return isListEmpty(dirs_matching_search)


def git_is_cmake_project(pygit, repo_contents):
    # repo = pygit.get_repo(repoName)
    # contents = repo.get_contents("")
    dirs = list(map(lambda x: x.path, repo_contents))
    return "CMakeLists.txt" in dirs


def get_projects_from_user(py_git, username):
    return py_git.get_user(username).get_repos()


# Filtering
# 1) language (general)
# 2) Language + size (test)
# Note: Github's API gives size value in bytes, this is ~1MB of code in C/C++, Java or Python
min_size_in_bytes = 1 * 1000 * 1000
general_lang_sizes = [("C++", min_size_in_bytes),
                      ("C", min_size_in_bytes),
                      ("Java", min_size_in_bytes),
                      ("Python", min_size_in_bytes)]


def filter_on_languages(language_size_dict, repository):
    """Filter based on the overall languages used, in number of bytes"""
    language_lookup = requests.get(repository.languages_url).json()
    if not language_lookup:
        return False
    err = language_lookup.get("message")
    if err and "rate limit" in err:
        raise API
    # total_size = sum(map(lambda e: int(e[1]), language_lookup.items()))

    # This is a fixed length for each run
    for requested_lang, lang_min_size in language_size_dict:
        size_for_repo = language_lookup.get(requested_lang)
        if size_for_repo and size_for_repo >= lang_min_size:
            return True
    return False


class ProjectSize(IntEnum):
    Tiny = 0,
    Small = 1,
    Medium = 2,
    Large = 3


class ClocData:
    project_path = ""
    lang_data = dict()

    def __init__(self, lang_data_dict, path):
        self.lang_data = lang_data_dict
        self.project_path = path

    def __getitem__(self, item):
        if isinstance(item, str):
            return self.lang_data[item]
        return None

    @staticmethod
    def make_from_string(cloc_output, run_path):
        root = ET.fromstring(cloc_output)
        langs = root.find("languages")
        if not langs:
            return None
        lang_data_dict = dict()
        for l in langs:
            if l.tag == "language":
                attr = l.attrib
                LangData = namedtuple("LangData", ["files", "blank", "commented", "code"])
                lang_data_dict[attr["name"]] = LangData(int(attr["files_count"]), int(attr["blank"]),
                                                        int(attr["comment"]), int(attr["code"]))

        return ClocData(lang_data_dict, run_path)

    def classify(self, language="C++"):
        """Return Small, Medium, or large-scale based on #LoC for language of interest"""
        # Small = <10k LoC
        # Medium <100k LoC
        # Large >=100k LoC
        result = ProjectSize.Tiny
        size = self.lang_data.get(language)
        if not size:
            return None
        else:
            if size.code < 10000:
                result = ProjectSize.Small if result < ProjectSize.Small else result
            elif size.code < 100000:
                result = ProjectSize.Medium if result < ProjectSize.Medium else result
            else:
                result = ProjectSize.Large
        return result

    def get_project_sizes_sorted(self, languages):
        """Get a list of language, size class pairs, sorted in descending order"""
        sizes = [(l, self.classify(l)) for l in languages if self.classify(l)]
        sizes.sort(key=lambda e: e[1], reverse=True)
        return sizes

def cloc_invocation(languages, top_folder=".", perl_dir_filter=""):
    directory_filter = " --match-d=" + perl_dir_filter + " " if perl_dir_filter != "" else " "
    invocation = [CLOC_BIN, f'--include-lang={",".join(languages)}', '--xml', '--quiet']
    if directory_filter != " ":
        invocation.append(directory_filter)
    invocation.append(top_folder)
    cloc_res = subprocess.run(invocation, capture_output=True)
    if cloc_res.returncode == 0:
        output = cloc_res.stdout.decode("utf-8").strip()
        return ClocData.make_from_string(output, top_folder)
    return None


def filter_on_testware_language(languages, repository):
    """Filter based on what languages are used to implement test code"""
    # The basic idea is to find testware folders, then somehow find the languages used
    # Worst case approach is to clone them, run e.g. cloc and then based on the result include/exclude them
    cloc = cloc_invocation(languages, repository.full_name, '.*[tT]est.*')
    if cloc:
        for l in languages:
            #  false if less than 1k lines of code in test folder
            if cloc.classify(l) > ProjectSize.Tiny:
                return True
    return False


def filter_on_project_loc_size(languages, size_classes_to_keep, repository):
    """Filtering based on LoC"""
    """Based on
    https://stackoverflow.com/questions/26881441/can-you-get-the-number-of-lines-of-code-from-a-github-repository
    the simplest way seems to be to shallow clone it, run e.g. cloc and then parse results"""
    res = subprocess.run(["git", "clone", "--depth", "1", repository.clone_url, repository.full_name])
    if res.returncode == 128:
        # Return code for "destination already exists"
        return True  # We assume this has already been filtered once
    cloc = cloc_invocation(languages, repository.full_name)
    if cloc:
        repo_size_classes = [e[1] for e in cloc.get_project_sizes_sorted(languages)]
        for s in size_classes_to_keep:
            if s in repo_size_classes:
                return True
    else:
        return False


def apply_filters_log_filtering(repo_list, repository_filters_explanation, log_filename):
    """Given a list of repositories, we filter (with logging) based on the set of filters supplied.
    Result will be a list of the list of projects that were left after each filter step"""
    Path("./.FILTERDATA").mkdir(parents=True, exist_ok=True)
    os.chdir("./.FILTERDATA")
    with open(log_filename, "w") as log:
        # Each iteration generates a new subset using current filter function
        def inner(repos, filters, acc):
            if not filters:
                return acc
            if not repos:
                log.write("No more repositories. Exiting ...")
                return acc
            f_head, *f_tail = filters
            filter_function, explanation_text = f_head
            filtered_repositories = [r for r in repos if filter_function(r)]
            filtered_repositories_names = map(lambda e: e.full_name + "\n", filtered_repositories)
            log.write(explanation_text + "\n")
            log.writelines(filtered_repositories_names)
            log.write("\n")
            acc.append(filtered_repositories)

            return inner(filtered_repositories, f_tail, acc)

        # I want to keep each step of the filtering, will make it easier for data extraction
        return inner(repo_list, repository_filters_explanation, [repo_list])


def eval_example(github_user):
    g = Github(token)
    repos = get_projects_from_user(g, github_user)

    if not repos:
        logging.debug("No repositories returned from user: " + github_user)
        return None
    # Partial applications of filter configuration on filter functions
    # Should return a function for which the remaining argument is the repository object from pygit
    filters = [(partial(filter_on_languages, general_lang_sizes), "Filtering based on overall code size using >=~1MB of code in C/C++, Java or Python"),
               (partial(filter_on_project_loc_size, ["C", "C++", 'C/C++ Header', "Python", "Java"], [ProjectSize.Medium, ProjectSize.Large]), "Filtering based on LoC"),
               (partial(filter_on_testware_language, ["C", "C++", "Python", "Java"]), "Filtering based on Testware LoC")]
    filtered_projects = apply_filters_log_filtering(repos, filters, github_user + "_FilteredProjects.log")


def make_clone_script():
    parser = argparse.ArgumentParser(description="github search wrapper")
    parser.add_argument('-s', '--size', default=100000, help="provide minimum size in kb")
    parser.add_argument('-st', '--stars', default=1000, help="provide minimum number of stars")
    parser.add_argument('-f', '--forks', default=100, help="provide minimum number of forks")
    parser.add_argument('-langs', '--languages', nargs='*',
                        default=['C', 'C++'], help="Provide Main languages to search for")
    parser.add_argument('-sp', '--searchphrase', help="Provide search string to use (will target readme file")
    args = parser.parse_args()
    # python3 github_api_utils.py --size=100000 --stars=1000 --forks=100 --languages=["Java"] --searchphrase="test"
    search = SearchData(args.stars, args.forks, args.size, args.searchphrase, args.languages).toSearchString()
    now = datetime.now()
    dt_string = now.strftime("%d%m%y_%H_%M_%S")
    with open(f"./out/cloneReposWithTestFolderInBase_{dt_string}.sh", "w+") as outfile:
        with open(f"./out/cloneReposWithCMakeSetup_{dt_string}.sh", "w+") as outfile2:
            outfile.write("#!/bin/sh\n")
            outfile.write(f"#SEARCH STRING: {search}\n")

            outfile2.write("#!/bin/sh\n")
            outfile2.write(f"#SEARCH STRING: {search}\n")

            g = Github(token)
            repositories = g.search_repositories(query=search)
            for repo in repositories:
                print(repo.full_name)
                has_test_dir, has_cmake_file = git_is_directory_name_substring_in_repo(g, repo.full_name, "test", False)
                git_command = f"git clone --depth 1 --recurse-submodules https://github.com/{repo.full_name} || :\n"
                if has_test_dir:
                    outfile.write(git_command)
                    if has_cmake_file:
                        outfile2.write(git_command)


if __name__ == "__main__":
    # make_clone_script()
    eval_example("Ericsson")
    # cloc_invocation(languages=["C", "C++", 'C/C++ Header', "Python", "Java"], perl_dir_filter="",
    #                top_folder="/home/jmm01/Git_Repos/KAzNU/apac")
