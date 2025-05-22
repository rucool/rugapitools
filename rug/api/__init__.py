import logging
import requests
import pandas as pd
import numpy as np
from shapely.geometry import Polygon
from geopandas import GeoDataFrame
from rug.api.urls import end_points

logging.getLogger(__file__)


def get_deployments_by_name(deployment_names: list):
    """
    Fetch one or more metadata records for the specified deployment name(s)
    :param deployment_names: list of registered deployment names
    :return: DataFrame containing deployment metadata records
    """

    deployments = pd.DataFrame()

    base_url = end_points['DEPLOYMENTS'].url
    results = {'data': [],
               'count': 0}
    for deployment_name in deployment_names:
        deployment_url = '{:}?deployment={:}'.format(base_url, deployment_name)
        try:
            r = requests.get(deployment_url, timeout=10)
            if r.status_code != 200:
                logging.warning('Failed to fetch deployment {:} ({:})'.format(deployment_name, e))
                continue
            response = r.json()
            if response['count'] == 0:
                logging.warning('No deployment found for deployment_name {:}'.format(deployment_name))
                continue
            elif response['count'] > 1:
                logging.warning('Multiple deployments found for deployment name {:}'.format(deployment_name))
                continue
            results['data'].append(response['data'][0])
            results['count'] += 1
        except (requests.exceptions.RequestException, ValueError) as e:
            logging.error('{:}: {:}'.format(deployment_name, e))

    if results['count'] > 0:
        deployments = deployments_json_to_df(results)
    else:
        logging.warning('No deployments found for specified deployment name(s)')

    return deployments


def get_active_deployments():
    """
    Fetch all active deployments
    :return: data frame
    """

    deployments = pd.DataFrame()

    r = requests.get(end_points['ACTIVE_DEPLOYMENTS'].url, timeout=30)
    response = None
    if r.status_code == 200:
        response = r.json()
        deployments = deployments_json_to_df(response)

    return deployments


def get_all_deployments():
    """
    Fetch all registered deployments (active and recovered)
    :return: data frame
    """

    deployments = pd.DataFrame()

    r = requests.get(end_points['DEPLOYMENTS'].url, timeout=30)
    response = None
    if r.status_code == 200:
        response = r.json()
        deployments = deployments_json_to_df(response)

    return deployments


def df2geodf(deployments, crs='EPSG:4326'):
    """
    Convert a deployments API data frame to a GeoPandas data frame
    :param deployments: deployments API data frame
    :param crs: coordinate reference system of the GeoPandas geometries
    :return: GeoPandas data frame
    """
    geo_df = GeoDataFrame()
    bboxes = []
    for deployment_name, row in deployments.iterrows():

        track_url = '{:}/?deployment={:}'.format(end_points['TRACKS'].url, deployment_name)

        bbox = Polygon()

        try:
            r = requests.get(track_url, timeout=10)
            if r.status_code == 200:
                response = r.json()
                if not response['bbox']:
                    logging.debug('No track (bounding box) for for {:}'.format(deployment_name))
                else:
                    # Create the shapely.Polygon
                    # polygon = [nw, ne, se, sw, nw]
                    bbox = Polygon(((response['bbox'][3], response['bbox'][0]),
                                    (response['bbox'][3], response['bbox'][2]),
                                    (response['bbox'][1], response['bbox'][2]),
                                    (response['bbox'][1], response['bbox'][0]),
                                    (response['bbox'][3], response['bbox'][0])))
        except Exception as e:
            logging.error('{:}: {:}'.format(deployment_name, e))

        bboxes.append(bbox)

    geo_df = GeoDataFrame(deployments, geometry=bboxes, crs=crs)

    return geo_df


def deployments_json_to_df(response_json):
    """
    Convert an deployments API response to a pandas data frame
    :param response_json: deployments API response
    :return: data frame
    """
    deployments = []
    for response_item in response_json['data']:

        if 'last_surfacing' in response_item:
            srf = response_item.pop('last_surfacing')

            response_item.update(srf)

        deployments.append(response_item)

    deployments_df = pd.DataFrame(deployments)

    # Convert None in end_date_epoch to NaN
#    deployments_df.end_date_epoch.fillna(pd.NaT, inplace=True)
    deployments_df['end_date_epoch'] = deployments_df.end_date_epoch.fillna(pd.NaT)

    # Convert start_date_epoch and end_date_epoch to datetimes
    deployments_df['start_date'] = pd.to_datetime(deployments_df.start_date_epoch, unit='s')
    deployments_df['end_date'] = pd.to_datetime(deployments_df.end_date_epoch, unit='s')

    # update column names
    deployments_df['glider'] = deployments_df.glider_name

    # Drop columns
    drop_columns = ['glider_name']

    return deployments_df.drop(columns=drop_columns).set_index('deployment_name')
