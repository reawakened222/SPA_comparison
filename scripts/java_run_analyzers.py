from _typeshed import FileDescriptor
import os
import argparse
import subprocess
from . import is_testware_translation_unit
USER = os.environ["USER"]
CODECHECKER_BIN_PATH = f"/home/{USER}/codechecker/build/CodeChecker/bin/"
path_to_codechecker_report_converter = f"${CODECHECKER_BIN_PATH}report-converter"
def store_to_codechecker(analysisoutputPath, codechecker_outputpath, analyzer, projectName):
    #success, convert to CodeChecker report and store in running server
    res = subprocess.run(["/home/$USER/codechecker/build/CodeChecker/bin/report-converter", "-t", analyzer, "-o", codechecker_outputpath, analysisoutputPath])
    if(res.returncode != 0):
        return False
    return subprocess.run(["CodeChecker", "store", "-name", projectName]).returncode == 0
def run_spotbugs_on_target(resultdir, targetdir):
    subprocess.call(["mkdir", "-p", resultdir])
    res = subprocess.run(["spotbugs", "-xml:withMessages", "-output", 
                            resultdir + "/bugs.xml", "text-ui", targetdir])
    if(res.returncode != 0):
        return False
    return store_to_codechecker(resultdir + "/bugs.xml", 
                            resultdir + "/codechecker_results_spotbugs", 
                            "spotbugs", os.path.dirname(targetdir))
    

def run_fbinfer_on_target(resultdir, targetdir):
    files_in_dir = list(filter(lambda x: os.path.isfile(x), os.listdir(targetdir)))
    infer_invocation_command = ["infer", "run", "--"]
    os.chdir(os.path.join(targetdir))
    if "gradlew" in files_in_dir or "gradle" in files_in_dir:
        infer_invocation_command.extend(["./gradlew", "build"])
    elif "CMakeLists.txt" in files_in_dir:
        #invoke with cmake ...
        subprocess.run(["mkdir", "-p", "cmakebuild_compilecommand"])
        os.chdir("cmakebuild_compilecommand")
        
        return False
    elif "build.xml" in files_in_dir:
        #TODO: Add stuff
        return False
    infer_run = subprocess.run(infer_invocation_command, capture_output=True)
    if(infer_run.returncode != 0):
        #log error to some file
        #for now, will print stdout and stderr
        print(infer_run.stdout + "\n")
        print(infer_run.stderr)
        return False
    else:
        return store_to_codechecker("./infer-out", "./codechecker_infer_results","fbinfer", os.path.dirname(targetdir))

def run_java_analyzers(basePath):
    runner_ctu_pairs = [(run_fbinfer_on_target, False), ]
    dirs_in_dir = list(filter(lambda x: os.path.isdir(x), os.listdir(basePath)))
    for d in dirs_in_dir:
        run_fbinfer_on_target(os.path.abspath(os.path.join(basePath, d)))

if __name__ == "__main__":
    currPath = os.getcwd()
    run_java_analyzers(currPath)
