import pathlib
import shutil
import xml.etree.ElementTree as ET
import logging
import os
from dotenv import load_dotenv
from framework_utils import get_framework_args

from codechecker_interface import *
from build_system_handler import *
SCRIPT_PATH = pathlib.Path(__file__).parent.absolute()
load_dotenv(f"{SCRIPT_PATH}/.env")
USER = os.getenv("HOME")
PMD_INSTALL_PATH = os.getenv("PMD_PATH") #Path to Java ruleset xml file
INFER_INSTALL_PATH = os.getenv("INFER_PATH")
SPOTBUGS_INSTALL_PATH = os.getenv("SPOTBUGS_PATH")

logging.basicConfig(filename='spa_javaInvocation.log', level=logging.DEBUG, format='%(asctime)s %(message)s\n')
LOG = logging.getLogger("SPA_JAVA")

parser = get_framework_args("java")
args = None

def run_spotbugs_on_target(target_dir):
    result_dir = generate_analysis_output_folderpath(target_dir, "spotbugs", True)
    spotbugs_result_file = f"{result_dir}/spotbugs_bugs.xml"
    res = subprocess.run([f"{SPOTBUGS_INSTALL_PATH}/spotbugs", "-xml:withMessages", "-output",
                          spotbugs_result_file, "text-ui", target_dir])
    if res.returncode != 0:
        LOG.error("Spotbugs run failed on " + target_dir)
        #return False
    return convert_and_store_to_codechecker(spotbugs_result_file,
                                            result_dir + "/spotbugs_results",
                                        "spotbugs", os.path.dirname(target_dir), "_spotbugs", args.server_product)


def add_task_to_ant_build(build_xml, property_string, target_strings):
    tree = ET.parse(build_xml)
    root = tree.getroot()
    prop = ET.fromstring(property_string)
    root.append(prop)
    for target in target_strings:
        root.append(ET.fromstring(target))
    with open("mybuild.xml", "w") as f:
        mydata = str(ET.tostring(root))
        f.write(mydata)
    return "mybuild.xml"


ANT_BUILD_FILE = "build.xml"


def run_pmd_on_target(target_dir):
    result_dir = generate_analysis_output_folderpath(target_dir, 'pmd', True)
    pmd_result_file = f"{result_dir}/pmd_res.xml"
    os.chdir(os.path.join(target_dir))
    build_system = determine_build_system(target_dir)
    if build_system == BuildSystem.Ant:
        # Ant build
        new_build = add_task_to_ant_build(f"./{ANT_BUILD_FILE}",
                                          '<taskdef name="pmd" classname="net.sourceforge.pmd.ant.PMDTask"/>',
                                          [f'''
        <taskdef name="pmd" classname="net.sourceforge.pmd.ant.PMDTask">
            <classpath>
                <fileset dir="{PMD_INSTALL_PATH}/lib">
                    <include name="*.jar"/>
                </fileset>
            </classpath>
        </taskdef>
        ''',
                                           f'''
        <target name="pmd">
            <taskdef name="pmd" classname="net.sourceforge.pmd.ant.PMDTask"/>
            <pmd rulesetfiles="rulesets/internal/all-java.xml">
                <formatter type="xml" toFile="{pmd_result_file}"/>
                <fileset dir="{target_dir}">
                    <include name="**/*test*.java"/>
                    <include name="**/*Test*.java"/>
                </fileset>
            </pmd>
        </target>'''])
        shutil.move(ANT_BUILD_FILE, "original_build.xml")
        shutil.move(new_build, ANT_BUILD_FILE)

        # Run new ant build
        res = subprocess.run(["ant", "pmd"])
        if res.returncode != 0:
            print("SPA Comparison: Modified Ant build failed\n")
        else:
            # send results to CodeChecker
            convert_and_store_to_codechecker(
                f"{pmd_result_file}",
                f"{result_dir}/pmd_results",
                "pmd",
                os.path.dirname(target_dir))
        # clean up, replace modified build with original (backed up)
        os.remove(ANT_BUILD_FILE)
        shutil.move("original_build.xml", ANT_BUILD_FILE)
    else:
        # Just try to run it on targetdir
        res = subprocess.run([f"{PMD_INSTALL_PATH}/bin/run.sh", "pmd", "-d", target_dir,
                              "-f", "xml", "-R", "rulesets/internal/all-java.xml",
                              "-reportfile", pmd_result_file], capture_output=True)
        with open(f"{result_dir}/PMD_log.txt", "w") as f:
            f.write(str(res.stdout))
            if res.stderr:
                f.write(str(res.stderr))
        pmd_violations_found_errorcode = 4
        #if res.returncode == pmd_violations_found_errorcode:
        convert_and_store_to_codechecker(
            f"{pmd_result_file}",
            f"{result_dir}/pmd_results",
            "pmd",
            os.path.dirname(target_dir))


