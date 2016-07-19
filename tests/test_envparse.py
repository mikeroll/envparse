# -*- coding: utf-8 -*-
import pytest

import envparse
from envparse import Env, ConfigurationError, urlparse


env_vars = dict(
    BLANK='',
    STR='foo',
    INT='42',
    FLOAT='33.3',
    BOOL_TRUE='1',
    BOOL_FALSE='0',
    PROXIED='{{STR}}',
    LIST_STR='foo,bar',
    LIST_STR_WITH_SPACES=' foo,  bar',
    LIST_INT='1,2,3',
    LIST_INT_WITH_SPACES=' 1,  2,3',
    DICT_STR='key1=val1, key2=val2',
    DICT_INT='key1=1, key2=2',
    JSON='{"foo": "bar", "baz": [1, 2, 3]}',
    URL='https://example.com/path?query=1',
    REDIS_URL='redis://:redispass@127.0.0.1:6379/0'
)


@pytest.fixture(autouse=True, params=['schema', 'schemaless'])
def proto_env(request):
    """Create a schema or a schemaless Env object."""
    if request.param == 'schema':
        return Env(STR=str, STR_DEFAULT=dict(cast=str, default='default'),
                   INT=int, LIST_STR=list,
                   LIST_INT=dict(cast=list, subcast=int))
    elif request.param == 'schemaless':
        return envparse.env


@pytest.fixture(autouse=True, params=['os_environ', 'envdict', 'envfile'])
def env(monkeypatch, proto_env, request):
    """Populate the Env object with data from os.environ, a dict, or a file"""
    if request.param == 'os_environ':
        # use `env` with `os.environ` - the default
        for key, val in env_vars.items():
            monkeypatch.setenv(key, val)
        return proto_env
    elif request.param == 'envdict':
        # use the provided dict directly
        return proto_env.from_env(env_vars)
    elif request.param == 'envfile':
        return proto_env.from_envfile('tests/envfile')


# Helper function
def assert_type_value(cast, expected, result):
    assert cast == type(result)
    assert expected == result


def test_var_not_present(env):
    with pytest.raises(ConfigurationError):
        env('NOT_PRESENT')


def test_var_not_present_with_default(env):
    default_val = 'default val'
    assert default_val, env('NOT_PRESENT', default=default_val)


def test_default_none(env):
    assert_type_value(type(None), None, env('NOT_PRESENT', default=None))


def test_implicit_nonbuiltin_type(env):
    with pytest.raises(AttributeError):
        env.foo('FOO')


def test_str(env):
    expected = str(env_vars['STR'])
    assert_type_value(str, expected, env('STR'))
    assert_type_value(str, expected, env.str('STR'))


def test_int(env):
    expected = int(env_vars['INT'])
    assert_type_value(int, expected, env('INT', cast=int))
    assert_type_value(int, expected, env.int('INT'))


def test_float(env):
    expected = float(env_vars['FLOAT'])
    assert_type_value(float, expected, env.float('FLOAT'))


def test_bool(env):
    assert_type_value(bool, True, env.bool('BOOL_TRUE'))
    assert_type_value(bool, False, env.bool('BOOL_FALSE'))


def test_list(env):
    list_str = ['foo', 'bar']
    assert_type_value(list, list_str, env('LIST_STR', cast=list))
    assert_type_value(list, list_str, env.list('LIST_STR'))
    assert_type_value(list, list_str, env.list('LIST_STR_WITH_SPACES'))
    list_int = [1, 2, 3]
    assert_type_value(list, list_int, env('LIST_INT', cast=list,
                      subcast=int))
    assert_type_value(list, list_int, env.list('LIST_INT', subcast=int))
    assert_type_value(list, list_int, env.list('LIST_INT_WITH_SPACES',
                      subcast=int))
    assert_type_value(list, [], env.list('BLANK', subcast=int))


def test_dict(env):
    dict_str = dict(key1='val1', key2='val2')
    assert_type_value(dict, dict_str, env.dict('DICT_STR'))
    assert_type_value(dict, dict_str, env('DICT_STR', cast=dict))
    dict_int = dict(key1=1, key2=2)
    assert_type_value(dict, dict_int, env('DICT_INT', cast=dict,
                      subcast=int))
    assert_type_value(dict, dict_int, env.dict('DICT_INT', subcast=int))
    assert_type_value(dict, {}, env.dict('BLANK'))


def test_json(env):
    expected = {'foo': 'bar', 'baz': [1, 2, 3]}
    assert_type_value(dict, expected, env.json('JSON'))


def test_url(env):
    url = urlparse.urlparse('https://example.com/path?query=1')
    assert_type_value(url.__class__, url, env.url('URL'))


def test_proxied_value(env):
    assert_type_value(str, 'foo', env('PROXIED'))


def test_preprocessor(env):
    assert_type_value(str, 'FOO', env('STR', preprocessor=lambda
                                      v: v.upper()))


def test_postprocessor(env):
    """
    Test a postprocessor which turns a redis url into a Django compatible
    cache url.
    """
    expected = {'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': '127.0.0.1:6379:0',
                'OPTIONS': {'PASSWORD': 'redispass'}}

    def django_redis(url):
        return {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': '{}:{}:{}'.format(url.hostname, url.port,
                                          url.path.strip('/')),
            'OPTIONS': {'PASSWORD': url.password}}

    assert_type_value(dict, expected, env.url('REDIS_URL',
                      postprocessor=django_redis))
