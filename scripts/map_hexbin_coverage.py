#!/usr/bin/env python

import logging
import argparse
import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl import ticker
from dateutil import parser
from rug.api import get_all_deployments, df2geodf
from rug.geo import locate_datasets, fetch_track_to_df


def main(args):
    """Plot hexbin coverage of RU-COOL glider deployments"""

    log_level = getattr(logging, args.loglevel.upper())
    log_format = '%(asctime)s:%(module)s:%(levelname)s:%(message)s [line %(lineno)d]'
    logging.basicConfig(format=log_format, level=log_level)

    glider = args.glider
    project_name = args.project_name
    start_date = args.start_date
    end_date = args.end_date
    add_geometries = False
    north = args.north
    south = args.south
    east = args.east
    west = args.west
    img_name = args.img_name
    clobber = args.clobber
    valid_image_types = ['png',
                         'jpg',
                         'pdf',
                         'svg']
    dpi = args.dpi
    gridsize = args.gridsize
    # Cartopy mapping args
    central_longitude = 0.
    projection = args.projection
    gps_padding = args.gps_padding
    opacity = args.opacity
    log_scale = args.log_scale
    vmin = args.vmin
    vmax = args.vmax
    mincount = args.mincount
    cmap = args.colormap
    if cmap not in plt.colormaps():
        logging.error('Invalid matplotlib colormap name: {:}'.format(cmap))
        return 1
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
                logging.warning('Image exists (Use -c to clobber): {:}'.format(img_name))
                return 1

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
            logging.error('Error parsing start date {:} ({:}}'.format(start_date, e))
            return 1
    # Parse end_date if specified
    dt1 = None
    if end_date:
        try:
            dt1 = parser.parse(end_date)
        except ValueError as e:
            logging.error('Error parsing end date {:} ({:})'.format(end_date, e))
            return 1

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
    if add_geometries:

        if north is None:
            north = 90.
        if south is None:
            south = -90.
        if east is None:
            east = 180.
        if west is None:
            west = -179.9

        logging.info('Adding geometries to filtered deployments for bounding box search...(Patience please)')
        deployments = df2geodf(deployments)

        logging.info('Searching bounding box {}N, {}S, {}E, {}W'.format(north, south, east, west))
        # Find the data sets that are within the specified bounding box
        deployments = locate_datasets(deployments, north=north, south=south, east=east, west=west)

    # Add the tracks for all selected deployments
    tracks = pd.DataFrame()
    logging.info('Fetching deployment tracks...')
    now_dt = pd.to_datetime('now')
    for deployment, row in deployments.iterrows():
        logging.info('Adding {:} track'.format(deployment))

        track = fetch_track_to_df(deployment)

        track['deployment'] = deployment

        tracks = pd.concat([tracks, track])

        # Update the end_date for all active deployments
        if pd.isna(row.end_date):
            deployments.loc[deployment, 'end_date'] = now_dt

    tracks = tracks.set_index('deployment')

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
    land = cfeature.NaturalEarthFeature(category='physical',
                                        name='land',
                                        scale='10m',
                                        edgecolor=edge_color,
                                        facecolor=land_color,
                                        linewidth=0.5)
    map_ax.add_feature(land,
                       zorder=0)

    # States
    states = cfeature.NaturalEarthFeature(category='cultural',
                                          name='admin_1_states_provinces_lines',
                                          scale='50m',
                                          facecolor='none',
                                          linewidth=0.5)

    map_ax.add_feature(states, zorder=1)

    # Lakes/Rivers
    lakes = cfeature.NaturalEarthFeature(category='physical',
                                         name='lakes',
                                         scale='110m',
                                         edgecolor=edge_color,
                                         facecolor=ocean_color)
    map_ax.add_feature(lakes,
                       zorder=2)

    # Plot the hexbins
    if log_scale:
        logging.info('Plotting hexbins using log scaling')
        # Plot results on log scale
        c = map_ax.hexbin(tracks.longitude, tracks.latitude,
                          gridsize=gridsize,
                          cmap=cmap,
                          transform=ccrs.PlateCarree(),
                          alpha=opacity,
                          bins='log',
                          mincnt=mincount,
                          vmin=vmin,
                          vmax=vmax)
    else:
        logging.info('Plotting hexbins using linear scale')
        # Plot results using vmin, vmax and mincount
        c = map_ax.hexbin(tracks.longitude, tracks.latitude,
                          gridsize=gridsize,
                          cmap=cmap,
                          transform=ccrs.PlateCarree(),
                          alpha=opacity,
                          mincnt=mincount,
                          vmin=vmin,
                          vmax=vmax)

    lat_locator = ticker.LatitudeLocator()
    lon_locator = ticker.LongitudeLocator()

    # Figure out ticks
    x_ticks = lat_locator.tick_values(vmin=bbox[0], vmax=bbox[1])
    y_ticks = lon_locator.tick_values(vmin=bbox[2], vmax=bbox[3])

    # Update map axes
    logging.info('Setting map extents: north={:}, south={:}, east={:}, west={:}'.format(bbox[3],
                                                                                        bbox[2],
                                                                                        bbox[1],
                                                                                        bbox[0]))
    # Set x and y ticks
    map_ax.set_xticks(x_ticks, crs=ccrs.PlateCarree())
    map_ax.set_yticks(y_ticks, crs=ccrs.PlateCarree())

    lon_formatter = ticker.LongitudeFormatter(number_format='.1f',
                                              degree_symbol=u"\N{DEGREE SIGN}",
                                              dateline_direction_label=True)
    lat_formatter = ticker.LatitudeFormatter(number_format='.1f',
                                             degree_symbol=u"\N{DEGREE SIGN}")

    map_ax.xaxis.set_major_formatter(lon_formatter)
    map_ax.yaxis.set_major_formatter(lat_formatter)

    map_ax.set_extent((bbox[0], bbox[1], bbox[2], bbox[3]), crs=ccrs.PlateCarree())
    # Add the colorbar
    cb = map_fig.colorbar(c, ax=map_ax, shrink=0.8, orientation='vertical')
    # Title the colorbar
    if log_scale:
        cb.set_label('Total GPS Fixes (log scale)')
    else:
        cb.set_label('Total GPS Fixes (linear scale)')

    # Title the figure
    dt_string = '{:} - {:}'.format(deployments.end_date.min().strftime('%Y-%m-%d'), deployments.end_date.max().strftime('%Y-%m-%d'))
    map_ax.set_title('RU-COOL Glider Coverage: {:}'.format(dt_string))

    if img_name:
        logging.info('Writing image: {:}'.format(img_name))
        plt.savefig(img_name, dpi=dpi)
    else:
        logging.info('Displaying image')
        plt.show()


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(description=main.__doc__,
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    arg_parser.add_argument('-g', '--glider',
                            help='Search data sets for the specified glider',
                            type=str)

    arg_parser.add_argument('--project',
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

    arg_parser.add_argument('--start_date',
                            type=str,
                            help='Filter by start date')

    arg_parser.add_argument('--end_date',
                            type=str,
                            help='Filter by end date')

    arg_parser.add_argument('--padding',
                            dest='gps_padding',
                            help='Padding added to axes limits if not creating a global map (--global)',
                            type=float,
                            default=0.)

    arg_parser.add_argument('-p', '--projection',
                            help='Set map projection',
                            choices=['PlateCarree', 'Mollweide', 'Robinson', 'Mercator'],
                            default='Mercator',
                            type=str)

    arg_parser.add_argument('--gridsize',
                            help='Number of hexbin grid points',
                            default=100,
                            type=int)

    arg_parser.add_argument('--vmin',
                            help='Colorbar minimum.',
                            type=int,
                            default=1)

    arg_parser.add_argument('--vmax',
                            help='Colorbar maximum.',
                            type=int,
                            default=100)

    arg_parser.add_argument('--mincount',
                            help='Minimum number of points that must be in a hexbin to display',
                            type=int,
                            default=1)

    arg_parser.add_argument('--log_scale',
                            help='Log scale the hexbin results',
                            action='store_true')

    arg_parser.add_argument('--opacity',
                            help='Opacity of plotted hexbins',
                            type=float,
                            default=1.0)

    arg_parser.add_argument('--colormap',
                            help='Valid matplotlib colormap. Use plt.colormaps() for available colormaps',
                            default='viridis',
                            type=str)

    arg_parser.add_argument('-o', '--image_name',
                            dest='img_name',
                            help='Write image to the specified filename. If not specified, image is displayed. The '
                                 'extension specifies the image type',
                            type=str)

    arg_parser.add_argument('-c', '--clobber',
                            help='Clobber existing image',
                            action='store_true')

    arg_parser.add_argument('--dpi',
                            help='Resolution, in dpi, of the image',
                            type=int,
                            default=300)

    arg_parser.add_argument('-l', '--loglevel',
                            help='Verbosity level',
                            type=str,
                            choices=['debug', 'info', 'warning', 'error', 'critical'],
                            default='info')

    parsed_args = arg_parser.parse_args()

#    print(parsed_args)
#    sys.exit(13)

    sys.exit(main(parsed_args))
