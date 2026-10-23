import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from os.path import join

import jsonschema
from bs4 import BeautifulSoup
from html_form_to_dict import html_form_to_dict
from jsonschema import validate
from rich.markup import escape

import src.helper as helper

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

# Turn a form value into the type metadata.schema asks for. A value that does not convert is kept
# as it is, so that the validation at the end names the field instead of a ValueError here.
def convert_by_schema(value, schema):
    try:
        if schema.get('type') == 'integer':
            return int(value)
        if schema.get('type') == 'number':
            return as_number(value)
    except ValueError:
        return value
    if schema.get('type') == 'boolean':
        return value in ('1', 'true')
    return value

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

def read_subtasks(form, settings):
    subtasks = []
    index = 0
    while settings.tioj_instance.subtasks_data_td_list % index in form:
        subtasks.append({
            'td_list': form_value(form, settings.tioj_instance.subtasks_data_td_list % index),
            'constraints': form_value(form, settings.tioj_instance.subtasks_data_constraints % index),
            'score': form_value(form, settings.tioj_instance.subtasks_data_score % index),
        })
        index += 1
    return subtasks

def read_samples(form, settings):
    samples = []
    index = 0
    while settings.tioj_instance.sample_input % index in form:
        samples.append((form_value(form, settings.tioj_instance.sample_input % index),
                        form_value(form, settings.tioj_instance.sample_output % index)))
        index += 1
    return samples

# TIOJ shows a sample as plain text unless told otherwise, which tps has no way to say.
def warn_sample_display_types(form, count, settings):
    for index in range(count):
        display_type = form_value(form, settings.tioj_instance.sample_display_type % index)
        if display_type not in ('', 'plaintext'):
            helper.throw_warning(f'Sample {index} is shown as {display_type} on TIOJ but a tps directory has no place for it, it will not be downloaded.')

# The banned compilers are checkboxes holding compiler ids, which can mean different compilers on
# another instance, so they are reported by the names on their buttons instead of being kept.
def warn_banned_compilers(page, settings):
    soup = BeautifulSoup(page, 'html.parser')
    names = []
    for checkbox in soup.find_all('input', attrs={'name': settings.tioj_instance.banned_compilers}):
        if checkbox.has_attr('checked'):
            button = checkbox.find_previous_sibling('button')
            names.append(button.get_text(strip=True) if button else f"id {checkbox.get('value')}")
    if names:
        helper.throw_warning(f'The problem bans the compilers {", ".join(names)} on TIOJ but a tps directory has no place for it, they will not be banned after the upload.')

'''
Requirement: None.

Description: The testset name that makes tps name a test the way settings.path.sample matches,
             which for 'tests/0-*' is '0'.

Return value: The name, or None when path.sample is not '<testdata directory>/<name>-*'.
'''
def sample_testset_name(settings):
    testdata_directory = os.path.dirname(settings.path.testdata)
    sample_directory, sample_pattern = os.path.split(settings.path.sample)
    match = re.fullmatch(r'([^*?\[\]]+)-\*', sample_pattern)
    if sample_directory != testdata_directory or match is None:
        return None
    return match.group(1)

'''
Requirement: None.

Description: Arrange the testcases into testsets for gen/data. tps only puts a test into a subtask
             through the testsets the subtask includes, so consecutive testcases that belong to
             exactly the same subtasks share a testset, and every subtask includes the testsets
             of its testcases. When the first testcases are the samples, they form the testset
             sample_name, whose tests match settings.path.sample, which is where upload-problem
             takes the samples from.

Return value: A list of (testset name, list of positions), in position order.
'''
def group_testdata(count, memberships, sample_count, sample_name):
    groups = []
    for position in range(count):
        key = sample_name if position < sample_count else memberships[position]
        if groups and groups[-1][0] == key and (key == sample_name or len(groups[-1][1]) < MAX_TESTSET_SIZE):
            groups[-1][1].append(position)
        else:
            groups.append([key, [position]])

    # The other testsets are 't<serial>', or 'u<serial>' should the sample testset take that form.
    prefix = 'u' if sample_name is not None and re.fullmatch(r't\d+', sample_name) else 't'
    width = len(str(sum(1 for key, _ in groups if key != sample_name)))
    named, serial = [], 0
    for key, positions in groups:
        if key == sample_name:
            named.append((sample_name, positions))
        else:
            serial += 1
            named.append((f'{prefix}{serial:0{width}d}', positions))
    return named

