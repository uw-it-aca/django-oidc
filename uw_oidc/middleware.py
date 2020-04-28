import logging
from django.contrib import auth
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from uw_oidc.exceptions import InvalidTokenError
from uw_oidc.id_token import UWIdPToken
from uw_oidc.logger import log_err, log_info

logger = logging.getLogger(__name__)


class IDTokenAuthenticationMiddleware(MiddlewareMixin):
    """
    Supports ID Token (issued by UW OIDC provider)
    based request authentication for specified clients.
    """
    TOKEN_SESSION_KEY = 'uw_oidc_idtoken'

    def __init__(self, get_response=None):
        self.get_response = get_response

    def process_request(self, request):
        if not hasattr(request, 'session'):
            raise ImproperlyConfigured(
                'This authentication middleware requires session middleware '
                'to be installed. Edit your MIDDLEWARE setting to insert '
                '"django.contrib.sessions.middleware.SessionMiddleware" '
                'before "uw_oidc.middleware.IDTokenAuthenticationMiddleware".')

    def process_view(self, request, view_func, view_args, view_kwargs):
        if 'HTTP_AUTHORIZATION' in request.META:
            try:
                if request.user.is_authenticated:
                    # honor the existing session
                    return None

                # We are seeing this user for the first time in this
                # session, attempt to authenticate the user.
                token = request.META['HTTP_AUTHORIZATION'].replace(
                    'Bearer ', '', 1)
                username = self.clean_username(
                    UWIdPToken().username_from_token(token))

                user = auth.authenticate(request, remote_user=username)
                if user:
                    # User is valid.  Set request.user and persist user
                    # in the session by logging the user in.
                    auth.login(request, user)
                    request.session[self.TOKEN_SESSION_KEY] = token
                    log_info(logger, {'msg': "Login token based session",
                                      'user': username,
                                      'url': request.META.get('REQUEST_URI')})
            except InvalidTokenError as ex:
                return HttpResponse(status=401, reason=str(ex))
        return None

    def clean_username(self, username):
        if username is None or not len(username):
            raise InvalidTokenError('Missing username')

        try:
            (username, domain) = username.split('@', 1)
        except ValueError:
            pass

        return username
