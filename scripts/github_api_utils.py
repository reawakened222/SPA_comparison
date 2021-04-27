from github import Github
import os
import enum
import argparse
import json #For serializing
import copy
from datetime import datetime
token = os.getenv('GITHUB_TOKEN', '...')

class SearchParameter:
    value = 0
    operator = "op"
    tag = ""
    def __init__(self, tag, value, op = ">"):
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
    searchstring = "test"
    languages = ["C", "C++"]
    def __init__(self, stars,forks,sizeKB, searchstring, langs):
        self.stars = SearchParameter(tag="stars", value=stars)
        self.forks = SearchParameter(tag="forks", value=forks)
        self.size_in_kb = SearchParameter(tag="size", value=sizeKB)
        self.languages = langs
        self.searchstring = searchstring + " in:readme"
    
    def toSearchString(self):
        langs = ""
        for lang in self.languages:
            langs += f"language:{lang} "
        return f"{self.stars} {self.forks} {self.size_in_kb} {langs} {self.searchstring}"
def isListEmpty(_list:list):
    #Note: Empty list should convert to false in statement below
    return bool(_list)
def git_is_folder_in_repo(pygit, repoName, folderName, recursive=False):
    '''Returns path to folder if it exists'''
    #https://pygithub.readthedocs.io/en/latest/examples/Repository.html#get-all-of-the-contents-of-the-root-directory-of-the-repository
    repo = pygit.get_repo(repoName)
    contents = repo.get_contents("")
    root_contents = copy.copy(contents)
    dirs = []
    #Add all directories to dirs list
    if recursive:
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                contents.extend(repo.get_contents(file_content.path))
                dirs.append((file_content.path.lower(), True))
    else:
        dirs = list(map(lambda x: (x.path.lower(), x.type == "dir"), contents))
    #dirs should contain all directories of interest, traverse and check for folderName
    dirs_matching_search = [i for (i,isDir) in dirs if folderName in i and isDir]

    #for now, will hack in a check for CMake here, to reduce API calls
    return (isListEmpty(dirs_matching_search), isListEmpty(git_is_cmake_project(pygit, root_contents)))
    #return isListEmpty(dirs_matching_search)
    
def git_is_cmake_project(pygit, repoContents):
    #repo = pygit.get_repo(repoName)
    #contents = repo.get_contents("")
    dirs = list(map(lambda x: x.path, repoContents))
    return "CMakeLists.txt" in dirs
def main():
    parser = argparse.ArgumentParser(description="github search wrapper")
    parser.add_argument('-s', '--size', default=100000, help="provide minimum size in kb")
    parser.add_argument('-st', '--stars', default=1000, help="provide minimum number of stars")
    parser.add_argument('-f', '--forks', default=100, help="provide minimum number of forks")
    parser.add_argument('-langs', '--languages', nargs='*', default=['C', 'C++'], help="Provide Main languages to search for")
    parser.add_argument('-sp', '--searchphrase', help="Provide search string to use (will target readme file")
    args = parser.parse_args()
    #python3 github_api_utils.py --size=100000 --stars=1000 --forks=100 --languages=["Java"] --searchphrase="test"
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
                hasTestDir, hasCMakeFile = git_is_folder_in_repo(g, repo.full_name, "test", False)
                git_command = f"git clone --depth 1 --recurse-submodules https://github.com/{repo.full_name} || :\n"
                if hasTestDir:
                    outfile.write(git_command)
                    if hasCMakeFile:
                        outfile2.write(git_command)



if __name__ == "__main__":
    main()
