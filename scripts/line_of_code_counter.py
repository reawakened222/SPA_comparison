from enum import IntEnum
import xml.etree.ElementTree as ET
from collections import namedtuple
import subprocess
import os
import logging
from dotenv import load_dotenv

load_dotenv(".env")
CLOC_BIN = os.getenv("CLOC_BIN", '/usr/bin/cloc')

logging.basicConfig(filename="CLOC.log", format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.DEBUG)
LOG = logging.getLogger("CLOC")

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
        if 'language' not in cloc_output:
            return None
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
    directory_filter = "--match-d=" + perl_dir_filter if perl_dir_filter != "" else ""
    invocation = [CLOC_BIN, f'--include-lang={",".join(languages)}', '--xml', '--quiet']
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
        return ClocData.make_from_string(output, top_folder)
    return None