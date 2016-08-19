import os
import binascii
from iktomi.auth import check_password
from iktomi.auth import encrypt_password
import ikcms.ws_components.base
import ikcms.ws_apps.base.forms

from . import exc
from .forms import message_fields


def restrict(role=None):
    def wrap(handler):
        async def wrapper(self, env, message):
            if not env.user:
                raise exc.AccessDeniedError()
            return
        return wrapper
    return wrap


class AuthForm(ikcms.ws_apps.base.forms.MessageForm):
    fields = [
        message_fields.token,
        message_fields.login,
        message_fields.password,
    ]


class Component(ikcms.ws_components.base.Component):
    name = 'auth'
    requirements = ['db', 'cache']
    users_mapper = 'main.User'

    def env_init(self, env):
        env.user = None

    async def h_login(self, env, message):
        form = AuthForm()
        data = form.to_python(message)
        token = data.get('token', None)
        login = data.get('login', None)
        password = data.get('password', None)
        if token is not None:
            user, token = await self.auth_by_token(env.app, token)
        elif login is not None and password is not None:
            user, token = await self.auth_by_password(env.app, login, password)
        else:
            raise exc.InvalidCredentialsError()
        env.user = user
        return {
            'user': {
                'login': user['login'],
                'name': user['name'],
            },
            'token': token,
        }

    async def h_logout(self, env, message):
        if env.user is None:
            raise exc.AccessDeniedError()
        env.user = None

    async def get_user_by_login(self, app, login):
        Users = app.db.mappers.get_mapper(self.users_mapper)
        query = Users.query().filter_by(login=login)
        async with await app.db() as session:
            users = await query.select_items(session)
        return next(iter(users), None)

    async def get_user_by_token(self, app, token):
        login = await app.cache.get(token)
        if login is not None:
            return await self.get_user_by_login(app, login)
        return None

    async def auth_by_token(self, app, token):
        user = await self.get_user_by_token(app, token)
        if user is None:
            raise exc.InvalidTokenError()
        return user, token

    async def auth_by_password(self, app, login, password):
        user = await self.get_user_by_login(app, login)
        if user is None or not check_password(password, user['password']):
            raise exc.InvalidPasswordError()
        token = binascii.hexlify(os.urandom(10)).decode('ascii')
        await app.cache.set(token, login)
        return user, token


component = Component.create_cls
