import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from os.path import join

from bs4 import BeautifulSoup

import src.helper as helper

# The fields of the edit form that a tps directory has no place for, with the value TIOJ gives a
# new problem. A problem that changed one of them is downloaded without that change, so the user is
# told about it rather than finding out after the upload.
UNSUPPORTED_FIELDS = {
    'problem[specjudge_compile_args]': '',
    'problem[_problem_prog_enabled]': '0',
    'problem[problem_prog_code]': '',
    'problem[judge_abnormally_terminated]': '0',
    'problem[default_scoring_args]': '',
    'problem[code_length_limit]': '5000000',
    'problem[ranklist_display_score]': '0',
    'problem[skip_group]': '0',
    'problem[summary_type]': 'none',
    'problem[summary_code]': '',
    'problem[score_precision]': '2',
}

# A run of testcases goes into one testset, and tps names a test '<testset>-<offset>' with the
# offset written in two digits. Past 99 the names stop sorting in their real order, and the upload
# sends testcases in sorted order, so a longer run is split.
MAX_TESTSET_SIZE = 99

# html_form_to_dict gives a checkbox as a list of the hidden '0' and, when it is checked, '1'.
def form_value(form, name):
    value = form.get(name, '')
    if isinstance(value, list):
        return value[-1] if value else ''
    return value

def as_number(text):
    number = float(text)
    return int(number) if number.is_integer() else number

# Undo the '^' to '^ ' of statement_filter in edit_problem and upload_subtasks_data, so that
# uploading the downloaded text again gives back what TIOJ holds now instead of piling up another
# round of spaces. The lib<problem id>.h that edit_problem writes for the grader header is left as
# it is.
def unfilter_statement(content):
    return content.replace('^ ', '^')

# Undo helper.replace_header: a header that was pasted in on upload becomes an #include again. A
# header that differs from the one in files/ in any way is left inlined, which still uploads fine.
def unreplace_header(content, settings):
    path = helper.expand_settings_variable(settings.default.replace_header_paths)
    for header in settings.default.replace_headers:
        content = content.replace(helper.read_file(join(path, header)), f'#include "{header}"')
    return content

