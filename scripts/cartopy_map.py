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

#    exclude_ids = args.exclude or []
#    start_date = args.start_ts
#    end_date = args.end_ts
    debug = args.debug
    north = args.north
    south = args.south
    east = args.east
    west = args.west
#    glider = args.glider
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
    opacity = args.opacity

    edge_color = "black"
    land_color = "sandybrown"
    ocean_color = cfeature.COLORS['water']  # cfeature.COLORS['water'] is the standard

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

    # bbox format: [S, W, N, E]
    bbox = [west - gps_padding,
            east + gps_padding,
            south - gps_padding,
            north + gps_padding]

    kws = {'projection': getattr(ccrs, projection)(central_longitude=central_longitude)}
    logging.info('Using {:} map projection'.format(projection))
    map_fig, map_ax = plt.subplots(figsize=(11, 8), subplot_kw=kws)

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

    arg_parser.add_argument('--exclude',
                            nargs='*',
                            help='Do not plot tracks from these data sets',
                            type=str)

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

    arg_parser.add_argument('--opacity',
                            help='Opacity of hexbin points',
                            type=float,
                            default=1.0)

    arg_parser.add_argument('-g', '--glider',
                            help='Return data sets with glider call signs starting with the specified string',
                            type=str)

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
