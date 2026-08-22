import typer
import json
import os
import sys
from dynaconf import Dynaconf
from pathlib import Path
from typing import Optional

from rich import print

import src.helper as helper
from src.session import open_session
import src.profile as profile_handler
from src.config import settings
from src.config import Compiler
import src.problem_handler as problem_handler
from src.submit import submit_submission

app = typer.Typer()

@app.callback()
def main():
    '''
    A tool for assisting TIOJ problem setting.

    Pass --profile <alias> anywhere on the command line, before or after the subcommand, to work
    against a TIOJ instance other than the current profile.
    '''

'''
Requirement: None.

Description: Take --profile out of the command line by hand. Declaring it as an option on every
             command would work too, but then it only reaches the commands that remember to
             declare it, and a command added later silently has no --profile at all. Pulling it
             out here means every command gets it, wherever it is written.

Return value: The alias, or None when it was not given, and the remaining arguments.
'''
def extract_profile(argv):
    alias, rest, index = None, [], 0
    while index < len(argv):
        arg = argv[index]
        if arg == '--':
            rest += argv[index:]
            break
        if arg in ('--profile', '-p'):
            if index + 1 >= len(argv):
                helper.throw_error(f'{arg} needs a profile alias.')
            alias = argv[index + 1]
            index += 2
            continue
        if arg.startswith('--profile='):
            alias = arg.split('=', 1)[1]
            index += 1
            continue
        rest.append(arg)
        index += 1
    return alias, rest


profile_app = typer.Typer(help='Manage the TIOJ instances and accounts you switch between.')
app.add_typer(profile_app, name='profile')

@profile_app.command('add')
def profile_add(alias: str = typer.Argument(..., help='The name you will refer to this instance by.'),
                url: str = typer.Option(None, '--url', help='The TIOJ url. Asked interactively when omitted.'),
                username: str = typer.Option(None, '--username', help='The TIOJ username. Asked interactively when omitted.')):
    '''
    Add a TIOJ instance and store its password in the system keyring.
    '''
    data = profile_handler.load_profiles()

    if alias in data['profiles']:
        typer.confirm(f'The profile "{alias}" already exists. Overwrite it?', abort=True)

    if url is None:
        url = typer.prompt('TIOJ url')
    if username is None:
        username = typer.prompt('TIOJ username')
    password = typer.prompt(f'(user: {username}) Password', hide_input=True)

    profile_handler.set_password(alias, password)

    data['profiles'][alias] = {'tioj_url': url, 'tioj_username': username}
    if data['current'] is None:
        data['current'] = alias
    path = profile_handler.save_profiles(data)

    helper.throw_info(f'Saved the profile [bold]{alias}[/bold] into {path}, its password is in the system keyring.')
    if data['current'] == alias:
        helper.throw_info(f'The current profile is now [bold]{alias}[/bold].')

@profile_app.command('use')
def profile_use(alias: str = typer.Argument(..., help='The profile alias to switch to.')):
    '''
    Switch the profile that every command uses by default.
    '''
    data = profile_handler.load_profiles()

    if alias not in data['profiles']:
        known = ', '.join(sorted(data['profiles'])) if data['profiles'] else '(none)'
        helper.throw_error(f'Unknown profile [bold]{alias}[/bold]. Known profiles: {known}.')

    data['current'] = alias
    profile_handler.save_profiles(data)

    entry = data['profiles'][alias]
    helper.throw_info(f"The current profile is now [bold]{alias}[/bold]: {entry['tioj_username']} at {entry['tioj_url']}.")

@profile_app.command('list')
def profile_list():
    '''
    List the known profiles.
    '''
    data = profile_handler.load_profiles()

    if not data['profiles']:
        helper.throw_info('No profile yet, add one with "tioj.py profile add <alias>".')
        return

    helper.throw_info(f'Profiles in {profile_handler.profiles_path()}:')
    for alias in sorted(data['profiles']):
        entry = data['profiles'][alias]
        marker = '*' if alias == data['current'] else ' '
        stored = profile_handler.has_password(alias)
        secret = 'password stored' if stored else ('no password' if stored is False else 'keyring unreachable')
        print(f"  {marker} [bold]{alias}[/bold]: {entry['tioj_username']} at {entry['tioj_url']} ({secret})")

@profile_app.command('remove')
def profile_remove(alias: str = typer.Argument(..., help='The profile alias to remove.'),
                   yes: bool = typer.Option(False, '--yes', '-y', help='Skip the confirmation prompt.')):
    '''
    Remove a profile and its stored password.
    '''
    data = profile_handler.load_profiles()

    if alias not in data['profiles']:
        known = ', '.join(sorted(data['profiles'])) if data['profiles'] else '(none)'
        helper.throw_error(f'Unknown profile [bold]{alias}[/bold]. Known profiles: {known}.')

    if not yes:
        typer.confirm(f'Remove the profile "{alias}" and its stored password?', abort=True)

    del data['profiles'][alias]
    if data['current'] == alias:
        data['current'] = next(iter(sorted(data['profiles'])), None)
    profile_handler.save_profiles(data)
    profile_handler.delete_password(alias)

    helper.throw_info(f'Removed the profile [bold]{alias}[/bold].')
    if data['current'] is not None:
        helper.throw_info(f"The current profile is now [bold]{data['current']}[/bold].")

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

