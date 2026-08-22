import src.helper as helper
from src.problem_handler.clean_subtasks_data import clean_subtasks_data
from src.problem_handler.get_data_idmap import get_data_idmap

# Replace the statement content to fit TIOJ's features.
def statement_filter(content, problem_id, problem):
    return content.replace('^', '^ ')

'''
Requirement: Admin permission.

Description: Update the subtasks' data of a tps problem to a TIOJ problem.

Return value: None.
'''
def upload_subtasks_data(problem, problem_id, tioj, settings):
    helper.throw_status(f"Uploading the subtasks' data of problem [bold]{problem.metadata['code']}[/bold] to TIOJ problem {problem_id}...")
   
    clean_subtasks_data(problem_id, tioj, settings)

    data_idmap = get_data_idmap(problem_id, tioj, settings)

    data = {}
    
    for sub in problem.subtasks['subtasks']:
        index = problem.subtasks['subtasks'][sub]['index']
        constraints = statement_filter(problem.subtasks['subtasks'][sub]['text'], problem_id, problem)
        score = str(problem.subtasks['subtasks'][sub]['score'])
        lists = []
        if sub in problem.mapping.tests_map:
            for test in sorted(list(problem.mapping.tests_map[sub])):
                if test in data_idmap:
                    lists += data_idmap[test]
                else:
                    helper.throw_warning(f'Cannot find testcase {test} on TIOJ problem {problem_id}.')
        data[settings.tioj_instance.subtasks_data_td_list % index] = helper.compress_id_list(lists)
        data[settings.tioj_instance.subtasks_data_constraints % index] = constraints
        data[settings.tioj_instance.subtasks_data_score % index] = score
        data[settings.tioj_instance.subtasks_data_destroy % index] = 'false'

    response = tioj.submit_form(settings.endpoints.edit_problem % problem_id, data=data)
    
    helper.throw_info(f"Completed upload the subtasks' data of problem [bold]{problem.metadata['code']}[/bold] to TIOJ problem {problem_id}.")
