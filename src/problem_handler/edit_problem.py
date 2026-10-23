from os.path import isfile
import re

import src.helper as helper

# Replace the statement content to fit TIOJ's features.
def statement_filter(content, problem_id, problem, path):
    if re.match(r".*\.md$", path):
        content = content.replace('^', '^ ')
    content = content.replace(problem.metadata['code'] + '.h', 'lib%04d.h' % int(problem_id))
    return content

# Add a statement file into the form's data. A missing file is left out of the form, which leaves
# whatever TIOJ already holds in that field alone; with clear_missing it is uploaded as an empty
# string instead, so that the tps directory always overwrites TIOJ.
def add_statement(data, name, path, found_msg, problem_id, problem, clear_missing):
    if isfile(path):
        helper.throw_status(found_msg)
        data[name] = statement_filter(helper.read_file(path), problem_id, problem, path)
    elif clear_missing:
        helper.throw_warning(f'Cannot find {path}, clearing the corresponding field on TIOJ.')
        data[name] = ''

'''
Requirement: Admin permission.

Description: Parse problem.json and the statements. Upload them to a TIOJ problem.

Return value: None
'''
def edit_problem(problem, problem_id, tioj, settings, clear_missing_statements=False):
    helper.throw_status(f"Editing the metadata of problem [bold]{problem.metadata['code']}[/bold] on TIOJ problem {problem_id}...")
    
    data = {}
    
    for prop in settings.tioj_instance.auto_upload.__dict__['_box_config']['__safe_keys']:
        if prop in settings.path.auto_upload.__dict__['_box_config']['__safe_keys']:
            add_statement(data, eval(f'settings.tioj_instance.auto_upload.{prop}'), problem.full_path(eval(f'settings.path.auto_upload.{prop}')), f'Found {prop}!', problem_id, problem, clear_missing_statements)
        else:
            helper.throw_warning(f'Cannot match {prop} from tioj_instance.auto_upload with path.auto_upload.')
   
    for prop in settings.tioj_instance.auto_parse.__dict__['_box_config']['__safe_keys']:
        if prop in problem.metadata:
            data[eval(f'settings.tioj_instance.auto_parse.{prop}')] = problem.metadata[prop]

    response = tioj.submit_form(settings.endpoints.edit_problem % problem_id, data=data)
    
    helper.throw_info(f"Completed edit the metadata of problem [bold]{problem.metadata['code']}[/bold] on TIOJ problem {problem_id}.")
