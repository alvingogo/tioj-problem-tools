import os

from bs4 import BeautifulSoup

import src.helper as helper

'''
Requirement: Logged in.

Description: Read the compilers a TIOJ problem accepts off its submission form. TIOJ keeps a
             compiler's id in a database row, so it differs between instances and cannot be
             hardcoded, while the name is unique and stable. The name is the part of the
             description TIOJ shows before the first '/', for example the description
             "c++17/gnu c++ compiler 11.2.0 | options: -O2 -std=c++17" belongs to "c++17".

             Reading the form also means the compilers a problem bans are left out, since TIOJ
             does not offer them there in the first place.

Return value: A list of (name, description, id), in the order TIOJ lists them.
'''
def get_compilers(problem_id, tioj, settings):
    page = tioj.get(settings.endpoints.submit_problem % problem_id)
    soup = BeautifulSoup(page.text, 'html.parser')

    select = soup.find('select', {'name': settings.tioj_instance.submission_compiler_id})
    if select is None:
        helper.throw_error(f'Cannot find the field {settings.tioj_instance.submission_compiler_id} on the submission form of TIOJ problem {problem_id}.')

    compilers = []
    for option in select.find_all('option'):
        value = option.get('value')
        if value is None:
            continue
        description = option.text.strip()
        name = description.split('/')[0].strip()
        compilers.append((name if name else description, description, value))

    if not compilers:
        helper.throw_error(f'TIOJ problem {problem_id} offers no compiler to submit with.')

    return compilers

'''
Requirement: None.

Description: Work out which of the compilers of a problem to submit with. A name given on the
             command line wins, looked up as it is written and then through
             tioj_instance.compiler_alias, and the file's extension decides when there is none.
             Nothing is guessed beyond that: submitting with the wrong compiler only shows up
             as a compilation error much later, so an unknown name is an error rather than a
             fallback to some default.

Return value: The tuple (name, id).
'''
def resolve_compiler(compiler, path, compilers, settings):
    available = ', '.join(name for name, _, _ in compilers)

    if compiler is None:
        extension = os.path.splitext(path)[1].lstrip('.').lower()
        if not extension:
            helper.throw_error(f'{path} has no extension to take a compiler from, name one with --compiler. Available: {available}.')
        table = settings.tioj_instance.compiler_extension.to_dict()
        wanted = table.get(extension.lower())
        if wanted is None:
            helper.throw_error(f'No compiler is configured for the extension ".{extension}" in tioj_instance_settings.toml/tioj_instance.compiler_extension, name one with --compiler. Available: {available}.')
        origin = f'the extension ".{extension}"'
    else:
        wanted = settings.tioj_instance.compiler_alias.to_dict().get(compiler.lower(), compiler)
        origin = f'--compiler {compiler}'

    for name, description, id in compilers:
        if wanted.lower() in (name.lower(), description.lower()):
            return name, id

    helper.throw_error(f'{origin} asks for the compiler "{wanted}", which TIOJ does not offer here. Available: {available}.')

'''
Requirement: Logged in.

Description: Submit local program to problem "probem_id".

Return value: None.
'''
def submit_submission(problem_id, path, compiler, replace, tioj, settings):
    if not problem_id.isdigit():
        helper.throw_error('problem_id must be digits')
    problem_id = str(int(problem_id))

    if not os.path.isfile(path):
        helper.throw_error(f'Cannot find the program source {path}.')

    name, compiler_id = resolve_compiler(compiler, path, get_compilers(problem_id, tioj, settings), settings)

    helper.throw_status(f"Submit to TIOJ problem {problem_id} from {path} (compiler: {name})...")

    code = helper.read_file(path)
    for pattern, string in replace:
        code = code.replace(pattern, string) 

    data = {
        settings.tioj_instance.submission_compiler_id: str(compiler_id),
        settings.tioj_instance.submission_code: code,
        settings.tioj_instance.submission_file: ('', None, 'application/octet-stream')
    }

    response = tioj.submit_form(settings.endpoints.submit_problem % problem_id, data=data, multipart=True)

    helper.throw_info(f"Completed submit the {path} to TIOJ problem {problem_id}.")
