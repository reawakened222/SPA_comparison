import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from codechecker_interface import gen_convert_to_codechecker_command
from .analyzer_parent import Analyzer

CPPCHECK_PATH = os.getenv("CPPCHECK_PATH", shutil.which("cppcheck"))


def cppcheck_to_codechecker_warning_mapping():
    """
    As CppCheck warnings are all presented as unknown, we do an initial mapping
    based on the severity of similar CodeChecker checks:
    Mapping:
    severity="error"        => High (H)
    severity="information"  => Unrecognized (U)
    severity="performance"  => Low (L)
    severity="portability"  => Low (L)
    severity="style"        => Style (S)
    severity="warning"      => Medium (M)
    """
    def base_mapping(cpp_severity):
        mapper = {'error': 'H',
                  'information': 'U',
                  'performance': 'L',
                  'portability': 'L',
                  'style': 'S',
                  'warning': 'M'
                  }
        return mapper.get(cpp_severity, 'U')
    get_error_xml = subprocess.run([CPPCHECK_PATH, '--errorlist'], capture_output=True)
    if get_error_xml.returncode != 0:
        print("Something went wrong when grabbing CppCheck error list")
    errorlist = get_error_xml.stdout.decode('utf-8')
    root = ET.fromstring(errorlist)
    errorNodes = root.find('errors').findall('error')
    return dict([(e.attrib['id'], base_mapping(e.attrib['severity'])) for e in errorNodes])

cpp_to_codechecker_mapper = cppcheck_to_codechecker_warning_mapping()
def map_warning_severity(warn_id):
    return cpp_to_codechecker_mapper.get(warn_id, 'NOT_CPPCHECK')

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




