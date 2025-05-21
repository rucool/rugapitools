#!/usr/bin/env python

import logging
import argparse
import sys
import os
import tabulate
import pandas as pd
import datetime
import json
from jinja2 import Template
from dateutil import parser
from rug.api import get_active_deployments, get_all_deployments, df2geodf
from rug.geo import locate_datasets, fetch_track_to_df, average_daily_track_gps, latlon_to_geojson_track


def main(args):
    """Create a kml file displaying Rutgers University Coastal Ocean Observation Lab glider tracks retrieved from the
    API. Tracks of active deployments are displayed by default."""

    log_level = getattr(logging, args.loglevel.upper())
    log_format = '%(asctime)s:%(module)s:%(levelname)s:%(message)s [line %(lineno)d]'
    logging.basicConfig(format=log_format, level=log_level)

    debug = args.debug
    glider = args.glider
    daily = args.daily
    start_date = args.start_date
    end_date = args.end_date
    north = args.north
    south = args.south
    east = args.east
    west = args.west
    active = args.active
    kml_template = args.template
    kml_name = args.kml_name
    project_name = args.project_name

    if not os.path.isfile(kml_template):
        logging.error('KML template not found: {:}'.format(kml_template))
        return 1
    try:
        with open(kml_template, 'r', encoding='latin-1') as fid:
            template = Template(fid.read())
    except Exception as e:
        logging.error('Error loading template {:} ({:})'.format(kml_template, e))
        return 1

    # Parse start_date if specified
    dt0 = None
    if start_date:
        try:
            dt0 = parser.parse(start_date)
        except ValueError as e:
            logging.error('Error parsing start date: {:}'.format(start_date))
            return 1
    dt1 = None
    # Parse end_date if specified
    if end_date:
        try:
            dt1 = parser.parse(end_date)
        except ValueError as e:
            logging.error('Error parsing end date: {:}'.format(end_date))
            return 1

    if active:
        logging.info('Selecting active deployments')
        deployments = get_active_deployments()
    else:
        logging.info('Selecting all deployments')
        deployments = get_all_deployments()

    # Further filter the results
    if glider:
        logging.info('Finding deployments matching glider: {:}'.format(glider))
        deployments = deployments[deployments.glider.str.contains(glider, case=False)]

    if project_name:
        logging.info('Finding deployments with project name: {:}'.format(project_name))
        deployments = deployments[deployments.project_name.str.contains(project_name, case=False)]

    if dt0:
        logging.info('Finding deployments starting on or after {:}'.format(dt0))
        deployments = deployments[deployments.start_date >= dt0]

    if dt1:
        logging.info('Finding deployments ending on or before {:}'.format(dt1))
        deployments = deployments[deployments.start_date <= dt1]

    # After filtering, add the geometries
    logging.info('Adding geometries to filtered deployments...')
    deployments = df2geodf(deployments)

    no_gps = deployments[deployments.geometry.is_empty]
    logging.warning('Skipping KML creation for {} deployments missing GPS/tracks'.format(no_gps.shape[0]))
    if no_gps.shape[0] == deployments.shape[0]:
        logging.warning('Skipping KML creation -> No GPS/tracks found for all deployments')
        return 0

    # Find the data sets that are within the specified bounding box
    deployments = locate_datasets(deployments, north=north, south=south, east=east, west=west)

    # If debug (-x), print the selected deployments but do not write the kml
    if debug:

        print_columns = ['start_date',
                         'end_date',
                         'glider',
                         'project_name',
                         'os',
                         'distance_flown_km',
                         'deployment_id',
                         'glider_id',
                         'project_id',
                         'coolops_did']

        sys.stdout.write(
            '{:}\n'.format(tabulate.tabulate(deployments[print_columns], tablefmt='psql', headers='keys')))
        logging.info('{:} data sets found'.format(deployments.shape[0]))
        logging.warning('{} deployments skipped for missing tracks'.format(no_gps.shape[0]))

        return 0

    if deployments.empty:
        logging.warning('No deployments found for the specified search criteria')
        return 1

    logging.info('Preparing {:} tracks for kml...'.format(deployments.shape[0]))
    if daily:
        logging.info('Creating daily averaged GPS positions for all tracks')

    # Create the geojson feature collections and write the kml
    tracks = []
    for deployment_name, row in deployments.iterrows():

        gps = fetch_track_to_df(deployment_name)
        if gps.empty:
            logging.warning('No GPS track found for {:}'.format(deployment_name))

        gps.sort_values('time', inplace=True, ascending=True)

        if daily:
            gps = average_daily_track_gps(gps)

        track = latlon_to_geojson_track(gps.latitude, gps.longitude, gps.time, include_points=False)
        if not track:
            logging.warning('Error creating track FeatureCollection: {:}'.format(deployment_name))
            continue

        # Calculate the number of days and deployment status
        t_delta = datetime.datetime.now() - row.start_date
        status = 'Active'
        dt1 = ''
        if not pd.isna(row.end_date):
            t_delta = row.end_date - row.start_date
            status = 'Recovered'
            dt1 = row.end_date

        deployment_props = {'deployment': deployment_name,
                            'status': status,
                            'glider': row.glider,
                            'project': row.project_name,
                            'start_date': row.start_date,
                            'end_date': dt1,
                            'distance': '{:} km'.format(row.distance_flown_km),
                            'days': t_delta.days}

        track['features'][0]['properties'] = deployment_props

        tracks.append(track)

    if not tracks:
        logging.error('There are no tracks for kml creation')
        return 1

    logging.info('Writing {:} tracks to kml...'.format(len(tracks)))

    kml = template.render(kml_name=kml_name, num_deployments=deployments.shape[0], tracks=tracks)

    sys.stdout.write('{:}\n'.format(kml))

    logging.warning('{} deployments skipped for missing tracks'.format(no_gps.shape[0]))

    return 0


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(description=main.__doc__,
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    arg_parser.add_argument('-t', '--template',
                            help='Specify the KML template to be used',
                            default=os.path.realpath('../src/kml/templates/simple_tracks.kml'))

    arg_parser.add_argument('--name',
                            help='KML file display name',
                            dest='kml_name',
                            default='RUCOOL Glider Deployments')

    arg_parser.add_argument('-d', '--daily',
                            help='Average fixes for one point per day',
                            action='store_true')

    arg_parser.add_argument('-g', '--glider',
                            help='Search data sets for the specified glider',
                            type=str)

    arg_parser.add_argument('-p', '--project',
                            help='Search data sets for the specified project name',
                            dest='project_name')

    arg_parser.add_argument('-n', '--north',
                            help='Maximum search latitude',
                            default=90.,
                            type=float)

    arg_parser.add_argument('-s', '--south',
                            help='Minimum search latitude',
                            default=-90.,
                            type=float)

    arg_parser.add_argument('-e', '--east',
                            help='Maximum search longitude',
                            default=180.,
                            type=float)

    arg_parser.add_argument('-w', '--west',
                            help='Minimum search longitude',
                            default=-180.,
                            type=float)

    arg_parser.add_argument('--start_date',
                            type=str,
                            help='Filter by start date')

    arg_parser.add_argument('--end_date',
                            type=str,
                            help='Filter by end date')

    arg_parser.add_argument('-a', '--active',
                            action='store_true',
                            help='Select active deployments only')

    arg_parser.add_argument('-x', '--debug',
                            help='Debug mode. No operations performed',
                            action='store_true')

    arg_parser.add_argument('-l', '--loglevel',
                            help='Verbosity level',
                            type=str,
                            choices=['debug', 'info', 'warning', 'error', 'critical'],
                            default='info')

    parsed_args = arg_parser.parse_args()

    # print(parsed_args)
    # sys.exit(13)

    sys.exit(main(parsed_args))
