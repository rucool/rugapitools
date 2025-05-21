#!/usr/bin/env python

import logging
import argparse
import sys
import datetime
import tabulate
import pandas as pd
from pprint import pprint as pp
from erddapy import ERDDAP
from rug.api import get_active_deployments, get_all_deployments


def main(args):
    """Display ERDDAP data set start time, end time and latency (hrs) for the specified RU-COOL deployments."""

    log_level = getattr(logging, args.loglevel.upper())
    log_format = '%(asctime)s:%(module)s:%(levelname)s:%(message)s [line %(lineno)d]'
    logging.basicConfig(format=log_format, level=log_level)

    deployments = args.deployments
    erddap_url = 'https://slocum-data.marine.rutgers.edu/erddap'
    protocol = 'tabledap'
    response_type = 'csv'
    format = args.format
    ascending = args.ascending
    descending = args.descending

    if not deployments:
        logging.info('Selecting active deployments...')
        deployments_df = get_active_deployments()
    else:
        logging.error('Need to implement multiple deployments search')
        return 1

    e = ERDDAP(server=erddap_url, protocol=protocol, response=response_type)
    url = e.get_download_url(dataset_id='allDatasets')
    erddap_datasets = pd.read_csv(url, parse_dates=['minTime', 'maxTime'], skiprows=[1])

    # rename columns more friendly by replacing spaces with underscores and lower casing everything
    columns = {s: s.replace(' ', '_').lower() for s in erddap_datasets.columns}
    columns['datasetID'] = 'dataset_id'
    erddap_datasets.rename(columns=columns, inplace=True)

    # Use dataset_id as the index
    erddap_datasets.set_index('dataset_id', inplace=True)

    # Find deployments that have at least one erddap dataset id
    deployment_ids = deployments_df.index.tolist()
    erddap_ids = erddap_datasets.index.tolist()
    has_ids = []
    for eid in erddap_ids:
        for did in deployment_ids:
            if eid.startswith(did):
                has_ids.append(eid)

    if not has_ids:
        logging.warning('No ERDDAP data sets found for deployment ids')
        return 1

    datasets = erddap_datasets.loc[has_ids, ['mintime', 'maxtime']]

    now = pd.to_datetime(datetime.datetime.now())
    datasets['latency_hrs'] = ((now.utcnow() - datasets.maxtime).dt.total_seconds()/3600).astype(int)

    # Sort based on args.sort. True == ascending, False == descending
    if ascending:
        datasets = datasets.sort_values(by='latency_hrs', ascending=True)
    elif descending:
        datasets = datasets.sort_values(by='latency_hrs', ascending=False)

    sys.stdout.write('{:}\n'.format(tabulate.tabulate(datasets, tablefmt=format, headers='keys')))
    logging.info('{:} data sets found'.format(datasets.shape[0]))

    # Calculate how many hours ago
    return 0


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(description=main.__doc__,
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    arg_parser.add_argument('deployments',
                            nargs='*',
                            help='RU-COOL deployment names. If not specified, active deployments are searched')

    arg_parser.add_argument('-f', '--format',
                            help='Pretty print the results using a tabulate format',
                            type=str,
                            choices=['csv', 'json'] + tabulate.tabulate_formats,
                            default='fancy_grid')

    arg_parser.add_argument('-a', '--ascending',
                            help='Sort by latency in ascending order',
                            action='store_true')

    arg_parser.add_argument('-d', '--descending',
                            help='Sort by latency in descending order',
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
