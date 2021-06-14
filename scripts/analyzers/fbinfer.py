import logging
import os
import pathlib
import shutil
from codechecker_interface import gen_convert_to_codechecker_command
from analyzers.analyzer_parent import Analyzer
from build_system_handler import *
import subprocess

INFER_PATH = os.getenv("INFER_PATH", shutil.which("infer"))
logging.basicConfig(filename="INFER.log", level=logging.INFO)
LOG = logging.getLogger("FB_INFER")

INFER_UNSUPPORTED_FLAGS = ['-pass-exit-codes']

INFER_ALL_CHECK_FLAGS = [('--annotation-reachability', ['C', 'Java', '.NET']),
                         ('--biabduction', ['C', 'Java', '.NET']),
                         ('--bufferoverrun', ['C', 'Java', '.NET']),
                         ('--impurity', ['C', 'Java', '.NET']),
                         ('--inefficient-keyset-iterator', ['Java', '.NET']),
                         ('--litho-required-props', ['Java', '.NET']),
                         ('--liveness', ['C']),
                         ('--loop-hoisting', ['C', 'Java', '.NET']),
                         ('--pulse', ['C', 'Java']),
                         ('--purity', ['C', 'Java', '.NET']),
                         ('--quandary', ['C', 'Java', '.NET']),
                         ('--racerd', ['C', 'Java', '.NET']),
                         ('--siof', ['C']),
                         ('--starvation', ['C', 'Java', '.NET']),
                         ('--uninit', ['C'])
                         ]

INFER_ALL_C_FLAGS = [flag for (flag, langs) in INFER_ALL_CHECK_FLAGS if 'C' in langs]
INFER_ALL_JAVA_FLAGS = [flag for (flag, langs) in INFER_ALL_CHECK_FLAGS if 'Java' in langs]


class FBInfer(Analyzer):
    def __init__(self):
        super().__init__("fbinfer", False, True, ["C", "C++", "Java"])

    def gen_analysis_commands(self, project_dir, project_name):
        def fbinfer_command_on_dir(resultdir, targetdir):
            LOG.info(f"FB Infer running on {targetdir}")
            build_system = determine_build_system(targetdir)
            if build_system == BuildSystem.UNSUPPORTED:
                LOG.warning("No supported build system found to build " + targetdir)
                return []

            infer_invocation_command = [INFER_PATH, "run", "--results-dir", resultdir]
            LOG.info(f"Infer detected {build_system} build")
            if build_system == BuildSystem.CMake:
                cmake_build_dir = pathlib.Path(targetdir).joinpath(f"./{CMAKE_BUILD_DIRECTORY_NAME}").absolute()
                # Check if cmake has been run before
                if not cmake_build_dir.exists() or \
                    pathlib.Path(cmake_build_dir).joinpath(CMAKE_COMPILE_COMMAND_DEFAULT):
                    LOG.debug("CMake folder or compilation database not found, rerunning basic cmake config")
                    subprocess.run(["mkdir", "-p", cmake_build_dir])
                    os.chdir(cmake_build_dir)
                    cmake_result = subprocess.run(["cmake", "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON", ".."])
                    if cmake_result.returncode != 0:
                        LOG.error("Something went wrong during CMake run. Skipping Infer invocation ...")
                        return []
                    os.chdir("..")
                return [["infer", "run", "--compilation-database",
                         f"{cmake_build_dir}/{CMAKE_COMPILE_COMMAND_DEFAULT}"]]
            else:
                # We need to use capture mode
                infer_invocation_command.append("--")
                if build_system == BuildSystem.Ant:
                    infer_invocation_command.extend(["ant", "test"])
                elif build_system == BuildSystem.Gradle:
                    infer_invocation_command.extend(["./gradlew", "test"])
                elif build_system == BuildSystem.Maven:
                    infer_invocation_command.extend(["mvn", "test"])
                return [infer_invocation_command]
        result_folder = self.get_analysis_output_folderpath(project_dir)
        return fbinfer_command_on_dir(result_folder, project_dir)

    def gen_analysis_commands_from_compile_commands_file(self, project_dir, project_name, compile_command_database):
        result_folder = self.get_analysis_output_folderpath(project_dir)
        return [[INFER_PATH, "run",
               "-o", result_folder,  # output folder
               "--compilation-database", compile_command_database]
                ], result_folder


