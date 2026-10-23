import src.helper as helper
import src.profile as profile
from src.config import settings
from src.tioj_interactor import TIOJ_Session

'''
Requirement: None.

Description: Open a logged in TIOJ session for the profile this run should use, which is the
             one --profile named or otherwise the current one. Every command that talks to TIOJ
             goes through here, so that resolving the credentials stays in one place and no
             command has to take a profile argument of its own.

Return value: A logged in TIOJ_Session. Prints an error and terminates when admin permission is
              required but the account does not have it.
'''
def open_session(require_admin=False):
    alias, tioj_url, tioj_username = profile.resolve()

    where = f'profile [bold]{alias}[/bold]' if alias is not None else 'default_settings.toml'
    helper.throw_status(f'Using {where}: {tioj_username} at {tioj_url}')

    tioj = TIOJ_Session(tioj_url, settings.endpoints.login)
    tioj.login(tioj_username, profile.get_password(alias))

    if require_admin and not tioj.isadmin():
        helper.throw_error(f'The user [bold]{tioj.whoami()}[/bold] doesn\'t have admin permission!')

    return tioj
