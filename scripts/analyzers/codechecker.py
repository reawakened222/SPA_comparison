import os
import shutil
from codechecker_interface import gen_convert_to_codechecker_command
from analyzer_parent import Analyzer

CODECHECKER_PATH = os.getenv("CODECHECKER_PATH", "CodeChecker")     # This one should hopefully be sourced through venv


class CppCheck(Analyzer):
    def __init__(self, run_ctu):
        super().__init__("codechecker", run_ctu, False, ["C", "C++"])

    def gen_analysis_commands(self, project_dir, project_name):
        """Method for getting a general analysis command, e.g. when running it on a target folder"""
        raise NotImplemented

    def gen_analysis_commands_from_compile_commands_file(self, project_dir, project_name, compile_command_database):
        result_folder = self.get_analysis_output_folderpath(project_dir)
        command = [CODECHECKER_PATH, "analyze", "-o", result_folder]
        if self.run_ctu:
            command.append("--ctu-all")
        command.append(compile_command_database)
        return [command], result_folder