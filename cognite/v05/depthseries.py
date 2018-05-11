# -*- coding: utf-8 -*-
"""Depthseries Module

This module mirrors the Timeseries API, but handles pairs of timeseries to emulate depth(or other indexed) data series. It allows you to fetch data from the api and output it in various formats.

https://doc.cognitedata.com/0.5/#Cognite-API-Time-series
"""

import sys

from typing import List
import copy
import itertools

import cognite._utils as _utils
import cognite.config as config

from cognite.v05 import timeseries
from cognite.v05.dto import  LatestDatapointResponse, \
    DatapointDepthDTO, \
    TimeSeriesDTO, TimeseriesResponse, DatapointDTO





def post_datapoints(depthseries, depthdatapoints: List[DatapointDepthDTO], **kwargs):
    '''Insert a list of datapoints.

    Args:
        timeseries (str):       Name of timeseries to insert to.

        datapoints (list[v05.data_objects.DatapointDTO): List of datapoint data transfer objects to insert.

        offset(int): Offset of index. -1 means append to existsing series, 0 means start at first index
    Keyword Args:
        api_key (str): Your api-key.

        project (str): Project name.

    Returns:
        An empty response.
    '''
    depthseries = depthseries.replace('/', '%2F')
    msIncrement=1000
    api_key, project = config.get_config_variables(kwargs.get('api_key'), kwargs.get('project'))
    try:
        res = timeseries.get_latest(depthseries)
        offset = res.to_json()['timestamp']+msIncrement
    except:
        offset = 0 #Random timestamp to start the time series

    url = config.get_base_url(api_version=0.5) + '/projects/{}/timeseries/data/{}'.format(project, depthseries)
    urldepth = config.get_base_url(api_version=0.5) + '/projects/{}/timeseries/data/{}'.format(project, _generateIndexName(depthseries))

    headers = {
        'api-key': api_key,
        'content-type': 'application/json',
        'accept': 'application/json'
    }
    datapoints=[]
    depthpoints=[]
    for datapoint in depthdatapoints:
        datapoints.append(DatapointDTO(offset,datapoint.value))
        depthpoints.append(DatapointDTO(offset,datapoint.depth))
        offset += msIncrement

    ul_dps_limit = 100000
    i = 0
    while i < len(datapoints):
        body = {'items': [dp.__dict__ for dp in datapoints[i:i + ul_dps_limit]]}
        _utils.post_request(url, body=body, headers=headers)
        body = {'items': [dp.__dict__ for dp in depthpoints[i:i + ul_dps_limit]]}
        res = _utils.post_request(urldepth, body=body, headers=headers)
        i += ul_dps_limit

    return res.json()


def get_latest(depthseries, **kwargs):
    '''Returns a LatestDatapointObject containing the latest datapoint for the given timeseries.

    Args:
        timeseries (str):       The name of the timeseries to retrieve data for.

    Keyword Arguments:
        api_key (str):          Your api-key.

        project (str):          Project name.

    Returns:
        v05.data_objects.LatestDatapointsResponse: A data object containing the requested data with several getter methods with different
        output formats.
    '''
    api_key, project = config.get_config_variables(kwargs.get('api_key'), kwargs.get('project'))
    timeseries = timeseries.replace('/', '%2F')
    url = config.get_base_url(api_version=0.5) + '/projects/{}/timeseries/latest/{}'.format(project, timeseries)
    headers = {
        'api-key': api_key,
        'accept': 'application/json'
    }
    res = _utils.get_request(url, headers=headers, cookies=config.get_cookies())
    return LatestDatapointResponse(res.json())





def get_depthseries(prefix=None, description=None, include_metadata=False, asset_id=None, path=None, **kwargs):
    '''Returns a TimeseriesObject containing the requested timeseries.

    Args:
        prefix (str):           List timeseries with this prefix in the name.

        description (str):      Filter timeseries taht contains this string in its description.

        include_metadata (bool):    Decide if the metadata field should be returned or not. Defaults to False.

        asset_id (int):        Get timeseries related to this asset.

        path (str):             Get timeseries under this asset path branch.

    Keyword Arguments:
        limit (int):            Number of results to return.

        api_key (str):          Your api-key.

        project (str):          Project name.

        autopaging (bool):      Whether or not to automatically page through results. If set to true, limit will be
                                disregarded. Defaults to False.

    Returns:
        v05.data_objects.TimeseriesResponse: A data object containing the requested timeseries with several getter methods with different
        output formats.
    '''
    api_key, project = config.get_config_variables(kwargs.get('api_key'), kwargs.get('project'))
    url = config.get_base_url(api_version=0.5) + '/projects/{}/timeseries'.format(project)
    headers = {
        'api-key': api_key,
        'accept': 'application/json'
    }
    params = {
        'q': prefix,
        'description': description,
        'includeMetadata': include_metadata,
        'assetId': asset_id,
        'path': path,
        'limit': kwargs.get('limit', 10000) if not kwargs.get('autopaging') else 10000
    }

    timeseries = []
    res = _utils.get_request(url=url, headers=headers, params=params, cookies=config.get_cookies())
    timeseries.extend([ts for ts in res.json()['data']['items'] if not ts.name.endswith(_generateIndexName(""))])
    next_cursor = res.json()['data'].get('nextCursor')

    while next_cursor and kwargs.get('autopaging'):
        params['cursor'] = next_cursor
        res = _utils.get_request(url=url, headers=headers, params=params, cookies=config.get_cookies())
        timeseries.extend([ts for ts in res.json()['data']['items'] if not ts.name.endswith(_generateIndexName(""))])
        next_cursor = res.json()['data'].get('nextCursor')

    return TimeseriesResponse(
        {'data': {'nextCursor': next_cursor, 'previousCursor': res.json()['data'].get('previousCursor'),
                  'items': timeseries}})