def write_public_samples(samples, tps_directory, settings):
    for index, (sample_input, sample_output) in enumerate(samples):
        name = join(tps_directory, settings.path.public_sample.replace('*', f'{index + 1:02d}'))
        write_text(name + settings.path.input_suffix, sample_input)
        write_text(name + settings.path.output_suffix, sample_output)

# A sample typed into the edit page comes back with the CRLF a browser submits a textarea with,
# and with or without a newline at the end, while the testcase holding the same data is an
# uploaded file with neither, so the two are compared the way a judge compares output.
def same_text(data, text):
    normalize = lambda content: content.replace(b'\r\n', b'\n').rstrip(b'\n')
    return normalize(data) == normalize(text.encode())

def samples_lead_testdata(samples, testdata, memberships, directory):
    if not samples or len(samples) > min(len(testdata), MAX_TESTSET_SIZE):
        return False
    for position, (sample_input, sample_output) in enumerate(samples):
        if memberships[position] != memberships[0]:
            return False
        if (not same_text(read_bytes(join(directory, f'{position}.in')), sample_input)
                or not same_text(read_bytes(join(directory, f'{position}.out')), sample_output)):
            return False
    return True

'''
Requirement: Admin permission.

Description: Download a TIOJ problem into a tps directory that upload-problem accepts, so that
             it can be uploaded to another TIOJ instance. Nothing is written to TIOJ.

             The problem is written into a temporary directory next to tps_directory, which takes
             its place only once everything is downloaded, so a failure halfway leaves neither a
             partial directory nor, when replace is set, a deleted one. A tps_directory that
             already holds something is refused unless replace is set, in which case all of it is
             deleted: leftovers such as testcases under other names would otherwise be uploaded
             along with the problem.

             The upload is undone where it changed things on the way: the statement filters are
             reversed and the headers in files/ become #include lines again. What a tps
             directory cannot express is reported as a warning rather than silently dropped:
             the edit form fields this tool does not upload, limits that differ between
             testcases and samples that are not among the testdata.

             TIOJ keeps no solution, so solutions.json names a placeholder as the model
             solution, which verify-problem requires.

             The problem is downloaded as invisible unless keep_visible_state is set, so that
             uploading it never publishes it by accident, and without tags unless keep_tags is
             set.

Return value: None.
'''
def download_problem(problem_id, tps_directory, code, keep_visible_state, keep_tags, replace, tioj, settings):
    if not problem_id.isdigit():
        helper.throw_error('problem_id must be digits')
    problem_id = str(int(problem_id))
    code = code or f'tioj{problem_id}'

    if os.path.exists(tps_directory) and not os.path.isdir(tps_directory):
        helper.throw_error(f'{tps_directory} already exists and is not a directory.')
    occupied = os.path.isdir(tps_directory) and len(os.listdir(tps_directory)) > 0
    if occupied and not replace:
        helper.throw_error(f'{tps_directory} already exists and is not an empty directory.')

    helper.throw_status(f'Downloading TIOJ problem {problem_id} into {tps_directory} (problem code: [bold]{code}[/bold])...')

    parent = os.path.dirname(os.path.abspath(tps_directory))
    os.makedirs(parent, exist_ok=True)
    staging = tempfile.mkdtemp(prefix=f'.{os.path.basename(os.path.abspath(tps_directory))}.download-', dir=parent)
    try:
        write_problem(problem_id, staging, code, keep_visible_state, keep_tags, tioj, settings)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    if os.path.isdir(tps_directory):
        if occupied:
            helper.throw_status(f'Deleting the old content of {tps_directory}...')
        shutil.rmtree(tps_directory)
    os.rename(staging, tps_directory)

    helper.throw_info(f'Completed download TIOJ problem {problem_id} into {tps_directory}.')

