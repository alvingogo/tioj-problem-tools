from os.path import basename
import glob

import src.helper as helper

'''
Requirement: None.

Description: Parse and verify sample testcases of a tps problem and store the file names of them in the problem structure.

             sample_source in problem.json says where the samples are: 'tests' takes the testcases
             matching path.sample, which makes the samples part of the testdata, and 'public'
             takes path.public_sample, the examples handed to contestants, which can differ from
             the testdata, such as another valid answer of a problem with a checker. Without it,
             a problem with a grader uses 'public', since a grader reads examples in a format
             of its own, and any other problem uses 'tests'.

Return value: None.
'''
def verify_sample(problem, settings):

    helper.throw_status(f'Parsing sample testcases...')
    
    source = problem.metadata.get('sample_source')
    if source is None:
        source = 'public' if problem.metadata.get('has_grader') else 'tests'

    if source == 'public':
        sample_inputs = glob.glob(problem.full_path(settings.path.public_sample + settings.path.input_suffix))
        sample_outputs = glob.glob(problem.full_path(settings.path.public_sample + settings.path.output_suffix))
    else:
        sample_inputs = glob.glob(problem.full_path(settings.path.sample + settings.path.input_suffix))
        sample_outputs = glob.glob(problem.full_path(settings.path.sample + settings.path.output_suffix))

    input_name = set(s[:-len(settings.path.input_suffix)] for s in sample_inputs) 
    output_name = set(s[:-len(settings.path.output_suffix)] for s in sample_outputs) 

    for testcase in input_name:
        if testcase not in output_name:
            helper.throw_error(f'{testcase}{settings.path.input_suffix} does not have a matched output.')

    for testcase in output_name:
        if testcase not in input_name:
            helper.throw_error(f'{testcase}{settings.path.output_suffix} does not have a matched input.')

    problem.samples = list(input_name)
    problem.samples.sort()

    if len(problem.samples) > 0:
        helper.throw_status('Found sample: ' + ', '.join([basename(s) for s in problem.samples]))
    else:
        helper.throw_warning('Didn\'t find any sample.')

