import logging
import subprocess

from pathlib import Path
from github import Github
import os
import pathlib
import xml.etree.ElementTree as ET
import argparse
import copy
from datetime import datetime
from functools import partial
from line_of_code_counter import ProjectSize, cloc_invocation
from dotenv import load_dotenv

load_dotenv(".env")
token = os.getenv('GITHUB_TOKEN', '...')
PY_GIT = Github(token)
CLOC_BIN = os.getenv("CLOC_BIN", '/usr/bin/cloc')

logging.basicConfig(filename="GITHUB_LOG.log", format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
LOG = logging.getLogger("GITHUB")


class APIException(BaseException):
    def __init__(self, message):
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


def git_is_directory_name_substring_in_repo(py_git, repo_name, folder_name, recursive=False):
    """Returns path to folder if it exists"""
    # https://pygithub.readthedocs.io/en/latest/examples/Repository.html#get-all-of-the-contents-of-the-root-directory-of-the-repository
    repo = py_git.get_repo(repo_name)
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
    return is_list_empty(dirs_matching_search), is_list_empty(git_is_cmake_project(py_git, root_contents))
    # return isListEmpty(dirs_matching_search)


def git_is_cmake_project(py_git, repo_contents):
    # repo = py_git.get_repo(repoName)
    # contents = repo.get_contents("")
    dirs = [x.path for x in repo_contents]
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
max_time_since_update = 365 * 1
today_date = datetime.today()


def filter_on_activity(max_days_since_update_allowed, repository):
    """Filter based on the number of days since last update was made to project."""
    # While there is a updated_at property, it seems to consider non-data related updates, so will use pushed_at for now
    repo_update_date = repository.pushed_at
    date_diff = today_date - repo_update_date
    return date_diff.days <= max_days_since_update_allowed


def filter_on_languages(language_size_dict, repository):
    """Filter based on the overall languages used, in number of bytes"""
    #request = requests.get(repository.languages_url, headers={'Authentication': "token " + token})
    language_lookup = repository.get_languages()
    err = language_lookup.get("message")
    if err:
        LOG.error("Request failed for " + repository.full_name + "\n")
    if not language_lookup:
        return False

    # This is a fixed length for each run
    for requested_lang, lang_min_size in language_size_dict:
        size_for_repo = language_lookup.get(requested_lang)
        if size_for_repo and size_for_repo >= lang_min_size:
            LOG.debug(repository.full_name + " included due to " + requested_lang + "\n")
            return True
    LOG.debug(repository.full_name + " rejected based on size\n")
    return False


def filter_on_testware_language(languages, repository):
    """Filter based on what languages are used to implement test code"""
    cloc = cloc_invocation(languages, repository.full_name, '.*[tT]est.*')
    if cloc:
        for l in languages:
            size = cloc.classify(l)
            #  false if less than 1k lines of code in test folder
            if size is not None and size > ProjectSize.Tiny:
                return True
    return False


def filter_on_project_loc_size(languages, size_classes_to_keep, repository):
    """Filtering based on LoC"""
    """Based on
    https://stackoverflow.com/questions/26881441/can-you-get-the-number-of-lines-of-code-from-a-github-repository
    the simplest way seems to be to shallow clone it, run e.g. cloc and then parse results"""
    cmd = ["git", "clone"]
    if repository.default_branch == 'main':
        cmd.extend(["--depth", "1"])
    else:
        LOG.debug(f"Potential issue: following repository does not default to main - {repository.full_name}. Pulling everything ...")
    cmd.extend([repository.clone_url, repository.full_name])
    res = subprocess.run(cmd)
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


def apply_filters_log_filtering(repo_list, repository_filters_explanation, log_filename, filters_base_path="."):
    """Given a list of repositories, we filter (with logging) based on the set of filters supplied.
    Result will be a list of the list of projects that were left after each filter step"""
    base_path = Path.absolute(filters_base_path).join("/.FILTERDATA")
    base_path.mkdir(parents=True, exist_ok=True)
    os.chdir(base_path)
    acc = []
    repos = repo_list
    with open(log_filename, "w") as xml_log:
        xml_log.write('<?xml version="1.0"?>\n')
        xml_log.write('<Filterings>\n')
        for f_head in repository_filters_explanation:
            if not repos:
                LOG.debug("No more repositories. Exiting ...")
                break
            filter_function, explanation_text = f_head
            print(f"Filtering with filter: {explanation_text}\n")
            filtered_repositories = [r for r in repos if filter_function(r)]
            xml_log.write(f'\t<Filter note="{explanation_text}" amount="{len(filtered_repositories)}">\n')
            for r in filtered_repositories:
                xml_log.write(f'\t\t<Repository name="{r.full_name}" url="{r.clone_url}" />\n')
            xml_log.write(f'\t</Filter>\n')
            acc.append(filtered_repositories)
            repos = filtered_repositories
        xml_log.write('</Filterings>\n')
    os.chdir("..")
    return acc


def get_final_projects_absolute_paths(filter_file):
    data_file = open(filter_file)
    data = data_file.read()
    data_file.close()
    root = ET.fromstring(data)
    last_filter_node = root.findall("Filter")[-1]

    # Get relative path to projects in relation to the filter file
    base_path = os.path.split(filter_file)[0]
    final_project_set = [base_path + "/" + r.get("name") for r in list(last_filter_node)]
    return last_filter_node


def eval_example(github_user, working_directory=os.getcwd()):
    repos = get_projects_from_user(PY_GIT, github_user)
    if not repos:
        LOG.debug("No repositories returned from user: " + github_user)
        return None
    if not pathlib.Path(github_user + "_AllProjects.log").exists():
        with open(github_user + "_AllProjects.log", "w") as log:
            for name in [r.full_name for r in repos]:
                log.write(name + "\n")

    # Partial applications of filter configuration on filter functions
    # Should return a function for which the remaining argument is the repository object from pygit
    filters = [(partial(filter_on_languages, general_lang_sizes),
                "Filtering based on overall code size using >=~1MB of code in C/C++, Java or Python"),
               (partial(filter_on_activity, max_time_since_update),
                "Filtering based on time since last activity: <= " + str(max_time_since_update) + " days"),
               (partial(filter_on_project_loc_size, ["C", "C++", 'C/C++ Header', "Python", "Java"],
                        [ProjectSize.Medium, ProjectSize.Large]),
                "Filtering based on LoC count overall (>10000 LoC in any of the languages listed)"),
               (
               partial(filter_on_testware_language, ["C", "C++", "Python", "Java"]),
               "Filtering based on Testware LoC (>1000 Lines of tests)")]
    filtered_projects = apply_filters_log_filtering(repos, filters, github_user + "_FilteredProjects.xml")


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

            repositories = PY_GIT.search_repositories(query=search)
            for repo in repositories:
                print(repo.full_name)
                has_test_dir, has_cmake_file = git_is_directory_name_substring_in_repo(PY_GIT, repo.full_name, "test", False)
                git_command = f"git clone --depth 1 --recurse-submodules https://github.com/{repo.full_name} || :\n"
                if has_test_dir:
                    outfile.write(git_command)
                    if has_cmake_file:
                        outfile2.write(git_command)


if __name__ == "__main__":
    # make_clone_script()
    eval_example("Ericsson", "../Case_Studies")
    eval_example("Google", "../Case_Studies")
    eval_example("Microsoft", "../Case_Studies")
