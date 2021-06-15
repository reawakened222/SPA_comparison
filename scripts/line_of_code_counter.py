import glob
from enum import IntEnum
import xml.etree.ElementTree as ET
from collections import namedtuple
import subprocess
import os
import logging
from dotenv import load_dotenv
import argh
import pickle
script_path = os.path.abspath(os.path.dirname(__file__))

load_dotenv(f"{script_path}/.env")
CLOC_BIN = os.getenv("CLOC_BIN", '/usr/bin/cloc')

logging.basicConfig(filename="CLOC.log", format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.DEBUG)
LOG = logging.getLogger("CLOC")

class ProjectSize(IntEnum):
    Tiny = 0,
    Small = 1,
    Medium = 2,
    Large = 3

    @staticmethod
    def get_size_from_loc_count(loc_count):
        if loc_count <= 1000:
            return ProjectSize.Tiny
        elif loc_count <= 50000:
            return ProjectSize.Small
        elif loc_count <= 100000:
            return ProjectSize.Medium
        else:
            return ProjectSize.Large



class LoCData:
    project_path = ''
    lang_data = dict()
    total_code_size = -1
    project_name = ''

    def __init__(self, lang_data_dict, size, path):
        self.lang_data = lang_data_dict
        self.total_code_size = size
        self.project_path = path

    def __getitem__(self, item):
        if isinstance(item, str):
            return self.lang_data[item]
        return None

    def save_to_string(self):
        res = ""
        c_cpp_files, c_cpp_loc = 0, 0
        #name	language	files	code
        for key, val in self.lang_data.items():
            if key not in ['C', 'C++', 'C/C++ Header']:
                res += f"{self.project_name},{key},{val[0]},{val[3]}" + "\n"
            else:
                c_cpp_files += val[0]
                c_cpp_loc += val[3]
        if c_cpp_loc > 0:
            res += f"{self.project_name},C/C++,{c_cpp_files},{c_cpp_loc}" + "\n"
        return res

    @staticmethod
    def make_from_string(cloc_output, run_path):
        if 'language' not in cloc_output:
            return None
        size = 0
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
                size += int(attr["code"])
        return LoCData(lang_data_dict, size, run_path)

    def classify(self, language="C++"):
        """Return Small, Medium, or large-scale based on #LoC for language of interest"""
        # Small = <10k LoC
        # Medium <100k LoC
        # Large >=100k LoC
        size = self.lang_data.get(language)
        if not size:
            return None
        else:
            return ProjectSize.get_size_from_loc_count(size.code)


    def get_project_sizes_sorted(self, languages):
        """Get a list of language, size class pairs, sorted in descending order"""
        sizes = [(l, self.classify(l)) for l in languages if self.classify(l)]
        sizes.sort(key=lambda e: e[1], reverse=True)
        return sizes


    def classify_total_size(self):
        return ProjectSize.get_size_from_loc_count(self.total_code_size)


def cloc_invocation(languages, top_folder=".", perl_dir_filter="", disable_timeout=False):
    directory_filter = "--match-d=" + perl_dir_filter if perl_dir_filter != "" else ""
    invocation = [f"{CLOC_BIN}/cloc", f'--include-lang={",".join(languages)}', '--xml', '--quiet']
    if disable_timeout:
        invocation.extend(['--timeout', '0'])

    if directory_filter != "":
        invocation.append(directory_filter)
    invocation.append(top_folder)
    cloc_res = subprocess.run(invocation, capture_output=True)
    if cloc_res.stderr:
        LOG.error("CLOC error for repo: " + top_folder + ": " + str(cloc_res.stderr))
        return None
    if cloc_res.returncode == 0 and not cloc_res.stderr:
        output = cloc_res.stdout.decode("utf-8").strip()
        LOG.debug("CLOC OUTPUT for repo: " + top_folder + ": " + output)
        return LoCData.make_from_string(output, top_folder)
    return None


def get_cloc_store_csv(basepath, result_directory='.',
                       reject_projects='', clear_cache=False,
                       disable_timeout=False, perl_folder_filter='',
                       append_log_name=''):
    proj_list = glob.glob(f"{basepath}/**/", recursive=False)
    rejected = reject_projects.split(';')
    proj_list_names = [(os.path.basename(os.path.dirname(t)), os.path.dirname(t)) for t in proj_list]
    if rejected:
        proj_list_names = [(name, path) for name, path in proj_list_names if name not in rejected]

    for name, path in proj_list_names:
        result_file_name = f"{result_directory}/{name}_LoCData{append_log_name}.csv"
        if not os.path.exists(result_file_name) or clear_cache:
            cloc_result = cloc_invocation(["C", "C++", 'C/C++ Header', "Python", "Java"], path, perl_folder_filter)
            if cloc_result is not None:
                cloc_result.project_name = name
                with open(result_file_name, 'w') as fp:
                    fp.write(f'name,language,files,code\n')
                    fp.write(cloc_result.save_to_string())


parser = argh.ArghParser()
parser.add_commands([get_cloc_store_csv])
if __name__ == '__main__':
    parser.dispatch()