def run_fbinfer_on_target(target_dir):
    build_system = determine_build_system(target_dir)
    result_dir = generate_analysis_output_folderpath(target_dir, 'infer')
    infer_invocation_command = [f"{INFER_INSTALL_PATH}/infer", "run", "-o", result_dir, "--"]
    os.chdir(target_dir)
    if build_system == BuildSystem.UNSUPPORTED:
        LOG.warning("No supported build system found to build " + target_dir)
    elif build_system == BuildSystem.Ant:
        infer_invocation_command.extend(["ant", "test"])
    elif build_system == BuildSystem.CMake:
        subprocess.run(["mkdir", "-p", CMAKE_BUILD_DIRECTORY_NAME])
        os.chdir(CMAKE_BUILD_DIRECTORY_NAME)
        subprocess.run(["spacomp_cmake", ".."])
        os.chdir("..")
        infer_invocation_command = [f"{INFER_INSTALL_PATH}/infer", "run", "-o", result_dir, "--compilation-database",
                                    "cmakebuild_compilecommand/compile_commands.json"]
    elif build_system == BuildSystem.Gradle:
        infer_invocation_command.extend(["./gradlew", "test"])
    elif build_system == BuildSystem.Maven:
        infer_invocation_command.extend(["mvn", "clean", "compile", "test-compile"])
        if "requirements.txt" in [f for f in os.listdir(target_dir)]:
            infer_invocation_command.extend("-s", "requirements.txt")
    else:
        LOG.warning("Build system is not supported by Infer")
    LOG.info(f"FB Infer running on {target_dir}")
    infer_run = subprocess.run(infer_invocation_command, capture_output=True)
    if infer_run.returncode != 0:
        # log error to some file
        # for now, will print stdout and stderr
        LOG.error("Error during Infer run")
        LOG.error(str(infer_run.stdout.decode('utf-8')))
        LOG.error(str(infer_run.stderr.decode('utf-8')))
        return False
    else:
        return convert_and_store_to_codechecker(f"{result_dir}/infer-out", f"{result_dir}/infer_results",
                                                "fbinfer", f'"{os.path.dirname(target_dir)}_infer"', args.server_product)


java_analyzer_mapping = {
    'pmd': run_pmd_on_target,
    'spotbugs': run_spotbugs_on_target,
    'infer': run_fbinfer_on_target
}

def get_analyzer_funcs(toolnames):
    def inner(tool):
        return java_analyzer_mapping.get(tool, None)
    if 'all' in toolnames:
        return [t for t in java_analyzer_mapping.items()]
    else:
        return [inner(t) for t in toolnames if t is not None]


def run_analyzers_on_project(project_base_path, funcs):
    project_abs_path = str(pathlib.Path(project_base_path).absolute())
    LOG.info("Running on project " + str(project_abs_path) + "\n")

    for runner in funcs:
        runner(project_abs_path)


if __name__ == "__main__":
    args = parser.parse_args()
    if not os.path.isdir(args.path):
        print(f"Invalid project path {args.path}.")
        exit(1)
    tools_list = args.tools.split(";")
    analyzer_funcs = get_analyzer_funcs(tools_list)
    dirs = [os.path.abspath(args.path)]
    if args.recursive:
        dirs = [os.path.abspath(d) for d in next(os.walk(args.path))[1]]
    for d in dirs:
        print("Running analyzers on " + d)
        run_analyzers_on_project(d, analyzer_funcs)