def _generateIndexName(depthSeriesName):
    return depthSeriesName+"_DepthIndex"

def post_depth_series(depth_series: List[TimeSeriesDTO], **kwargs):
    '''Create a new depth series.

    Args:
        depthseries (list[v05.data_objects.TimeSeriesDTO]):   List of time series data transfer objects to create.
        Corresponding depth series used for indexing will be created automatically, with unit of m(meter)

    Keyword Args:
        api_key (str): Your api-key.

        project (str): Project name.
    Returns:
        An empty response.
    '''

    api_key, project = config.get_config_variables(kwargs.get('api_key'), kwargs.get('project'))
    url = config.get_base_url(api_version=0.5) + '/projects/{}/timeseries'.format(project)
    depth_indexes=copy.deepcopy(depth_series)
    for ts in depth_indexes:
        ts.name=_generateIndexName(ts.name)
        ts.unit="m"
        ts.isString=False

    body = {
        'items': [ts.__dict__ for ts in itertools.chain(depth_series,depth_indexes)]
    }

    headers = {
        'api-key': api_key,
        'content-type': 'application/json',
        'accept': 'application/json'
    }

    res = _utils.post_request(url, body=body, headers=headers)
    return res.json()


def update_depth_series(depth_series: List[TimeSeriesDTO], **kwargs):
    '''Update an existing time series.

    For each field that can be updated, a null value indicates that nothing should be done.

    Args:
        timeseries (list[v05.data_objects.TimeSeriesDTO]):   List of time series data transfer objects to update.

    Keyword Args:
        api_key (str): Your api-key.

        project (str): Project name.

    Returns:
        An empty response.
    '''

    api_key, project = config.get_config_variables(kwargs.get('api_key'), kwargs.get('project'))
    url = config.get_base_url(api_version=0.5) + '/projects/{}/timeseries'.format(project)

    body = {
        'items': [ts.__dict__ for ts in depth_series]
    }

    headers = {
        'api-key': api_key,
        'content-type': 'application/json',
        'accept': 'application/json'
    }

    res = _utils.put_request(url, body=body, headers=headers)
    if res.json() == {}:
        for dsdto in depth_series:
            dsdto.name=_generateIndexName(dsdto.name)
            dsdto.isString = None
            dsdto.unit = None
        body = {
            'items': [ts.__dict__ for ts in depth_series]
        }
        res = _utils.put_request(url, body=body, headers=headers)
    return res.json()


def delete_depth_series(depthseries, **kwargs):
    '''Delete a depthseries.

    Args:
        depthseries (str):   Name of depthseries to delete.

    Keyword Args:
        api_key (str): Your api-key.

        project (str): Project name.

    Returns:
        An empty response.
    '''
    api_key, project = config.get_config_variables(kwargs.get('api_key'), kwargs.get('project'))
    url = config.get_base_url(api_version=0.5) + '/projects/{}/timeseries/{}'.format(project, depthseries)

    headers = {
        'api-key': api_key,
        'accept': 'application/json'
    }

    res = _utils.delete_request(url, headers=headers)
    if res == {}:
        url = config.get_base_url(api_version=0.5) + '/projects/{}/timeseries/{}'.format(project, _generateIndexName(depthseries))
        res = _utils.delete_request(url, headers=headers)

    return res.json()

def reset_depth_series(depthseries, **kwargs):
    '''Delete all datapoints for a depthseries.

       Args:
           depthseries (str):   Name of depthseries to delete.

       Keyword Args:
           api_key (str): Your api-key.

           project (str): Project name.

       Returns:
           An empty response.
       '''
    api_key, project = config.get_config_variables(kwargs.get('api_key'), kwargs.get('project'))
    url = config.get_base_url(
        api_version=0.5) + '/projects/{}/timeseries/{}?timestampInclusiveBegin=0?timestampInclusiveEnd={}'.format(
        project, depthseries, sys.maxsize)

    headers = {
        'api-key': api_key,
        'accept': 'application/json'
    }
    res = _utils.delete_request(url, headers=headers)
    if res == {}:
        url = config.get_base_url(
            api_version=0.5) + '/projects/{}/timeseries/{}?timestampInclusiveBegin=0?timestampInclusiveEnd={}'.format(
            project, _generateIndexName(depthseries), sys.maxsize)
        res = _utils.delete_request(url, headers=headers)

    return res.json()

