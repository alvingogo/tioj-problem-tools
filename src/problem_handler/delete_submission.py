import re

from bs4 import BeautifulSoup

import src.helper as helper

# Read the username of the account a submission came from off the submission's own page. Return
# an empty string when the page names no account we can compare against, which is what a
# submission made inside a contest looks like.
def get_submitter(submission_id, tioj, settings):
    page = tioj.get(settings.endpoints.submission % submission_id)
    soup = BeautifulSoup(page.text, 'html.parser')
    label = soup.find(string=re.compile(r'^\s*%s' % re.escape(settings.tioj_instance.submission_page.submitter_label)))
    if label is None:
        return ''
    # Look no further than the label that comes after the submitter's, so that a page naming the
    # submitter without linking to an account is read as naming nobody rather than as naming
    # whoever the next link on the page happens to point at.
    for element in label.find_all_next():
        if element.name == 'strong':
            break
        if element.name == 'a' and element.get('href'):
            match = re.match(settings.tioj_instance.submission_page.user_path_regex, element['href'])
            if match:
                return match.group(1)
    return ''

'''
Requirement: Admin permission.

Description: Delete a submission from TIOJ. Unless check_submitter is turned off, the submission
             is left alone when it was made by an account other than the one logged in. The
             confirm callback, if given, is asked one last time right before the deletion, and is
             handed the submitter so that it can say whose submission is about to go.

Return value: True if the submission was deleted, False if it was left alone.
'''
def delete_submission(submission_id, tioj, settings, check_submitter=True, confirm=None):
    submitter = get_submitter(submission_id, tioj, settings)

    if check_submitter:
        me = tioj.whoami()
        if not submitter:
            helper.throw_warning(f'Cannot tell who made submission {submission_id}, leaving it alone. Pass --no-check-submitter to delete it anyway.')
            return False
        if submitter != me:
            helper.throw_warning(f'Submission {submission_id} was made by [bold]{submitter}[/bold], not by you ([bold]{me}[/bold]), leaving it alone. Pass --no-check-submitter to delete it anyway.')
            return False

    if confirm is not None and not confirm(submitter):
        return False

    helper.throw_status(f'Deleting TIOJ submission {submission_id}...')

    endpoint = settings.endpoints.submission % submission_id
    tioj.delete(endpoint, endpoint)

    helper.throw_info(f'Completed delete TIOJ submission {submission_id}.')
    return True
