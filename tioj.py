import typer
import json
import os
from dynaconf import Dynaconf
from pathlib import Path

import src.helper as helper
from src.session import open_session
from src.config import settings
from src.config import Compiler
import src.problem_handler as problem_handler
from src.submit import submit_submission

app = typer.Typer()

@app.command()
def whoami():
    '''
    To test whether user can successfully login to TIOJ.
    '''
    tioj = open_session()
    helper.throw_info(f'You are: [bold]{tioj.whoami()}[/bold]')

@app.command()
def isadmin():
    '''
    To verify whether the account has admin permission.
    '''
    tioj = open_session()
    if tioj.isadmin():
        helper.throw_info(f'You have admin permission!')
    else:
        helper.throw_info(f'You don\'t have admin permission!')

@app.command()
def create_empty_problem(number: int = typer.Argument(1, help='The number of created empty problem(s).')):
    '''
    Create one or more empty problem(s) on TIOJ. Need admin permission.
    '''
    tioj = open_session(require_admin=True)

    for _ in range(number):
        problem_handler.create_empty_problem(tioj, settings)

@app.command()
def delete_problem(problem_id: str = typer.Argument(..., help="The TIOJ problem id."),
                   yes: bool = typer.Option(False, '--yes', '-y', help="Skip the confirmation prompt.")):
    '''
    Remove all the content of a TIOJ problem while keeping the problem id, which resets it to an empty problem. Need admin permission.
    '''
    if not problem_id.isdigit():
        helper.throw_error('problem_id must be digits')
    problem_id = str(int(problem_id))

    tioj = open_session(require_admin=True)

    if not yes:
        typer.confirm(f'This will erase everything in TIOJ problem {problem_id}. Continue?', abort=True)

    problem_handler.delete_problem(problem_id, tioj, settings)

@app.command()
def upload_problem(tps_dir: Path = typer.Argument(..., exists=True, file_okay=False, help='Path to the tps directory.'),
                   problem_id: str = typer.Argument('', help="The corresponding TIOJ problem id. Leave blank if you want to use 'tioj_problem_id' in problem.json; Use 'new' to upload the problem to a new empty problem."),
                   update_metadata: bool = typer.Option(True, help="Whether you want to update the metadata in problem.json and the statements."),
                   update_sample: bool = typer.Option(True, help="Whether you want to update the sample testcases."),
                   update_checker: bool = typer.Option(True, help="Whether you want to update the checker."),
                   update_grader: bool = typer.Option(True, help="Whether you want to update the header and grader."),
                   update_testdata: bool = typer.Option(True, help="Whether you want to update the testcases. --no-update-testdata will give an effective speed up when you don't want to update testcases."),
                   update_subtasks_data: bool = typer.Option(True, help="Whether you want to update the subtasks' data.")):
    '''
    Upload a problem directory in tps format to TIOJ. Need admin permission.
    '''
    tioj = open_session(require_admin=True)

    helper.throw_status(f'Uploading problem {problem_id} to TIOJ with {tps_dir}...')
    problem, problem_id = problem_handler.init_problem(tps_dir, problem_id, tioj, settings)
    
    if update_metadata:
        problem_handler.edit_problem(problem, problem_id, tioj, settings)

    if update_sample:
        problem_handler.upload_sample(problem, problem_id, tioj, settings)

    if update_checker and problem.metadata['specjudge_type'] != 'none':
        helper.throw_status(f"Detected sepcjudge_type: {problem.metadata['specjudge_type']}.")
        problem_handler.upload_checker(problem, problem_id, tioj, settings)

    if update_grader and problem.metadata['interlib_type'] != 'none':
        helper.throw_status(f"Detected interlib_type: {problem.metadata['interlib_type']}.")
        problem_handler.upload_grader(problem, problem_id, tioj, settings)

    if update_testdata:
        problem_handler.upload_testdata(problem, problem_id, tioj, settings)
    
    if update_subtasks_data:
        problem_handler.upload_subtasks_data(problem, problem_id, tioj, settings)

    helper.throw_info(f"Completed upload problem [bold]{problem.metadata['code']}[/bold] to TIOJ problem {problem_id}.")

@app.command()
def verify_problem(tps_dir: Path = typer.Argument(..., exists=True, file_okay=False, help='Path to the tps directory.')):
    '''
    Verify that a problem directory has a valid tps format, which is ready to be uploaded to TIOJ.
    '''
    problem_handler.Problem(tps_dir, settings)

@app.command()
def update_testcase(tps_dir: Path = typer.Argument(..., exists=True, file_okay=False, help='Path to the tps directory.'),
                    problem_id: str = typer.Argument('', help="The corresponding TIOJ problem id. Leave blank if you want to use 'tioj_problem_id' in problem.json."),
                    update_file: bool = typer.Option(True, help="Whether you want to update the input and output file. You can turn on --no-update-file to speed up if you only need to update the metadata (e.g., time limit) of the testcases.")):
    '''
    Update the testcase of a problem only. Need admin permission. 
    '''
    tioj = open_session(require_admin=True)

    problem, problem_id = problem_handler.init_problem(tps_dir, problem_id, tioj, settings)

    problem_handler.update_testcase(problem, problem_id, tioj, settings, update_file)

@app.command()
def update_metadata(problem_id: str = typer.Argument(..., help="The TIOJ problem id."),
                    attribute: str = typer.Argument(..., help="The attribute name, which must be listed in 'tioj_instance.auto_parse' of the file 'configs/tioj_instance.toml' to match the corresponding attribute on TIOJ."),
                    content: str = typer.Argument(..., help="The content of the metadata. It will fail if the input is not valid for TIOJ. You can see 'configs/metadata.schema' to learn valid inputs.")):
    '''
    Update a metadata attribute of a problem only. Need admin permission. 
    '''
    tioj = open_session(require_admin=True)

    problem_handler.update_metadata(problem_id, attribute, content, tioj, settings) 

@app.command()
def submit(problem_id: str = typer.Argument(..., help="The TIOJ problem id."),
           path: str = typer.Argument(..., help="The path to your program source."),
           compiler: Compiler = typer.Option(default="cplusplus17", help="The compiler."),
           replacement: str = typer.Option(default="", help="Replace keyword(s) to specific string(s). Doesn't support ':', ',', and whitespace in keywords or strings. Format: keyword1:string1,keyword2:string2,...")):
    '''
    Submit local program to TIOJ problem "problem_id". 
    '''
    tioj = open_session()
    replace = []
    for rep in replacement.split(','):
        rep = rep.strip().split(':')
        if len(rep) > 1:
            replace.append((rep[0], rep[1]))

    submit_submission(problem_id, path, settings.tioj_instance.compiler_list.index(compiler.value) + 1, replace, tioj, settings)

if __name__ == "__main__":
    app()
