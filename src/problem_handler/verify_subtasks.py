import json
import jsonschema
from jsonschema import validate

import src.helper as helper
from src.tps_parser import get_data_mapping

'''
Requirement: None.

Description: Parse and verify subtasks.json and gen/data of a tps problem, storing them in the problem structure, and generate the mapping from subtasks to testcases.

Return value: None.
'''
def verify_subtasks(problem, settings):
    helper.throw_status(f'Parsing subtasks.json...')
    
    problem.subtasks = helper.read_json(problem.full_path(settings.path.subtasks))
    schema = helper.read_json(settings.default.subtasks_schema)
    try:
        validate(instance=problem.subtasks, schema=schema)
    except jsonschema.exceptions.ValidationError as err:
        helper.throw_error(str(err))

    for prop in schema['properties']:
        if (prop not in problem.subtasks) and ('default' in schema['properties'][prop]):
            problem.subtasks[prop] = schema['properties'][prop]['default']

    subtask_properties = schema['properties']['subtasks']['patternProperties']['.*']['properties']
    for sub in problem.subtasks['subtasks']:
        for prop in subtask_properties:
            if (prop not in problem.subtasks['subtasks'][sub]) and ('default' in subtask_properties[prop]):
                problem.subtasks['subtasks'][sub][prop] = subtask_properties[prop]['default']

    indices = []
    sum_of_score = float(0)

    for sub in problem.subtasks['subtasks']:
        idx = problem.subtasks['subtasks'][sub]['index']
        helper.throw_status(f'Found subtask [bold]{sub}[/bold] (index: {idx})')
        indices.append(idx)
        sum_of_score += problem.subtasks['subtasks'][sub]['score']

    if len(indices) != len(set(indices)):
        helper.throw_error('Repeated subtask indices.')
    
    problem.gen_file = helper.read_file(problem.full_path(settings.path.gen_file)).split('\n')
    
    problem.mapping = get_data_mapping(problem)
    for sub in problem.subtasks['subtasks']:
        if sub not in problem.mapping.tests_map:
            helper.throw_warning(f'None of the testcase matched subtask {sub}.')

    helper.throw_status(f'Sum of score: {sum_of_score}')
