#!/usr/bin/env python

import sys
import os
import argparse
import logging
from dateutil import parser
import matplotlib.pyplot as plt
import matplotlib as mpl
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from rug.api import get_active_deployments, get_all_deployments, df2geodf
from rug.geo import locate_datasets, fetch_track_to_df


def main(args):
    """Search the RU-COOL glider deployment API for datasets and plot the resulting tracks on a map"""

    # Set up logger
    log_level = getattr(logging, args.loglevel.upper())
    log_format = '%(asctime)s:%(module)s:%(levelname)s:%(message)s [line %(lineno)d]'
    logging.basicConfig(format=log_format, level=log_level)

    dataset_ids = args.dataset_ids
    exclude_ids = args.exclude or []
    active = args.active
    start_date = args.start_ts
    end_date = args.end_ts
    debug = args.debug
    north = args.north
    south = args.south
    east = args.east
    west = args.west
    glider = args.glider
    img_name = args.img_name
    clobber = args.clobber
    valid_image_types = ['png',
                         'jpg',
                         'pdf',
                         'svg']

    # Plotting args
    central_longitude = args.central_longitude
    projection = args.projection
    global_map = args.global_map
    gps_padding = args.gps_padding
    edge_color = "black"
    land_color = "sandybrown"
    ocean_color = cfeature.COLORS['water']  # cfeature.COLORS['water'] is the standard
    track_color = args.track_color
    marker = 'None'
    marker_size = 1.0
    linewidth = args.linewidth
    linestyle = '-'

    if img_name:
        (img_path, iname) = os.path.split(img_name)
        if not os.path.isdir(img_path):
            logging.error('Specified image destination directory does not exist: {:}'.format(img_path))
            return 1

        tokens = iname.split('.')
        if len(tokens) < 2:
            logging.info('No image type specified. Valid image types are: {:}'.format(valid_image_types))
            return 1

        if tokens[-1] not in valid_image_types:
            logging.info('Invalid image type specified: {:}'.format(tokens[-1]))
            logging.info('Valid image types are: {:}'.format(valid_image_types))
            return 1

        if os.path.isfile(img_name):
            if not clobber:
                logging.warning('Image exists (Use -c to clobbber): {:}'.format(img_name))
                return 1

    dt0 = None
    dt1 = None
    if active:
        logging.info('Selecting active deployments')
        deployments = get_active_deployments()
    else:
        logging.info('Selecting all deployments')
        deployments = get_all_deployments()

        # Parse start_date if specified
        if start_date:
            try:
                dt0 = parser.parse(start_date)
            except ValueError as e:
                logging.error('Error parsing start date {:}: {:}'.format(start_date, e))
        # Parse end_date if specified
        if end_date:
            try:
                dt1 = parser.parse(end_date)
            except ValueError as e:
                logging.error('Error parsing end date{:}: {:}'.format(end_date, e))

        if dataset_ids:
            good_ids = []
            for dataset_id in dataset_ids:
                if dataset_id not in deployments.index:
                    logging.warning('Invalid deployment id: {:}'.format(dataset_id))
                    continue

                good_ids.append(dataset_id)

            if good_ids:
                logging.info('Keeping only specified dataset IDs')
                deployments = deployments.loc[good_ids]
            else:
                logging.error('No valid deployment IDs specified')
                return 1
        else:
            # Filter by glider
            if glider:
                logging.info('Finding deployments matching glider: {:}'.format(glider))
                deployments = deployments[deployments.glider.str.match(glider)]

            # Filter by start date
            if dt0:
                logging.info('Finding deployments starting on or after {:}'.format(dt0))
                deployments = deployments[deployments.start_date >= dt0]

            # Filter by end date
            if dt1:
                logging.info('Finding deployments ending on or before {:}'.format(dt1))
                deployments = deployments[deployments.start_date <= dt1]

    if debug:
        logging.info('Debug (-x). Skipping map creation')
        logging.info('Found {:} data sets'.format(deployments.shape[0]))
        print_columns = ['start_date',
                         'end_date',
                         'project_name']
        sys.stdout.write('{:}\n'.format(deployments.to_csv(index=True, columns=print_columns)))
        logging.info('Found {:} deployments'.format(deployments.shape[0]))
        return 0

    # Add the geometries so that we can do some geometric stuff
    logging.info('Adding geometries to {:} deployments'.format(deployments.shape[0]))
    deployments = df2geodf(deployments)
    deployments = locate_datasets(deployments, north=north, south=south, east=east, west=west)

    # Remove deployments for which there is no GPS track
    missing_count = deployments.geometry.is_empty.sum()
    logging.info('Removing {:} deployments with no bounding box'.format(missing_count))
    deployments = deployments[~deployments.geometry.is_empty]
    logging.info('Plotting {:} data sets'.format(deployments.shape[0]))
    if deployments.empty:
        return 0

    # bbox format: [S, W, N, E]
    bbox = [deployments.geometry.total_bounds[1] - gps_padding,
            deployments.geometry.total_bounds[3] + gps_padding,
            deployments.geometry.total_bounds[0] - gps_padding,
            deployments.geometry.total_bounds[2] + gps_padding]

    kws = {'projection': getattr(ccrs, projection)(central_longitude=central_longitude)}
    logging.info('Using {:} map projection'.format(projection))
    map_fig, map_ax = plt.subplots(figsize=(11, 8), subplot_kw=kws)

    # Automatically create a global map if the projection is Mollweide
    if projection == 'Mollweide':
        global_map = True

    if global_map:
        logging.info('Setting global bounds')
        map_ax.set_global()
    else:
        logging.info('Setting extent to search bounds')
        logging.info('Search bounding box: {:}N {:}S {:}E {:}W'.format(bbox[2], bbox[0], bbox[3], bbox[1]))
        map_ax.set_extent(bbox)

    map_ax.set_facecolor(ocean_color)  # way faster than adding the ocean feature above

    # Land
    lakes = cfeature.NaturalEarthFeature(category='physical',
                                         name='land',
                                         scale='10m',
                                         edgecolor=edge_color,
                                         facecolor=land_color,
                                         linewidth=0.5)
    map_ax.add_feature(lakes,
                       zorder=0)

    # Lakes/Rivers
    land = cfeature.NaturalEarthFeature(category='physical',
                                        name='lakes',
                                        scale='110m',
                                        edgecolor=edge_color,
                                        facecolor=ocean_color)
    map_ax.add_feature(land,
                       zorder=1)

    cbar = mpl.colormaps['rainbow'].resampled(deployments.shape[0])
    i = 0
    for deployment_name, row in deployments.iterrows():

        if deployment_name in exclude_ids:
            logging.warning('Skipping deployment {}'.format(deployment_name))
            continue

        logging.info('Fetching {:} track'.format(deployment_name))

        gps = fetch_track_to_df(deployment_name)
        if gps.empty:
            logging.warning('No GPS track found for {:}'.format(deployment_name))
            continue

        track = gps.sort_values('time', ascending=True)

        # Plot the track
        l_color = cbar(i)
        if track_color:
            l_color = track_color

        map_ax.plot(track.longitude, track.latitude,
                    marker=marker,
                    markersize=marker_size,
                    linestyle=linestyle,
                    linewidth=linewidth,
                    color=l_color,
                    transform=ccrs.PlateCarree())

        i += 1

    if img_name:
        logging.info('Writing image: {:}'.format(img_name))
        plt.savefig(img_name, dpi=300)
    else:
        logging.info('Displaying image')
        plt.show()

    return 0


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(description=main.__doc__,
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    arg_parser.add_argument('dataset_ids',
                            nargs='*',
                            help='One or more valid DAC data set IDs to search for')

    arg_parser.add_argument('--exclude',
                            nargs='*',
                            help='Do not plot tracks from these data sets',
                            type=str)

    arg_parser.add_argument('-a', '--active',
                            action='store_true',
                            help='Plot active deployments only')

    arg_parser.add_argument('-o', '--image_name',
                            dest='img_name',
                            help='Write image to the specified filename. If not specified, image is displayed. The '
                                 'extension specifies the image type',
                            type=str)

    arg_parser.add_argument('--start_time',
                            dest='start_ts',
                            help='Search start time',
                            type=str)

    arg_parser.add_argument('--end_time',
                            dest='end_ts',
                            help='Search end time',
                            type=str)

    arg_parser.add_argument('--hours',
                            type=float,
                            help='Number of hours before now. Set to <= 0 to disable',
                            default=24)

    arg_parser.add_argument('-n', '--north',
                            help='Maximum search latitude',
                            type=float,
                            default=90.)

    arg_parser.add_argument('-s', '--south',
                            help='Minimum search latitude',
                            type=float,
                            default=-90.)

    arg_parser.add_argument('-e', '--east',
                            help='Maximum search longitude',
                            type=float,
                            default=180.)

    arg_parser.add_argument('-w', '--west',
                            help='Minimum search longitude',
                            type=float,
                            default=-179.9)

    arg_parser.add_argument('-g', '--glider',
                            help='Return data sets with glider call signs starting with the specified string',
                            type=str)

    arg_parser.add_argument('--color',
                            dest='track_color',
                            help='Specify a single color for all tracks')

    arg_parser.add_argument('--linewidth',
                            help='Track linewidth',
                            type=float,
                            default=2.)

    arg_parser.add_argument('--global',
                            dest='global_map',
                            help='Set map bounds to global',
                            action='store_true')

    arg_parser.add_argument('-p', '--projection',
                            help='Set map projection',
                            choices=['PlateCarree', 'Mollweide', 'Robinson', 'Mercator'],
                            default='PlateCarree',
                            type=str)

    arg_parser.add_argument('--central_longitude',
                            help='Specify longitude for map center',
                            type=float,
                            default=0.)

    arg_parser.add_argument('--padding',
                            dest='gps_padding',
                            help='Padding added to axes limits if not creating a global map (--global)',
                            type=float,
                            default=0.)

    arg_parser.add_argument('-c', '--clobber',
                            help='Clobber existing image',
                            action='store_true')

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
