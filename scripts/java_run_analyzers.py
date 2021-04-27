import shutil
import xml.etree.ElementTree as ET
import logging
USER = os.environ["HOME"]
CODECHECKER_BIN_PATH = f"{USER}/codechecker/build/CodeChecker/bin"
CODECHECKER_RESULTCONVERTER_PATH = f"{CODECHECKER_BIN_PATH}/report-converter"
PMD_INSTALL_PATH = os.environ["PMD_PATH"] #Path to Java ruleset xml file
logging.basicConfig(filename='spa_javaInvocation.log', encoding='utf-8', level=logging.DEBUG, format='%(asctime)s %(message)s\n')

from .compile_commands_filter import *
from codechecker_interface import *

PMD_INSTALL_PATH = os.environ["PMD_PATH"]  # Path to Java ruleset xml file


def run_spotbugs_on_target(resultdir, targetdir):
    subprocess.call(["mkdir", "-p", resultdir])
    spotbugs_result_file = f"{resultdir}/spotbugs_bugs.xml"
    res = subprocess.run(["spotbugs", "-xml:withMessages", "-output",
                          spotbugs_result_file, "text-ui", targetdir])
    if res.returncode != 0:
        print("Spotbugs run failed on " + targetdir + "\n")
        return False
    return convert_and_store_to_codechecker(spotbugs_result_file,
                                                                  resultdir + "/spotbugs_results",
                                            "spotbugs", os.path.dirname(targetdir) + "_spotbugs")


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


def run_pmd_on_target(resultdir, targetdir):
    subprocess.call(["mkdir", "-p", resultdir])
    pmd_result_file = f"{resultdir}/pmd_res.xml"
    files_in_dir = list(filter(lambda x: os.path.isfile(x), os.listdir(targetdir)))
    os.chdir(os.path.join(targetdir))
    if ANT_BUILD_FILE in files_in_dir:
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
                <fileset dir="{targetdir}">
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
                f"{resultdir}/pmd_results",
                "pmd",
                os.path.dirname(targetdir))
        # clean up, replace modified build with original (backed up)
        os.remove(ANT_BUILD_FILE)
        shutil.move("original_build.xml", ANT_BUILD_FILE)
    else:
        # Just try to run it on targetdir
        res = subprocess.run(["pmd", "-d", targetdir,
                              "-f", "xml", "-R", "rulesets/internal/all-java.xml",
                              "-reportfile", pmd_result_file], capture_output=True)
        with open(f"{resultdir}/PMD_log.txt", "w") as f:
            f.write(str(res.stdout))
            if res.stderr:
                f.write(str(res.stderr))
        pmd_violations_found_errorcode = 4
        if res.returncode == pmd_violations_found_errorcode:
            convert_and_store_to_codechecker(
                f"{pmd_result_file}",
                f"{resultdir}/pmd_results",
                "pmd",
                os.path.dirname(targetdir))


def run_fbinfer_on_target(resultdir, targetdir):
    files_in_dir = list(filter(lambda x: os.path.isfile(x), os.listdir(targetdir)))
    infer_invocation_command = ["infer", "run", "--"]
    os.chdir(os.path.join(targetdir))
    logging.info(f"FB Infer running on {targetdir}")
    if "gradlew" in files_in_dir or "gradle" in files_in_dir:
        print("SPACOMP_LOG: INFER GRADLE BUILD ON " + targetdir)
        infer_invocation_command.extend(["./gradlew", "test"])
    elif "CMakeLists.txt" in files_in_dir:
        print("SPACOMP_LOG: INFER CMAKE BUILD ON " + targetdir)
        subprocess.run(["mkdir", "-p", "cmakebuild_compilecommand"])
        os.chdir("cmakebuild_compilecommand")
        subprocess.run(["spacomp_cmake", ".."])
        # filter_compile_command("compile_commands.json", "testware_compilecommands.json")
        os.chdir("..")
        infer_invocation_command = ["infer", "run", "--compilation-database",
                                    "cmakebuild_compilecommand/compile_commands.json"]
    elif "build.xml" in files_in_dir:
        logging.info("SPACOMP_LOG: INFER ANT BUILD ON " + targetdir)
        infer_invocation_command.extend(["ant", "test"])
    elif "pom.xml" in files_in_dir:
        logging.info("SPACOMP_LOG: INFER MAVEN BUILD ON " + targetdir)
        infer_invocation_command.extend(["mvn", "test"])
    else:
        logging.warning("No supported build system found")
    infer_run = subprocess.run(infer_invocation_command, capture_output=True)
    if infer_run.returncode != 0:
        # log error to some file
        # for now, will print stdout and stderr
        print(str(infer_run.stdout) + "\n")
        print(infer_run.stderr)
        logging.warning("Error during Infer run")
        return False
    else:
        return convert_and_store_to_codechecker(f"{resultdir}/infer-out", f"{resultdir}/infer_results",
                                                "fbinfer", f'"{os.path.dirname(targetdir)}_infer"')


def run_java_analyzers(base_path):
    dirs_in_dir = list(filter(lambda x: os.path.isdir(x), os.listdir(base_path)))
    for d in dirs_in_dir:
        try:
            logging.info("Running on project " + str(d) + "\n")
            run_fbinfer_on_target("infer_results",os.path.abspath(os.path.join(base_path, d)))
            run_pmd_on_target("pmd_results",os.path.abspath(os.path.join(base_path, d)))
            run_spotbugs_on_target("spotbugs_results",os.path.abspath(os.path.join(base_path, d)))
        except Exception as e:
            print(f"SPACOMP_LOG: Following exception raised on {d}: " + str(e))

if __name__ == "__main__":
    currPath = os.getcwd()
    run_java_analyzers(currPath)
