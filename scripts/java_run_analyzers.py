from _typeshed import FileDescriptor
import os
import shutil
import argparse
import subprocess
from sys import stderr
import xml.etree.ElementTree as ET
USER = os.environ["USER"]
CODECHECKER_BIN_PATH = f"/home/{USER}/codechecker/build/CodeChecker/bin/"
path_to_codechecker_report_converter = f"${CODECHECKER_BIN_PATH}report-converter"
PMD_INSTALL_PATH = os.environ["PMD_PATH"] #Path to Java ruleset xml file

def store_to_codechecker(analysisoutputPath, codechecker_outputpath, analyzer, projectName):
    #success, convert to CodeChecker report and store in running server
    res = subprocess.run(["/home/$USER/codechecker/build/CodeChecker/bin/report-converter", "-t", analyzer, "-o", codechecker_outputpath, analysisoutputPath])
    if(res.returncode != 0):
        return False
    return subprocess.run(["CodeChecker", "store", "-name", projectName + "_" + analyzer]).returncode == 0
def run_spotbugs_on_target(resultdir, targetdir):
    subprocess.call(["mkdir", "-p", resultdir])
    res = subprocess.run(["spotbugs", "-xml:withMessages", "-output", 
                            resultdir + "/bugs.xml", "text-ui", targetdir])
    if(res.returncode != 0):
        return False
    return store_to_codechecker(resultdir + "/bugs.xml", 
                            resultdir + "/codechecker_results_spotbugs", 
                            "spotbugs", os.path.dirname(targetdir))
def add_task_to_ant_build(build_xml, property_string, target_strings):
    tree = ET.parse(build_xml)
    root = tree.getroot()
    prop = ET.fromstring(property_string)
    root.append(prop)
    for target in target_strings:
        root.append(ET.fromstring(target))
    with open("mybuild.xml", "w") as f:
        mydata = ET.tostring(root)
        f.write(mydata)
    return "mybuild.xml"


ANT_BUILD_FILE = "build.xml"
def run_pmd_on_target(resultdir,targetdir):
    subprocess.call(["mkdir", "-p", resultdir])
    files_in_dir = list(filter(lambda x: os.path.isfile(x), os.listdir(targetdir)))
    os.chdir(os.path.join(targetdir))
    if ANT_BUILD_FILE in files_in_dir:
        #Ant build
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
                    <formatter type="xml" toFile="{resultdir}/pmd_res.xml"/>
                    <fileset dir="{targetdir}">
                        <include name="**/test*.java"/>
                        <include name="**/Test*.java"/>
                        <include name="**/*test.java"/>
                        <include name="**/*Test.java"/>
                    </fileset>
                </pmd>
        </target>'''])
        shutil.move(ANT_BUILD_FILE, "original_build.xml")
        shutil.move(new_build, ANT_BUILD_FILE)

        #Run new ant build
        res = subprocess.run("ant", "pmd")
        if(res):
            print("SPA Comparison: Modified Ant build failed\n")
        else:
            # send results to CodeChecker
            store_to_codechecker(
                "{resultdir}/pmd_res.xml", 
                "{resultdir}/codechecker_pmd_results", 
                "pmd", 
                os.path.dirname(targetdir))

        #clean up, replace modified build with original (backed up)
        os.remove(ANT_BUILD_FILE)
        shutil.move("original_build.xml", ANT_BUILD_FILE)
        
        
    else:
        #Just try to run it on targetdir
        res = subprocess.run(["pmd", "-d", targetdir, "-f", "xml", "-R", "rulesets/internal/all-java.xml"],capture_output=True)
        with open("{resultdir}/pmd_res.xml", "w") as f:
            f.write(res.stdout)
            if(res.stderr):
                f.write(res.stderr)
        store_to_codechecker(
                "{resultdir}/pmd_res.xml", 
                "{resultdir}/codechecker_pmd_results", 
                "pmd", 
                os.path.dirname(targetdir))

    

def run_fbinfer_on_target(resultdir, targetdir):
    files_in_dir = list(filter(lambda x: os.path.isfile(x), os.listdir(targetdir)))
    infer_invocation_command = ["infer", "run", "--"]
    os.chdir(os.path.join(targetdir))
    if "gradlew" in files_in_dir or "gradle" in files_in_dir:
        infer_invocation_command.extend(["./gradlew", "build"])
    elif "CMakeLists.txt" in files_in_dir:
        subprocess.run(["mkdir", "-p", "cmakebuild_compilecommand"])
        os.chdir("cmakebuild_compilecommand")
        subprocess.run(["spacomp_cmake", ".."])
        os.chdir("..")
        infer_invocation_command = ["infer", "run", "--compilation-database", "cmakebuild_compilecommand/compile_commands.json"]
    elif "build.xml" in files_in_dir:
        infer_invocation_command.extend(["ant"])
    infer_run = subprocess.run(infer_invocation_command, capture_output=True)
    if(infer_run.returncode != 0):
        #log error to some file
        #for now, will print stdout and stderr
        print(infer_run.stdout + "\n")
        print(infer_run.stderr)
        return False
    else:
        return store_to_codechecker(f"{resultdir}/infer-out", f"{resultdir}/codechecker_infer_results","fbinfer", os.path.dirname(targetdir))

def run_java_analyzers(basePath):
    #runner_ctu_pairs = [(run_fbinfer_on_target, False)]
    dirs_in_dir = list(filter(lambda x: os.path.isdir(x), os.listdir(basePath)))
    for d in dirs_in_dir:
        run_fbinfer_on_target("infer_results",os.path.abspath(os.path.join(basePath, d)))
        run_pmd_on_target("pmd_results",os.path.abspath(os.path.join(basePath, d)))
        run_spotbugs_on_target("spotbugs_results",os.path.abspath(os.path.join(basePath, d)))

if __name__ == "__main__":
    currPath = os.getcwd()
    run_java_analyzers(currPath)
