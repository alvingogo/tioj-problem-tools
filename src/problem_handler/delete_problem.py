import src.helper as helper
from src.problem_handler.clean_sample import clean_sample
from src.problem_handler.clean_subtasks_data import clean_subtasks_data
from src.problem_handler.clean_testdata import clean_testdata

'''
Requirement: Admin permission.

Description: Remove all the content of a TIOJ problem, which resets it to an empty problem.
             The problem id is retained so that it can be reused later.

Return value: None.
'''
def delete_problem(problem_id, tioj, settings):
    helper.throw_status(f'Deleting the content of TIOJ problem {problem_id}...')

    clean_testdata(problem_id, tioj, settings)
    clean_sample(problem_id, tioj, settings)
    clean_subtasks_data(problem_id, tioj, settings)

    helper.throw_status(f'Cleaning the metadata of TIOJ problem {problem_id}...')

    data = {}

    for prop in settings.tioj_instance.auto_upload.__dict__['_box_config']['__safe_keys']:
        data[eval(f'settings.tioj_instance.auto_upload.{prop}')] = ''

    for prop in settings.tioj_instance.auto_parse.__dict__['_box_config']['__safe_keys']:
        if prop in settings.tioj_instance.empty_value:
            data[eval(f'settings.tioj_instance.auto_parse.{prop}')] = str(eval(f'settings.tioj_instance.empty_value.{prop}'))
        else:
            helper.throw_warning(f'Cannot match {prop} from tioj_instance.auto_parse with tioj_instance.empty_value.')

    data[settings.tioj_instance.checker] = ''
    data[settings.tioj_instance.header] = ''
    data[settings.tioj_instance.grader] = ''

    response = tioj.submit_form(settings.endpoints.edit_problem % problem_id, data=data)

    helper.throw_info(f'Completed delete the content of TIOJ problem {problem_id}.')
