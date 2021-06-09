import logging
import os
from enum import Enum
from codechecker_interface import CODECHECKER_MAINSCRIPT_PATH
from compile_command_utils import COMPILE_COMMAND_DEFAULT

CMAKE_BUILD_DIRECTORY_NAME = "cmakebuild"
CMAKE_COMPILE_COMMAND_DEFAULT = "compile_commands.json"

# TODO: Would be good to add some generator for build setup and triggering compilation
# TODO: Refactor this into base- and subclasses instead of enum
class BuildSystem(Enum):
    def __str__(self):
        return self.name
    UNSUPPORTED = 0,
    Ant = 1,
    Bazel = 2,
    CMake = 3,
    Gradle = 4,
    Maven = 5,
    Meson = 6

def get_bazel_compilecommands(project_path, build_target='//...'):
    return ['log_bazel_build', project_path, build_target]

# Much of this can likely be a wrapper around CodeChecker's log command
# https://codechecker.readthedocs.io/en/latest/analyzer/user_guide/#log
def get_build_commands_compile_database_file(build_system, project_path, build_target=''):
    """Given a base path to a (fresh) project,
    this should return the necessary commands
    for creating a usable compile command file"""
    if not build_system:
        return None
    if not os.path.isdir(project_path):
        return None
    path = os.path.abspath(project_path)
    commands = []
    compile_command_path = ''



    return commands, compile_command_path

def determine_build_system(base_dir):
    files_in_dir = [f for f in os.listdir(base_dir)]

    if "gradlew" in files_in_dir or "gradle" in files_in_dir:
        return BuildSystem.Gradle
    elif "CMakeLists.txt" in files_in_dir:
        return BuildSystem.CMake
    elif "build.xml" in files_in_dir:
        return BuildSystem.Ant
    elif "pom.xml" in files_in_dir:
        return BuildSystem.Maven
    elif "BUILD.bazel" in files_in_dir:
        return BuildSystem.Bazel
    elif "meson.build" in files_in_dir:
        return BuildSystem.Meson
    else:
        return BuildSystem.UNSUPPORTED
