from datetime import datetime
import os
from codechecker_interface import gen_convert_to_codechecker_command


class Analyzer:
    def __init__(self, name, has_ctu, conversion_required, languages):
        self.name = name
        self.has_ctu = has_ctu
        self.conversion_required = conversion_required
        self.languages = languages

    def gen_analysis_commands(self, project_dir, project_name):
        """Method for getting a general analysis command, e.g. when running it on a target folder"""
        raise NotImplemented

    def gen_analysis_commands_from_compile_commands_file(self, project_dir, project_name, compile_command_database):
        """Method for running specifically on compile command file"""
        raise NotImplemented

    def gen_analysis_command_wrapper(self, target_path, project_name):
        if os.path.isfile(target_path):
            project_dir = os.path.split(target_path)[0]
            return self.gen_analysis_commands_from_compile_commands_file(project_dir, project_name, target_path)
        else:
            return self.gen_analysis_commands(target_path, project_name)

    def get_conversion_commands(self, original_path):
        """Returns the list of commands to run to convert analysis run from original path to the output directory"""
        if not self.conversion_required:
            return None
        converted_output_path = f"{original_path}/.CONV"
        return gen_convert_to_codechecker_command(original_path, "cppcheck", converted_output_path), \
               converted_output_path

    @property
    def ctu_suffix(self):
        return f"{'_ctu' if self.has_ctu else ''}"

    def get_analysis_run_name(self, project_name):
        return f"{project_name}_{self.name}{self.ctu_suffix}"

    def get_analysis_output_folderpath(self, output_path):
        now = datetime.now()
        analysis_starttime = now.strftime("%Y_%m_%d_%H_%M_%S")
        return f"{output_path}/{self.name}{self.ctu_suffix}_results_{analysis_starttime}"
