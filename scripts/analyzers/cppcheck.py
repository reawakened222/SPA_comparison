import os
import shutil
from codechecker_interface import gen_convert_to_codechecker_command
from .analyzer_parent import Analyzer

CPPCHECK_PATH = os.getenv("CPPCHECK_PATH", shutil.which("cppcheck"))


class CppCheck(Analyzer):
    def __init__(self):
        super().__init__("cppcheck", False, True, ["C", "C++"])

    def gen_analysis_commands(self, project_dir, project_name):
        """Method for getting a general analysis command, e.g. when running it on a target folder"""
        raise NotImplemented

    def gen_analysis_commands_from_compile_commands_file(self, project_dir, project_name, compile_command_database):
        result_folder = self.get_analysis_output_folderpath(project_dir)
        # Since CppCheck does not create output folders automatically, we must make sure it exists
        return [["mkdir", "-p", result_folder],
                [CPPCHECK_PATH, "--enable=all", "--inconclusive",
                 f"--project={compile_command_database}",  # compile commands to use
                 f"--plist-output={result_folder}"]
                ], result_folder




