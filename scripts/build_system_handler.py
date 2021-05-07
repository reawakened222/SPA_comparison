import logging
import os
from enum import Enum


class BuildSystems(Enum):
    UNSUPPORTED = 0,
    Ant = 1,
    Bazel = 2,
    CMake = 3,
    Gradle = 4,
    Maven = 5


def determine_build_system(base_dir):
    files_in_dir = [f for f in os.listdir(base_dir) if os.path.isfile(f)]
    if "gradlew" in files_in_dir or "gradle" in files_in_dir:
        return BuildSystems.Gradle
    elif "CMakeLists.txt" in files_in_dir:
        return BuildSystems.CMake
    elif "build.xml" in files_in_dir:
        return BuildSystems.Ant
    elif "pom.xml" in files_in_dir:
        return BuildSystems.Maven
    elif "BUILD.bazel" in files_in_dir:
        return BuildSystems.Bazel
    else:
        return BuildSystems.UNSUPPORTED
