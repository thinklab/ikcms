import logging

from . import exc
from . import messages

logger = logging.getLogger(__name__)


class AppBase:
    def __init__(self, cfg):
        """ Called before started ws server """
        self.cfg = cfg

    async def __call__(self, server, client_id):
        """ Called when recived message """
        raise NotImplementedError


class App(AppBase):

    messages = messages

    def __init__(self, cfg):
        super().__init__(cfg)
        self.client_envs = {}
        self.cfg.config_uid()
        self.cfg.config_logging()
        self.env_class = self.get_env_class()
        self.handlers = self.get_handlers()

    def get_handlers(self):
        return {}

    def get_env_class(self):
        from .env import Environment
        return Environment

    @property
    def clients(self):
        return self.client_envs.values()

    async def __call__(self, server, client_id):
        self.add_client(server, client_id)
        try:
            while True:
                try:
                    raw_message = await server.recv(client_id)
                    request = self.messages.from_json(raw_message)
                    handler = self.handlers.get(request['handler'])
                    if not handler:
                        raise exc.HandlerNotAllowed(request['handler'])
                    result = await handler(env, request['body'])
                    response = self.messages.Response.from_request(
                        request, body=result)
                except exc.BaseError as e:
                    logger.debug(str(e))
                    response = self.error_response(e, locals())
                await server.send(client_id, response.to_json())
        finally:
            self.remove_client(client_id)

    def add_client(self, server, client_id):
        env = self.env_class(self, server, client_id)
        self.client_envs[client_id] = env

    def remove_client(self, client_id):
        await self.client_envs[client_id].close()
        del self.client_envs[client_id]

    def error_response(self, e, locals):
        request = locals.get('request')
        return self.messages.Error(
            error=e.error,
            message=str(e),
            request_id=request['request_id'],
            handler=request['handler'],
        )


