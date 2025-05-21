#!/usr/bin/env python

import argparse
import pandas as pd
import requests
import logging
import sys
import io
from rug.api.urls import end_points


def main(args):
    """Create a kml file displaying Rutgers University Coastal Ocean Observation Lab glider tracks retrieved from the
    API for the specified deployment names."""

    log_level = getattr(logging, args.loglevel.upper())
    log_format = '%(asctime)s:%(module)s:%(levelname)s:%(message)s [line %(lineno)d]'
    logging.basicConfig(format=log_format, level=log_level)

    project_name = args.project_name
    base_url = end_points['DEPLOYMENTS'].url

    url = '{}/?type=projects&project={}'.format(base_url, project_name)

    r = requests.get(url)
    if r.status_code != 200:
        logging.error('Request failed: {} ({})'.format(r.status_code, r.reason))
        return 1

    # Fetch the response and keep on 'data'
    response = r.json()['data']
    if not response:
        logging.warning('No deployments found for project {}'.format(project_name))
        return 1

    # Convert to DataFrame
    deployments = pd.DataFrame(response)
    deployments['start_date'] = pd.to_datetime(deployments['start_date_epoch'], unit='s')
    deployments['end_date'] = pd.to_datetime(deployments['end_date_epoch'], unit='s')
    
    sys.stdout.write('{:}\n'.format(deployments.to_csv(index=False)))


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(description=main.__doc__,
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    arg_parser.add_argument('project_name',
                            help='Name of a registered RU-COOL project',
                            type=str)

    arg_parser.add_argument('-l', '--loglevel',
                            help='Verbosity level',
                            type=str,
                            choices=['debug', 'info', 'warning', 'error', 'critical'],
                            default='info')

    parsed_args = arg_parser.parse_args()

    #    print(parsed_args)
    #    sys.exit(13)

    sys.exit(main(parsed_args))
