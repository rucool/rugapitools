import logging
from shapely import Polygon
import pandas as pd
from rug.api.urls import end_points
import requests
from decimal import *

logging.getLogger(__file__)


def locate_datasets(datasets, north=90., south=-90, east=180., west=-180):
    """
    Find all data sets in the geopandas data frame that are in the specified bounding box
    :param datasets: geopandas data frame containing a geometry columm
    :param north: northernmost latitude
    :param south: southernmost latitude
    :param east: easternmost longitude
    :param west: westernmost longitude
    :return: geopandas data frame containing the found data sets
    """

    if not isinstance(datasets, pd.DataFrame):
        logging.error('datasets arg must be a geopandas data frame')
        return

    if 'geometry' not in datasets:
        logging.error('datasets arg must be a geopandas data frame with a geometry column')
        return

    bounding_box = Polygon(((north, west),
                            (north, east),
                            (south, east),
                            (south, west),
                            (north, west)))
    logging.debug('Finding deployments inside bounding box: {:}'.format(bounding_box.wkt))

    # Find the data sets that are within the specified bounding box
    datasets = datasets[datasets.intersects(bounding_box)]

    return datasets


def fetch_track_to_df(deployment_name: str):
    """
    Fetch the geojson track for the specified deployment name and convert to a pandas data frame
    :param deployment_name: deployment_name
    :return: data frame containing time,latitude,longitude GPS positions
    """

    track_df = pd.DataFrame()

    track_url = '{:}/?deployment={:}'.format(end_points['TRACKS'].url, deployment_name)

    try:
        r = requests.get(track_url, timeout=30)

        if r.status_code != 200:
            logging.error('Failed to fetch {:} track ({:})'.format(deployment_name, track_url))
            return track_df

        track_json = r.json()
        if not track_json:
            logging.warning('No track found for {:} ({:})'.format(deployment_name, track_url))
            return track_df

    except Exception as e:
        logging.error('{:}: {:}'.format(deployment_name, e))
        return track_df

    gps_fixes = [
        {'time': pd.to_datetime(f['properties']['gps_epoch'], unit='s'),
         'latitude': f['geometry']['coordinates'][1],
         'longitude': f['geometry']['coordinates'][0]}
        for f in track_json['features'] if
        f['geometry']['type'] == 'Point' and 'waypoint' not in f['properties']]

    if gps_fixes:
        track_df = pd.DataFrame(gps_fixes)

    return track_df


def latlon_to_geojson_track(latitudes, longitudes, timestamps, include_points=True, precision='0.001'):
    """
    Create a valid GeoJSON FeatureCollection set containing the track LineString and GPS fix Point features
    :param latitudes: pandas Series containing decimal degrees latitudes
    :param longitudes: pandas Series containing decimal degrees longitudes
    :param timestamps: pandas Series containing GPS fix datetime64[ns]
    :param include_points: True to include each GPS Point feature
    :param precision: GPS fix precision
    :return: GeoJSON FeatureCollection track object
    """

    geojson = {'type': 'FeatureCollection',
               'bbox': latlon_to_bbox(latitudes, longitudes, timestamps, precision=precision)}

    features = [latlon_to_linestring(latitudes, longitudes, timestamps, precision=precision)]

    if include_points:
        points = latlon_to_points(latitudes, longitudes, timestamps, precision=precision)
        features = features + points

    geojson['features'] = features

    return geojson


def latlon_to_linestring(latitudes, longitudes, timestamps, precision='0.001'):
    """
    Create a valid GeoJSON LineString Feature containing the GPS track
    :param latitudes: pandas Series containing decimal degrees latitudes
    :param longitudes: pandas Series containing decimal degrees longitudes
    :param timestamps: pandas Series containing GPS fix datetime64[ns]
    :param precision: GPS fix precision
    :return: GeoJSON LineString Feature object
    """
    dataset_gps = pd.DataFrame(index=timestamps)
    dataset_gps['latitude'] = latitudes.values
    dataset_gps['longitude'] = longitudes.values

    track = {'type': 'Feature',
             # 'bbox': bbox,
             'geometry': {'type': 'LineString',
                          'coordinates': [
                              [float(Decimal(pos.longitude).quantize(Decimal(precision),
                                                                     rounding=ROUND_HALF_DOWN)),
                               float(Decimal(pos.latitude).quantize(Decimal(precision),
                                                                    rounding=ROUND_HALF_DOWN))]
                              for i, pos in dataset_gps.iterrows()]},
             'properties': {}
             }

    return track


def latlon_to_points(latitudes, longitudes, timestamps, precision='0.001'):
    """
    Create valid GeoJSON Point Features containing the GPS fixes
    :param latitudes: pandas Series containing decimal degrees latitudes
    :param longitudes: pandas Series containing decimal degrees longitudes
    :param timestamps: pandas Series containing GPS fix datetime64[ns]
    :param precision: GPS fix precision
    :return: Array of GeoJSON Point Features
    """
    dataset_gps = pd.DataFrame(index=timestamps)
    dataset_gps['latitude'] = latitudes.values
    dataset_gps['longitude'] = longitudes.values

    return [{'type': 'Feature',
             'geometry': {'type': 'Point', 'coordinates':
                 [float(Decimal(pos.longitude).quantize(Decimal(precision),
                                                        rounding=ROUND_HALF_DOWN)),
                  float(Decimal(pos.latitude).quantize(Decimal(precision), rounding=ROUND_HALF_DOWN))]},
             'properties': {'ts': i.strftime('%Y-%m-%dT%H:%M:%SZ')}} for i, pos in dataset_gps.iterrows()]


def latlon_to_bbox(latitudes, longitudes, timestamps, precision='0.001'):
    """
    Create valid GeoJSON bounding box for the specified GPS fixes
    :param latitudes: pandas Series containing decimal degrees latitudes
    :param longitudes: pandas Series containing decimal degrees longitudes
    :param timestamps: pandas Series containing GPS fix datetime64[ns]
    :param precision: GPS fix precision
    :return: Bounding box
    """
    dataset_gps = pd.DataFrame(index=timestamps)
    dataset_gps['latitude'] = latitudes.values
    dataset_gps['longitude'] = longitudes.values

    return [float(Decimal(dataset_gps.longitude.min()).quantize(Decimal(precision), rounding=ROUND_HALF_DOWN)),
            float(Decimal(dataset_gps.latitude.min()).quantize(Decimal(precision), rounding=ROUND_HALF_DOWN)),
            float(Decimal(dataset_gps.longitude.max()).quantize(Decimal(precision), rounding=ROUND_HALF_DOWN)),
            float(Decimal(dataset_gps.latitude.max()).quantize(Decimal(precision), rounding=ROUND_HALF_DOWN))]


def average_daily_track_gps(track_df):
    """
    Average the track positions by day
    :param track_df: track data frome with columns time, latitude, longitude
    :return: daily average track data frame
    """

    track_df.set_index('time', inplace=True)

    return track_df.groupby(lambda x: x.date).agg({'latitude': 'mean', 'longitude': 'mean'}).reset_index().rename(
        columns={'index': 'time'})
