import logging
import sys
from rug.api import get_all_deployments
from gdt.erddap import GdacClient
from gdt.apis.dac import fetch_dac_catalog_dataframe

# Set up logger
log_level = getattr(logging, 'INFO')
log_format = '%(asctime)s:%(module)s:%(levelname)s:%(message)s [line %(lineno)d]'
logging.basicConfig(format=log_format, level=log_level)

# RU-COOL data sets
ru_datasets = get_all_deployments()

# DAC data sets
dac_client = GdacClient()
# Fetch all available DAC data sets
dac_client.search_datasets(include_delayed_mode=True)

# Fetch the DAC registered deployments API
dac_catalog = fetch_dac_catalog_dataframe()

# Merge the dac_datasets with the dac_catalog
all_dac_datasets = dac_client.datasets.merge(dac_catalog.drop(columns=['wmo_id']), on='dataset_id', how='left')

# Keep only the dac_datasets from username = 'rutgers'
rucool_dac_datasets = all_dac_datasets[all_dac_datasets.username == 'rutgers']

keep_cols = ['start_year',
             'project_name',
             'payload_bay',
             'lat_min',
             'lat_max',
             'lon_min',
             'lon_max',
             'num_profiles',
             'erddap',
             'username',
             'wmo_id']
datasets = rucool_dac_datasets.merge(
    ru_datasets.reset_index().rename(columns={'deployment_name': 'dataset_id'}).set_index('dataset_id'),
    on='dataset_id', how='outer')[keep_cols]

datasets = datasets.rename(columns={'payload_bay': 'ctd_sn'})
datasets['start_year'] = datasets.start_year.fillna(0).astype(int)
in_dac = datasets[~datasets.erddap.isna()].sort_values(by='start_year', ascending=False)
out_dac = datasets[datasets.erddap.isna()].sort_values(by='start_year', ascending=False)