#! /bin/bash --

. ~/.bashrc;

PATH=${PATH}:/bin:${HOME}/code:${HOME}/code/rugapitools;

app=$(basename $0);

# Default values for options
conda_env='gliders';
minutes=60;
mode='rt';
cdm='raw-trajectory';

# USAGE {{{
USAGE="
NAME
    $app - Display the ERDDAP data set latency for active glider deployments

SYNOPSIS

    $app [h] [-e ENVIRONMENT]

DESCRIPTION

    $app [h] [-e ENVIRONMENT]

    Display the ERDDAP data set latency for active glider deployments
    
    -h
        show help message

    -e ENVIRONMENT
        Use alternate conda ENVIRONMENT [Default=$conda_env]

    -x
        debug (No file I/O performed)
";
# }}}

# Process options
while getopts "he:" option
do
    case "$option" in
        "h")
            echo -e "$USAGE";
            exit 0;
            ;;
        "e")
            conda_env=$OPTARG;
            ;;
        "?")
            echo -e "$USAGE" >&2;
            exit 1;
            ;;
    esac
done

# Remove option from $@
shift $((OPTIND-1));

. logging.sh;
[ "$?" -ne 0 ] && exit 1;

info_msg "Activating conda environment: $conda_env";
conda activate $conda_env;
[ "$?" -ne 0 ] && exit 1;

get_dataset_erddap_status.py;

info_msg "De-activating conda environment: $conda_env";
conda deactivate;

[ -n "$debug" ] && info_msg "DRY-RUN (No file operations performed)";
info_msg "${app} finished processing all specified deployments";
info_msg "Goodbye";

# Print processed deployment names to STDOUT
echo "$processed";

