import argparse

def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


lang_analyzers_mapping = {
    'java': ['pmd', 'spotbugs', 'infer'],
    'c': ['codechecker', 'codechecker', 'codechecker_ctu', 'cppcheck', 'infer'],
    'c++': ['codechecker', 'codechecker', 'codechecker_ctu', 'cppcheck', 'infer'],
    'python': ['pylint', 'pyre']
}


def get_framework_args(language):
    parser = argparse.ArgumentParser(description='Run analysers')
    parser.add_argument('--path', '-p', help='Path to run script on', required=True)
    parser.add_argument('--recursive', '-r', help='run script on all folders in path',
                        type=str2bool, required=False, default=False)
    parser.add_argument('--project-name', '-out',
                        help='If set, this is the base name used to store the runs in the framework',
                        required=False, default='')
    parser.add_argument('--only-tests', '-at', help='Whether analysis should only be run on tests',
                        type=str2bool, required=False, default=False)
    parser.add_argument('--no-upload',
                        help='Set to true if you do not want to upload to framework (e.g. debugging of toolchain)',
                        type=str2bool, required=False, default=False)
    parser.add_argument('--server-product',
                        help='Set which product collection to upload to within the framework',
                        required=False, default="Default")
    low_lang = language.lower()
    tools_list = ['all']
    # This should fail if it goes wrong, e.g. if language is not supported
    tools_list.extend(lang_analyzers_mapping[low_lang])
    parser.add_argument('--tools', '-t',
                        help='A semicolon-separated list of the following analysis tools to run: ' +
                             f'{";".join(tools_list)}',
                             required=False, default='all')
    return parser

