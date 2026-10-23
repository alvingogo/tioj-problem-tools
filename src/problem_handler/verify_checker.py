import os
import shlex
import subprocess
import tempfile

from rich.markup import escape

import src.helper as helper

# Used when the configuration file has no checker_compile_command, so that a configs directory
# written before this check existed still gets it.
DEFAULT_COMPILE_COMMAND = 'g++ -x c++ -std=c++17 -O2 -o {output} -'

'''
Requirement: None.

Description: Compile the checker of a tps problem the way it will be compiled on TIOJ, so that a
             checker which does not build there is caught here rather than turning up as a
             "Judge Compilation Error" on every submission of the problem.

             What is compiled is the source after helper.replace_header, which is what actually
             leaves this machine: the testlib.h of the problem directory is never uploaded, the
             one in files/ takes its place, and the two are not the same file. Compiling the
             problem's own copy instead would pass while TIOJ still fails.

             The source is fed through stdin and the program written into a temporary directory,
             so nothing is written to the problem directory.

Return value: None. Prints an error and terminates when the checker does not compile.
'''
def verify_checker(problem, settings):
    if problem.metadata['specjudge_type'] == 'none':
        return

    helper.throw_status('Compiling the checker...')

    checker = helper.read_file(problem.full_path(settings.path.checker))
    source = helper.replace_header(checker, settings)
    command = settings.default.get('checker_compile_command', DEFAULT_COMPILE_COMMAND)

    with tempfile.TemporaryDirectory() as directory:
        argv = [word.replace('{output}', os.path.join(directory, 'checker'))
                for word in shlex.split(command)]
        try:
            result = subprocess.run(argv, input=source, capture_output=True, text=True)
        except FileNotFoundError:
            helper.throw_warning(f'Cannot run "{argv[0]}" to compile the checker, skipping the check.')
            return

    if result.returncode != 0:
        helper.throw_error('The checker does not compile with the testlib.h that replaces its own '
                           f'({shlex.join(argv)}):\n' + escape(result.stderr.strip()))

    helper.throw_info('The checker compiles.')
