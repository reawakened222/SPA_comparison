import logging
import os
from enum import Enum

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
