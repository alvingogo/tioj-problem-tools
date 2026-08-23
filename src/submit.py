import os
import time

from bs4 import BeautifulSoup

import src.helper as helper

# How long to leave between two looks at a submission's page while --wait waits for its
# verdict, in seconds.
POLL_INTERVAL = 2

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

Description: Read the verdict of a submission off its own page. While TIOJ is still judging it
             shows a waiting icon there, which is how it marks the verdicts that are not final
             ("queued", "received" and "Validating"), so the icon being gone is what tells a
             finished submission from one that merely reads as waiting.

Return value: The tuple (verdict, score, waiting).
'''
def get_verdict(submission_id, tioj, settings):
    page = tioj.get(settings.endpoints.submission % submission_id)
    soup = BeautifulSoup(page.text, 'html.parser')

    verdict = soup.find(id=settings.tioj_instance.submission_page.verdict)
    if verdict is None:
        helper.throw_error(f'Cannot find the element #{settings.tioj_instance.submission_page.verdict} on the page of submission {submission_id}.')

    score = soup.find(id=settings.tioj_instance.submission_page.score)
    waiting = soup.find(id=settings.tioj_instance.submission_page.waiting) is not None

    return verdict.text.strip(), score.text.strip() if score is not None else '', waiting

'''
Requirement: Logged in.

Description: Wait for a submission to be judged, reporting the verdict whenever it changes so
             that a long wait still says what it is waiting on. A timeout of zero waits for as
             long as it takes.

Return value: The tuple (verdict, score).
'''
def wait_for_verdict(submission_id, tioj, settings, timeout):
    deadline = time.monotonic() + timeout if timeout > 0 else None
    reported = None

    while True:
        verdict, score, waiting = get_verdict(submission_id, tioj, settings)

        if not waiting:
            return verdict, score

        if verdict != reported:
            helper.throw_status(f'Submission {submission_id}: {verdict}...')
            reported = verdict

        if deadline is not None and time.monotonic() + POLL_INTERVAL > deadline:
            helper.throw_error(f'Submission {submission_id} is still "{verdict}" after {timeout} seconds, giving up waiting for it.')

        time.sleep(POLL_INTERVAL)

'''
Requirement: Logged in.

Description: Submit local program to problem "probem_id".

Return value: None.
'''
def submit_submission(problem_id, path, compiler, replace, tioj, settings, wait=False, wait_timeout=0):
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

    # A submission TIOJ refuses is answered with the form again rather than with an error
    # status, so the status code says nothing. What does say something is where we ended up:
    # an accepted submission redirects to its own page, whose last path segment is its id.
    submission_id = response.url.rstrip('/').split('/')[-1]
    if not submission_id.isdigit():
        helper.throw_error(f'TIOJ did not accept the submission and answered with {response.url}.')

    helper.throw_info(f"Completed submit the {path} to TIOJ problem {problem_id}: {response.url}")

    if wait:
        verdict, score = wait_for_verdict(submission_id, tioj, settings, wait_timeout)
        helper.throw_info(f'Submission {submission_id}: [bold]{verdict}[/bold]' + (f' ({score})' if score else ''))
