#!/usr/bin/env python

import logging
import argparse
import sys
import tabulate
import pandas as pd
import datetime
import math
from dateutil import parser
from rug.api import get_active_deployments, get_all_deployments, df2geodf
from rug.geo import locate_datasets


def main(args):
    """Search the Rutgers University Coastal Ocean Observation Lab glider deployment API for active deployments"""

    log_level = getattr(logging, args.loglevel.upper())
    log_format = '%(asctime)s:%(module)s:%(levelname)s:%(message)s [line %(lineno)d]'
    logging.basicConfig(format=log_format, level=log_level)

    debug = args.debug
    glider = args.glider
    project_name = args.project_name
    start_date = args.start_date
    end_date = args.end_date
    active = args.active
    add_geometries = False
    north = args.north
    south = args.south
    east = args.east
    west = args.west
    missing = args.missing
    format = args.format

    # Add geopandas geometries if searching by bounding box
    if north is not None:
        add_geometries = True
    if south is not None:
        add_geometries = True
    if east is not None:
        add_geometries = True
    if west is not None:
        add_geometries = True

    # Parse start_date if specified
    dt0 = None
    if start_date:
        try:
            dt0 = parser.parse(start_date)
        except ValueError as e:
            logging.error('Error parsing start date: {:}'.format(start_date))
            return 1
    # Parse end_date if specified
    dt1 = None
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
        deployments = deployments[deployments.glider.str.match(glider)]

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
    no_track_count = 0
    if add_geometries:
        logging.info('Adding geometries to filtered deployments for bounding box search...')
        deployments = df2geodf(deployments)
        no_track_count = deployments[deployments.geometry.is_empty].shape[0]

        if missing:
            logging.info('Finding deployments with missing GPS tracks')
            deployments = deployments[deployments.geometry.is_empty]
        else:

            if north is None:
                north = 90.
            if south is None:
                south = -90.
            if east is None:
                east = 180.
            if west is None:
                west = -179.9

            logging.info('Searching bounding box {}N, {}S, {}E, {}W'.format(north, south, east, west))
            # Find the data sets that are within the specified bounding box
            deployments = locate_datasets(deployments, north=north, south=south, east=east, west=west)

    # Add the days deployed
    now = pd.to_datetime(datetime.datetime.utcnow())
    # Create a tmp_end_date column that has today's date if the deployment(s) are active and do not have an end_date.
    # We'll use this to calculate the number of days deployed.
    tmp_end_dates = []
    for id, row in deployments.iterrows():
        if pd.isnull(row.end_date):
            tmp_end_dates.append(now)
        else:
            tmp_end_dates.append(row.end_date)

    deployments['tmp_end_date'] = tmp_end_dates

    deployments['days'] = [math.ceil((row.tmp_end_date - row.start_date).total_seconds() / (60*60*24)) for id, row in deployments.iterrows()]
    print_columns = ['start_date',
                     'end_date',
                     'days',
                     'glider',
                     'project_name',
                     'os',
                     'distance_flown_km',
                     'deployment_id',
                     'glider_id',
                     'project_id',
                     'coolops_did']

    # Drop the geometry so we can dump as strings
    if add_geometries:
        deployments = deployments.drop(columns=['geometry'])
    # Convert end_date_epoch to a string
#    deployments.end_date_epoch = deployments.end_date_epoch.astype(str)
#    deployments = deployments.reset_index()

    if format == 'csv':
        sys.stdout.write('{:}'.format(deployments.to_csv(columns=print_columns, index=True)))
    elif format == 'json':
        sys.stdout.write('{:}\n'.format(deployments.reset_index().to_json(index=True, date_format='iso', orient='records', indent=4)))
    else:
        sys.stdout.write(
            '{:}\n'.format(tabulate.tabulate(deployments[print_columns], tablefmt=format, headers='keys')))
    logging.info('{:} data sets found'.format(deployments.shape[0]))
    if add_geometries:
        logging.warning('{} data sets excluded from bounding box search due to missing GPS/tracks'.format(no_track_count))


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(description=main.__doc__,
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    arg_parser.add_argument('-g', '--glider',
                            help='Search data sets for the specified glider',
                            type=str)

    arg_parser.add_argument('-p', '--project',
                            help='Search data sets for the specified project name',
                            dest='project_name')

    arg_parser.add_argument('-n', '--north',
                            help='Maximum search latitude (-90 to 90)',
                            type=float)

    arg_parser.add_argument('-s', '--south',
                            help='Minimum search latitude (-90 to 90)',
                            type=float)

    arg_parser.add_argument('-e', '--east',
                            help='Maximum search longitude (-180 to 180)',
                            type=float)

    arg_parser.add_argument('-w', '--west',
                            help='Minimum search longitude (-180 to 180)',
                            type=float)

    arg_parser.add_argument('-m', '--missing',
                            help='Show deployments with missing GPS tracks',
                            action='store_true')

    arg_parser.add_argument('--start_date',
                            type=str,
                            help='Filter by start date')

    arg_parser.add_argument('--end_date',
                            type=str,
                            help='Filter by end date')

    arg_parser.add_argument('-f', '--format',
                            help='Pretty print the results using a tabulate format',
                            type=str,
                            choices=['csv', 'json'] + tabulate.tabulate_formats,
                            default='psql')

    arg_parser.add_argument('-a', '--active',
                            action='store_true',
                            help='Select all deployments regardless of status (active or recovered)')

    arg_parser.add_argument('-x', '--debug',
                            help='Debug mode. No operations performed',
                            action='store_true')

    arg_parser.add_argument('-l', '--loglevel',
                            help='Verbosity level',
                            type=str,
                            choices=['debug', 'info', 'warning', 'error', 'critical'],
                            default='info')

    parsed_args = arg_parser.parse_args()

#    print(parsed_args)
#    sys.exit(13)

    sys.exit(main(parsed_args))
