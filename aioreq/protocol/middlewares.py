import logging
from abc import ABC, abstractmethod
from typing import Iterable, Union

from .headers import TransferEncoding, ContentEncoding, AuthenticationWWW
from .encodings import get_avaliable_encodings
from ..settings import LOGGER_NAME
from .auth import parse_auth_header

log = logging.getLogger(LOGGER_NAME)

default_middlewares = [
    'RetryMiddleWare',
    'RedirectMiddleWare',
    'DecodeMiddleWare',
    'AuthenticationMiddleWare',
]


class MiddleWare(ABC):

    def __init__(self, next_middleware):
        self.next_middleware = next_middleware

    @abstractmethod
    async def process(self, request, client):
        ...

    @staticmethod
    def build(middlewares_: Iterable[Union[str, type]]):
        result = RequestMiddleWare(next_middleware=None)
        for middleware in reversed(middlewares_):
            if isinstance(middleware, str):
                middleware = globals()[middleware]
            result = middleware(next_middleware=result)
        return result


class RequestMiddleWare(MiddleWare):

    async def process(self, request, client):
        resp = await client.send_request_directly(request)
        return resp


class RedirectMiddleWare(MiddleWare):
    redirect_count = 3

    def __init__(self, *args, **kwargs):
        redirect = kwargs.get('redirect', None)
        if not redirect:
            redirect = self.redirect_count
        self.redirect = max(redirect + 1, 1)
        super().__init__(*args, **kwargs)

    async def process(self, request, client):
        redirect = self.redirect
        response = None
        while redirect != 0:
            redirect -= 1
            response = await self.next_middleware.process(request, client)
            if (response.status // 100) == 3:
                request.host = response.headers['Location']

                if redirect < 1:
                    return response
            else:
                return response
            log.info(f'Redirecting request with status code {response.status}')
        assert response is not None

        return response


class DecodeMiddleWare(MiddleWare):

    def decode(self, response):
        for parser, header in (
                (TransferEncoding, 'transfer-encoding'),
                (ContentEncoding, 'content-encoding')
        ):
            header_content = response.headers.get(header, None)
            if header_content:
                encodings = parser.parse(header_content)

                for encoding in encodings:
                    response.content = encoding.decompress(response.content)

    async def process(self, request, client):

        if 'content-encoding' not in request.headers:
            request.headers.add_header(get_avaliable_encodings())

        response = await self.next_middleware.process(request, client)
        self.decode(response)
        return response


class RetryMiddleWare(MiddleWare):
    retry_count = 3

    def __init__(self, *args, **kwargs):
        self.retry_count = max(self.retry_count + 1, 1)
        super().__init__(*args, **kwargs)

    async def process(self, request, client):
        retry_count = self.retry_count
        response = None
        while retry_count != -1:
            retry_count -= 1
            try:
                response = await self.next_middleware.process(request, client)
                break
            except Exception as e:
                log.info(f"Retrying cause of error : {e}")
                if retry_count == -1:
                    raise e
        return response


class AuthenticationMiddleWare(MiddleWare):

    async def process(self, request, client):

        resp = await self.next_middleware.process(request, client)
        if resp.status != 401:
            return resp
        if 'www-authenticate' not in resp.headers:
            raise ValueError('401 status code received without `www-authenticate` header')
        header_obj = AuthenticationWWW.parse(resp.headers['www-authenticate'])
        for authentication_header in parse_auth_header(header_obj, request):
            request.headers['authorization'] = authentication_header
            resp = await self.next_middleware.process(request, client)
            if resp.status != 401:
                break
        return resp
