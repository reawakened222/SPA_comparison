import os
import shutil
from codechecker_interface import gen_convert_to_codechecker_command
from analyzer_parent import Analyzer

INFER_PATH = os.getenv("INFER_PATH", shutil.which("infer"))


class FBInfer(Analyzer):
    def __init__(self):
        super().__init__("fbinfer", False, True, ["C", "C++", "Java"])

    def get_analysis_commands(self, output_dir, project_name):
        # TODO: REFACTOR!
        def run_fbinfer_on_target(resultdir, targetdir):
            build_system = determine_build_system(targetdir)
            infer_invocation_command = [f"{INFER_INSTALL_PATH}/infer", "run", "--"]
            os.chdir(os.path.join(targetdir))
            LOG.info(f"FB Infer running on {targetdir}")
            if build_system == BuildSystem.UNSUPPORTED:
                LOG.warning("No supported build system found to build ")
            elif build_system == BuildSystem.Ant:
                LOG.info("SPACOMP_LOG: INFER ANT BUILD ON " + targetdir)
                infer_invocation_command.extend(["ant", "test"])
            elif build_system == BuildSystem.Bazel:
                infer_invocation_command.extend(["bazel", "test"])
            elif build_system == BuildSystem.CMake:
                print("SPACOMP_LOG: INFER CMAKE BUILD ON " + targetdir)
                subprocess.run(["mkdir", "-p", "cmakebuild_compilecommand"])
                os.chdir("cmakebuild_compilecommand")
                subprocess.run(["spacomp_cmake", ".."])
                os.chdir("..")
                infer_invocation_command = ["infer", "run", "--compilation-database",
                                            "cmakebuild_compilecommand/compile_commands.json"]
            elif build_system == BuildSystem.Gradle:
                print("SPACOMP_LOG: INFER GRADLE BUILD ON " + targetdir)
                infer_invocation_command.extend(["./gradlew", "test"])
            elif build_system == BuildSystem.Maven:
                LOG.info("SPACOMP_LOG: INFER MAVEN BUILD ON " + targetdir)
                infer_invocation_command.extend(["mvn", "test"])
            return infer_invocation_command, resultdir
        result_folder = self.get_analysis_output_folderpath(project_dir)

    def gen_analysis_commands_from_compile_commands_file(self, project_dir, project_name, compile_command_database):
        result_folder = self.get_analysis_output_folderpath(project_dir)
        # Since CppCheck does not create output folders automatically, we must make sure it exists
        return [[INFER_PATH, "run",
               "-o", result_folder,  # output folder
               "--compilation-database", compile_command_database]
                ], result_folder


