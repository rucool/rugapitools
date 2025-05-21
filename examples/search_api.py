"""Example for searching the RU-COOL glider deployment API and filtering results"""
import logging
import pandas as pd
import cartopy.feature as cfeature
from dateutil import parser
from rug.api import get_active_deployments, get_all_deployments, df2geodf
from rug.geo import locate_datasets

# Set up logger
log_level = getattr(logging, 'INFO')
log_format = '%(asctime)s:%(module)s:%(levelname)s:%(message)s [line %(lineno)d]'
logging.basicConfig(format=log_format, level=log_level)

dataset_ids = []
active = False
start_date = '2023-01-01'
end_date = None
debug = False
north = None
south = None
east = None
west = None
#north = 90.
#south = -90.
#east = 180.
#west = -180.
add_geometries = True
if not north and not south and not east and not west:
    add_geometries = False
glider = ''
img_name = ''
clobber = True
valid_image_types = ['png',
                     'jpg',
                     'pdf',
                     'svg']

# Plotting args
central_longitude = -74.
projections = ['PlateCarree',
            'Robinson',
            'Mollweide']
projection = projections[0]
global_map = False
clamp_bounds = True
edge_color = "black"
land_color = "tan"
ocean_color = cfeature.COLORS['water']  # cfeature.COLORS['water'] is the standard
marker = 'None'
marker_size = 1.0
linestyle = '-'

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
            logging.error('Error parsing start date: {:}'.format(start_date))
    # Parse end_date if specified
    if end_date:
        try:
            dt1 = parser.parse(end_date)
        except ValueError as e:
            logging.error('Error parsing end date: {:}'.format(end_date))

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
            deployments = pd.DataFrame()
    else:
        # Further filter the results
        if glider:
            logging.info('Finding deployments matching glider: {:}'.format(glider))
            deployments = deployments[deployments.glider.str.match(glider)]

        if dt0:
            logging.info('Finding deployments starting on or after {:}'.format(dt0))
            deployments = deployments[deployments.start_date >= dt0]

        if dt1:
            logging.info('Finding deployments ending on or before {:}'.format(dt1))
            deployments = deployments[deployments.start_date <= dt1]

        # After filtering, add the geometries
        if add_geometries:
            logging.info('Adding geometries to filtered deployments...')
            deployments = df2geodf(deployments)

            # Find the data sets that are within the specified bounding box
            deployments = locate_datasets(deployments, north=north, south=south, east=east, west=west)