'''
Requirement: Admin permission.

Description: Write a TIOJ problem into tps_directory, which exists and is empty. See
             download_problem.

Return value: None.
'''
def write_problem(problem_id, tps_directory, code, keep_visible_state, keep_tags, tioj, settings):
    page = tioj.get(settings.endpoints.edit_problem % problem_id).content
    try:
        form = dict(html_form_to_dict(page))
    except IndexError:
        helper.throw_error(f'Cannot find a form at endpoint {settings.endpoints.edit_problem % problem_id}')
    path = lambda p: join(tps_directory, p)

    for field, default in settings.tioj_instance.unsupported.items():
        if form_value(form, field) not in (default, ''):
            helper.throw_warning(f'{escape(field)} is set on TIOJ but a tps directory has no place for it, it will not be downloaded.')
    warn_banned_compilers(page, settings)

    # metadata
    metadata_schema = helper.read_json(settings.default.metadata_schema)
    metadata = {'name': code, 'code': code}
    for prop, field in settings.tioj_instance.auto_parse.items():
        if field in form:
            metadata[prop] = convert_by_schema(form_value(form, field), metadata_schema['properties'].get(prop, {}))

    # TIOJ has no problem type. upload-problem sends num_processes as the number of stages, so
    # more than one stage is what a Communication task leaves behind. A TwoSteps task looks the
    # same on TIOJ, and an OutputOnly one looks like a Batch task with a checker, neither of which
    # can be told apart from here.
    if isinstance(metadata.get('num_processes'), int) and metadata['num_processes'] > 1:
        metadata['type'] = 'Communication'
        helper.throw_warning(f"The problem runs in {metadata['num_processes']} stages on TIOJ, it is downloaded as a Communication task with num_processes {metadata['num_processes']}. "
                             'Change "type" in problem.json if it was a TwoSteps task.')
    else:
        metadata['type'] = 'Batch'
        metadata.pop('num_processes', None)
    # A public problem would otherwise go public on the instance it is uploaded to the moment the
    # upload finishes, before anyone had a chance to look at it there.
    if not keep_visible_state and metadata.get('visible_state', 'invisible') != 'invisible':
        helper.throw_status(f"The problem is {metadata['visible_state']} on TIOJ, it is downloaded as invisible. Pass --keep-visible-state to keep it.")
        metadata['visible_state'] = 'invisible'
    # The tags belong to the instance they were given on, where another instance may well use a
    # different set, and solution tags give the solution away, so neither is carried over.
    if not keep_tags:
        for prop in ('tag_list', 'solution_tag_list'):
            if metadata.get(prop):
                helper.throw_status(f'The problem has {prop} "{escape(metadata[prop])}" on TIOJ, it is downloaded empty. Pass --keep-tags to keep it.')
                metadata[prop] = ''
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
        metadata['time_limit'] = time_limit / 1000
    if vss_limit is not None:
        metadata['memory_limit'] = as_number(vss_limit / 1024)
    elif testdata:
        helper.throw_warning('No testcase has a VSS limit, upload-problem always sets one and will use the default of metadata.schema.')
    if rss_limit is not None:
        metadata['rss_limit'] = as_number(rss_limit / 1024)
    if output_limit is not None:
        metadata['output_limit'] = as_number(output_limit / 1024)

    # subtasks
    subtasks = read_subtasks(form, settings)
    memberships = [frozenset(i for i, sub in enumerate(subtasks) if td['position'] in parse_td_list(sub['td_list'], len(testdata)))
                   for td in testdata]

    # samples
    samples = read_samples(form, settings)
    warn_sample_display_types(form, len(samples), settings)
    sample_name = sample_testset_name(settings)
    sample_count = 0
    if metadata['has_grader']:
        write_public_samples(samples, tps_directory, settings)
    elif sample_name is not None and samples_lead_testdata(samples, testdata, memberships, download_directory):
        sample_count = len(samples)
    elif samples:
        write_public_samples(samples, tps_directory, settings)
        reason = ('are not the first testcases' if sample_name is not None
                  else f'cannot be named after path.sample "{settings.path.sample}", which is not "<testdata directory>/<name>-*"')
        helper.throw_warning(f'The {len(samples)} sample(s) {reason}, so tps has no place for them that upload-problem reads. '
                             f'They are saved in {os.path.dirname(settings.path.public_sample)}/ but uploading this directory leaves the problem without samples.')

    groups = group_testdata(len(testdata), memberships, sample_count, sample_name)

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

    # Checked here rather than left to verify-problem, so that a field TIOJ fills differently from
    # what the schemas expect is reported by the command that wrote it.
    for json_path, schema_path in ((settings.path.metadata, settings.default.metadata_schema),
                                   (settings.path.subtasks, settings.default.subtasks_schema),
                                   (settings.path.solutions, settings.default.solutions_schema)):
        try:
            validate(instance=helper.read_json(path(json_path)), schema=helper.read_json(schema_path))
        except jsonschema.exceptions.ValidationError as err:
            helper.throw_error(f'The downloaded {json_path} does not follow {os.path.basename(schema_path)}: {err.message}')