'''
Requirement: None.

Description: Resolve the tri-state --update-*/--no-update-* switches of upload_problem, where
             None means the switch was not given on the command line.
             - none of them given: every part is updated;
             - only --update-* given: only the mentioned parts are updated;
             - only --no-update-* given: every part but the mentioned ones is updated;
             - both styles given: an error, since the intent is ambiguous.

Return value: A dict mapping every option name to whether that part should be updated.
'''
def resolve_update_options(options):
    selected = [name for name, value in options.items() if value is True]
    excluded = [name for name, value in options.items() if value is False]

    if selected and excluded:
        helper.throw_error('Cannot mix ' +
                           ', '.join(f'--update-{name.replace("_", "-")}' for name in selected) +
                           ' with ' +
                           ', '.join(f'--no-update-{name.replace("_", "-")}' for name in excluded) +
                           '. Use only one of the two styles.')

    if selected:
        return {name: name in selected for name in options}
    if excluded:
        return {name: name not in excluded for name in options}
    return {name: True for name in options}

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
                   update_metadata: Optional[bool] = typer.Option(None, help="Update the metadata in problem.json and the statements."),
                   update_sample: Optional[bool] = typer.Option(None, help="Update the sample testcases."),
                   update_checker: Optional[bool] = typer.Option(None, help="Update the checker."),
                   update_grader: Optional[bool] = typer.Option(None, help="Update the header and grader."),
                   update_testdata: Optional[bool] = typer.Option(None, help="Update the testcases. --no-update-testdata will give an effective speed up when you don't want to update testcases."),
                   update_subtasks_data: Optional[bool] = typer.Option(None, help="Update the subtasks' data.")):
    '''
    Upload a problem directory in tps format to TIOJ. Need admin permission.

    Every part is uploaded by default. Passing --update-* uploads only the mentioned parts,
    while passing --no-update-* uploads everything but the mentioned parts. Mixing the two
    styles is an error.
    '''
    update = resolve_update_options({
        'metadata': update_metadata,
        'sample': update_sample,
        'checker': update_checker,
        'grader': update_grader,
        'testdata': update_testdata,
        'subtasks_data': update_subtasks_data,
    })

    tioj = open_session(require_admin=True)

    helper.throw_status(f'Uploading problem {problem_id} to TIOJ with {tps_dir}...')
    problem, problem_id = problem_handler.init_problem(tps_dir, problem_id, tioj, settings)
    
    if update['metadata']:
        problem_handler.edit_problem(problem, problem_id, tioj, settings)

    if update['sample']:
        problem_handler.upload_sample(problem, problem_id, tioj, settings)

    if update['checker'] and problem.metadata['specjudge_type'] != 'none':
        helper.throw_status(f"Detected sepcjudge_type: {problem.metadata['specjudge_type']}.")
        problem_handler.upload_checker(problem, problem_id, tioj, settings)

    if update['grader'] and problem.metadata['interlib_type'] != 'none':
        helper.throw_status(f"Detected interlib_type: {problem.metadata['interlib_type']}.")
        problem_handler.upload_grader(problem, problem_id, tioj, settings)

    if update['testdata']:
        problem_handler.upload_testdata(problem, problem_id, tioj, settings)
    
    if update['subtasks_data']:
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
def update_tag(problem_id: str = typer.Argument(..., help="The TIOJ problem id."),
               tags: list[str] = typer.Argument(None, help="The tags to work on. A single argument may hold several of them separated by commas."),
               remove: bool = typer.Option(False, '--remove', '-r', help="Remove the given tags instead of adding them."),
               clear: bool = typer.Option(False, '--clear', help="Drop the existing tags first. On its own it empties the list, together with tags it replaces them."),
               solution: bool = typer.Option(False, '--solution', '-s', help="Work on the solution tags instead of the ones shown to everyone.")):
    '''
    Update the tags of a problem. The tags already on TIOJ are kept unless --remove or --clear says otherwise. Need admin permission.
    '''
    if remove and clear:
        helper.throw_error('Cannot use --remove together with --clear. --clear already drops everything.')
    if not tags and not clear:
        helper.throw_error('Give the tags to add, or --remove with the tags to drop, or --clear to empty the list.')
    if remove and not tags:
        helper.throw_error('--remove needs the tags to drop. Use --clear to drop all of them.')

    tioj = open_session(require_admin=True)

    problem_handler.update_tag(problem_id, tags or [], tioj, settings, remove=remove, clear=clear, solution=solution)

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
    alias, sys.argv = extract_profile(sys.argv)
    profile_handler.set_cli_override(alias)
    app()
