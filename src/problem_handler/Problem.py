import os

from src import helper
from src.problem_handler.verify_checker import verify_checker
from src.problem_handler.verify_metadata import verify_metadata
from src.problem_handler.verify_sample import verify_sample
from src.problem_handler.verify_solutions import verify_solutions
from src.problem_handler.verify_subtasks import verify_subtasks
from src.problem_handler.verify_testdata import verify_testdata

'''
An object parse the data in a regular tps directory with verification.

Always print error and terminate when an unexpected error happen.
'''

class Problem:
    def __init__(self, tps_directory, settings):
        self.tps_directory = tps_directory
        
        verify_metadata(self, settings)
        verify_checker(self, settings)
        verify_sample(self, settings)
        verify_solutions(self, settings)
        verify_subtasks(self, settings)
        verify_testdata(self, settings)

        helper.throw_info(f"Verification done! (problem code: [bold]{self.metadata['code']}[/bold])")

    def full_path(self, path):
        return os.path.join(self.tps_directory, path)