def write_text(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as file:
        file.write(content)

# Unlike helper.write_json, keep non-ASCII text such as a Chinese title readable.
def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
        file.write('\n')

def read_bytes(path):
    with open(path, 'rb') as file:
        return file.read()

def decompress_zstd(source, destination):
    try:
        from compression import zstd
    except ImportError:
        zstd = None

    if zstd is not None:
        with zstd.open(source, 'rb') as reader, open(destination, 'wb') as writer:
            shutil.copyfileobj(reader, writer)
        return

    try:
        result = subprocess.run(['zstd', '-d', '-q', '-f', '-o', destination, source], capture_output=True, text=True)
    except FileNotFoundError:
        helper.throw_error('A testcase is stored compressed on TIOJ, but neither the python module compression.zstd (Python 3.14+) nor the "zstd" command is available to decompress it.')
    if result.returncode != 0:
        helper.throw_error(f'Cannot decompress {source}: ' + result.stderr.strip())

'''
Requirement: Admin permission.

Description: Read the testcase list of a TIOJ problem.

Return value: A list ordered by position, of dictionaries holding the file names, the download
              endpoints, whether each file is compressed and the limits of the testcase.
'''
def get_testdata_list(problem_id, tioj, settings):
    page = tioj.get(settings.endpoints.testdata_list % problem_id)
    soup = BeautifulSoup(page.text, 'html.parser')

    testdata = []
    for tr in soup.find_all('tr')[1:]:
        tds = tr.find_all('td')
        links = {}
        for a in tr.find_all('a', href=True):
            match = re.search(r'[?&]type=(input|output)', a['href'])
            if match:
                links[match.group(1)] = a
        if 'input' not in links or 'output' not in links:
            helper.throw_error(f'Cannot find the download links of testcase #{tds[0].get_text(strip=True)} on TIOJ problem {problem_id}, maybe your TIOJ has an unexpected format?')

        testdata.append({
            'position': int(tds[0].get_text(strip=True)),
            'input_name': tds[1].get_text(strip=True),
            'output_name': tds[3].get_text(strip=True),
            'input_endpoint': links['input']['href'],
            'output_endpoint': links['output']['href'],
            'input_compressed': 'zstd' in links['input'].get_text(),
            'output_compressed': 'zstd' in links['output'].get_text(),
            'time_limit': tds[5].get_text(strip=True),
            'vss_limit': tds[6].get_text(strip=True),
            'rss_limit': tds[7].get_text(strip=True),
            'output_limit': tds[8].get_text(strip=True),
        })

    return sorted(testdata, key=lambda td: td['position'])

def download_testcase(testcase, kind, path, tioj):
    if testcase[f'{kind}_name'] == 'Nil':
        helper.throw_error(f"Testcase #{testcase['position']} has no {kind} file on TIOJ.")
    if not testcase[f'{kind}_compressed']:
        tioj.download(testcase[f'{kind}_endpoint'], path)
        return
    with tempfile.TemporaryDirectory() as directory:
        compressed = join(directory, 'testcase.zst')
        tioj.download(testcase[f'{kind}_endpoint'], compressed)
        decompress_zstd(compressed, path)

'''
Requirement: None.

Description: One limit of the testcases, which tps keeps once for the whole problem. TIOJ keeps it
             per testcase, so differing values are reported and the largest one is kept.

Return value: The value in TIOJ's unit, or None when no testcase sets it.
'''
def common_limit(testdata, key, description):
    values = [int(td[key]) for td in testdata if td[key].lstrip('-').isdigit()]
    if not values:
        return None
    counts = Counter(values)
    if len(counts) > 1:
        helper.throw_warning(f'The testcases have different {description}s ({", ".join(f"{v} x{c}" for v, c in sorted(counts.items()))}), '
                             f'problem.json can only hold one, so every testcase gets the largest, {max(values)}.')
    return max(values)

def parse_td_list(td_list, count):
    positions = set()
    for part in td_list.split(','):
        part = part.strip()
        if part == '':
            continue
        match = re.fullmatch(r'(\d+)\s*-\s*(\d+)', part)
        first, last = (int(match.group(1)), int(match.group(2))) if match else (int(part), int(part))
        positions |= {p for p in range(first, last + 1) if p < count}
    return positions

def read_subtasks(form):
    subtasks = []
    index = 0
    while f'problem[subtasks_attributes][{index}][td_list]' in form:
        subtasks.append({
            'td_list': form_value(form, f'problem[subtasks_attributes][{index}][td_list]'),
            'constraints': form_value(form, f'problem[subtasks_attributes][{index}][constraints]'),
            'score': form_value(form, f'problem[subtasks_attributes][{index}][score]'),
        })
        index += 1
    return subtasks

def read_samples(form):
    samples = []
    index = 0
    while f'problem[sample_testdata_attributes][{index}][input]' in form:
        samples.append((form_value(form, f'problem[sample_testdata_attributes][{index}][input]'),
                        form_value(form, f'problem[sample_testdata_attributes][{index}][output]')))
        index += 1
    return samples

'''
Requirement: None.

Description: Arrange the testcases into testsets for gen/data. tps only puts a test into a subtask
             through the testsets the subtask includes, so consecutive testcases that belong to
             exactly the same subtasks share a testset, and every subtask includes the testsets
             of its testcases. When the first testcases are the samples, they form the testset
             '0', whose tests tps names '0-*', which is where upload-problem takes the samples
             from.

Return value: A list of (testset name, list of positions), in position order.
'''
def group_testdata(count, memberships, sample_count):
    groups = []
    for position in range(count):
        key = '0' if position < sample_count else memberships[position]
        if groups and groups[-1][0] == key and (key == '0' or len(groups[-1][1]) < MAX_TESTSET_SIZE):
            groups[-1][1].append(position)
        else:
            groups.append([key, [position]])

    width = len(str(sum(1 for key, _ in groups if key != '0')))
    named, serial = [], 0
    for key, positions in groups:
        if key == '0':
            named.append(('0', positions))
        else:
            serial += 1
            named.append((f't{serial:0{width}d}', positions))
    return named

def write_public_samples(samples, tps_directory, settings):
    for index, (sample_input, sample_output) in enumerate(samples):
        name = join(tps_directory, settings.path.public_sample.replace('*', f'{index + 1:02d}'))
        write_text(name + settings.path.input_suffix, sample_input)
        write_text(name + settings.path.output_suffix, sample_output)

def samples_lead_testdata(samples, testdata, memberships, directory):
    if not samples or len(samples) > min(len(testdata), MAX_TESTSET_SIZE):
        return False
    for position, (sample_input, sample_output) in enumerate(samples):
        if memberships[position] != memberships[0]:
            return False
        if (read_bytes(join(directory, f'{position}.in')) != sample_input.encode()
                or read_bytes(join(directory, f'{position}.out')) != sample_output.encode()):
            return False
    return True

'''
Requirement: Admin permission.

Description: Download a TIOJ problem into a new tps directory that upload-problem accepts, so that
             it can be uploaded to another TIOJ instance. Nothing is written to TIOJ.

             The upload is undone where it changed things on the way: the statement filters are
             reversed and the headers in files/ become #include lines again. What a tps
             directory cannot express is reported as a warning rather than silently dropped:
             the edit form fields this tool does not upload, limits that differ between
             testcases and samples that are not among the testdata.

             TIOJ keeps no solution, so solutions.json names a placeholder as the model
             solution, which verify-problem requires.

             The problem is downloaded as invisible unless keep_visible_state is set, so that
             uploading it never publishes it by accident.

Return value: None.
'''
def download_problem(problem_id, tps_directory, code, keep_visible_state, tioj, settings):
    if not problem_id.isdigit():
        helper.throw_error('problem_id must be digits')
    problem_id = str(int(problem_id))
    code = code or f'tioj{problem_id}'

    if os.path.exists(tps_directory) and (not os.path.isdir(tps_directory) or os.listdir(tps_directory)):
        helper.throw_error(f'{tps_directory} already exists and is not an empty directory.')

    helper.throw_status(f'Downloading TIOJ problem {problem_id} into {tps_directory} (problem code: [bold]{code}[/bold])...')

    form, _ = tioj.get_form(settings.endpoints.edit_problem % problem_id)
    path = lambda p: join(tps_directory, p)

    for field, default in UNSUPPORTED_FIELDS.items():
        if form_value(form, field) not in (default, ''):
            helper.throw_warning(f'{field} is set on TIOJ but a tps directory has no place for it, it will not be downloaded.')

    # metadata
    metadata = {'name': code, 'code': code, 'type': 'Batch'}
    integer_fields = {'num_processes', 'specjudge_compiler_id', 'judge_between_stages', 'strict_mode'}
    for prop, field in settings.tioj_instance.auto_parse.items():
        if field in form:
            value = form_value(form, field)
            metadata[prop] = int(value) if prop in integer_fields and value.lstrip('-').isdigit() else value
    # A public problem would otherwise go public on the instance it is uploaded to the moment the
    # upload finishes, before anyone had a chance to look at it there.
    if not keep_visible_state and metadata.get('visible_state', 'invisible') != 'invisible':
        helper.throw_status(f"The problem is {metadata['visible_state']} on TIOJ, it is downloaded as invisible. Pass --keep-visible-state to keep it.")
        metadata['visible_state'] = 'invisible'
    metadata['has_checker'] = metadata.get('specjudge_type', 'none') != 'none'
    metadata['has_grader'] = metadata.get('interlib_type', 'none') != 'none'
    if metadata['has_checker']:
        helper.throw_warning(f"The special judge compiler is id {metadata.get('specjudge_compiler_id')} on this instance, compiler ids can differ between TIOJ instances.")

    # statements
    for prop, field in settings.tioj_instance.auto_upload.items():
        if prop in settings.path.auto_upload:
            write_text(path(settings.path.auto_upload[prop]), unfilter_statement(form_value(form, field)))
        else:
            helper.throw_warning(f'Cannot match {prop} from tioj_instance.auto_upload with path.auto_upload.')

    # checker and grader
    if metadata['has_checker']:
        write_text(path(settings.path.checker), unreplace_header(form_value(form, settings.tioj_instance.checker), settings))
    if metadata['has_grader']:
        write_text(path(settings.path.header % code), unreplace_header(form_value(form, settings.tioj_instance.header), settings))
        write_text(path(settings.path.grader), unreplace_header(form_value(form, settings.tioj_instance.grader), settings))

    # testdata
    testdata = get_testdata_list(problem_id, tioj, settings)
    helper.throw_status(f'Found {len(testdata)} testcases.')

    download_directory = path('.download')
    os.makedirs(download_directory)
    for td in testdata:
        helper.throw_status(f"Downloading testcase #{td['position']} ({td['input_name']}, {td['output_name']})...")
        download_testcase(td, 'input', join(download_directory, f"{td['position']}.in"), tioj)
        download_testcase(td, 'output', join(download_directory, f"{td['position']}.out"), tioj)

    time_limit = common_limit(testdata, 'time_limit', 'time limit')
    vss_limit = common_limit(testdata, 'vss_limit', 'memory limit (VSS)')
    rss_limit = common_limit(testdata, 'rss_limit', 'memory limit (RSS)')
    output_limit = common_limit(testdata, 'output_limit', 'output limit')
    if time_limit is not None:
        metadata['time_limit'] = as_number(time_limit / 1000)
    if vss_limit is not None:
        metadata['memory_limit'] = as_number(vss_limit / 1024)
    elif testdata:
        helper.throw_warning('No testcase has a VSS limit, upload-problem always sets one and will use the default of metadata.schema.')
    if rss_limit is not None:
        metadata['rss_limit'] = as_number(rss_limit / 1024)
    if output_limit is not None:
        metadata['output_limit'] = as_number(output_limit / 1024)

    # subtasks
    subtasks = read_subtasks(form)
    memberships = [frozenset(i for i, sub in enumerate(subtasks) if td['position'] in parse_td_list(sub['td_list'], len(testdata)))
                   for td in testdata]

    # samples
    samples = read_samples(form)
    sample_count = 0
    if metadata['has_grader']:
        write_public_samples(samples, tps_directory, settings)
    elif samples_lead_testdata(samples, testdata, memberships, download_directory):
        sample_count = len(samples)
    elif samples:
        write_public_samples(samples, tps_directory, settings)
        helper.throw_warning(f'The {len(samples)} sample(s) are not the first testcases, so tps has no place for them that upload-problem reads. '
                             f'They are saved in {os.path.dirname(settings.path.public_sample)}/ but uploading this directory leaves the problem without samples.')

    groups = group_testdata(len(testdata), memberships, sample_count)

    os.makedirs(path(os.path.dirname(settings.path.testdata)))
    gen_data = [f'# Downloaded from TIOJ problem {problem_id} at {tioj.tioj_url}.',
                '# The tests were downloaded rather than generated, each line names the testcase on TIOJ.']
    for name, positions in groups:
        gen_data += ['', f'@testset {name}']
        for offset, position in enumerate(positions, start=1):
            test = f'{name}-{offset:02d}'
            gen_data.append(f"manual {testdata[position]['input_name']}")
            target = path(settings.path.testdata.replace('*', test))
            os.replace(join(download_directory, f'{position}.in'), target + settings.path.input_suffix)
            os.replace(join(download_directory, f'{position}.out'), target + settings.path.output_suffix)
    os.rmdir(download_directory)

    subtasks_json = {'subtasks': {}}
    for index, sub in enumerate(subtasks):
        name = f'subtask{index}'
        subtasks_json['subtasks'][name] = {
            'index': index,
            'score': as_number(sub['score'] or 0),
            'text': unfilter_statement(sub['constraints']),
        }
        gen_data += ['', f'@subtask {name}']
        gen_data += [f'@include {group_name}' for group_name, positions in groups
                     if any(index in memberships[p] for p in positions)]

    write_text(path(settings.path.gen_file), '\n'.join(gen_data) + '\n')
    write_json(path(settings.path.subtasks), subtasks_json)
    write_json(path(settings.path.metadata), metadata)
    write_json(path(settings.path.solutions), {
        'placeholder': {'verdict': settings.default.solution_code_verdict,
                        'note': 'TIOJ keeps no solution, this entry only makes the directory pass verify-problem.'}
    })

    helper.throw_info(f'Completed download TIOJ problem {problem_id} into {tps_directory}.')
