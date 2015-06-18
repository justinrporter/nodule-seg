'''A script to calculate the center of mass of a segmentation to use that
segmentation as a seed.'''

import sys
import argparse


def process_command_line(argv):
    '''Parse the command line and do a first-pass on processing them into a
    format appropriate for the rest of the script.'''

    parser = argparse.ArgumentParser()

    parser.add_argument("files", nargs="+",
                        help="The images to calculate the COM of.")
    parser.add_argument("--excise", default="-1-label",
                        help="Excise the given string from filenames.")

    args = parser.parse_args(argv[1:])

    return args


def calc_seed(fname):
    '''Calculate the center of mass of the given medpy.io-compatible file.'''
    import medpy.io
    import scipy.ndimage.measurements
    import numpy as np

    image, header = medpy.io.load(fname)  # pylint: disable=unused-variable

    com = scipy.ndimage.measurements.center_of_mass(np.array(image))

    return [int(i) for i in com]


def process_filename(fname, excise_str):
    '''Produce the output filename from the input filename. Right now, we're
    just excising the given string, but if I use this more, it could be a
    regexp'''
    import re

    fname = re.sub(excise_str, '', fname)

    return fname


def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's silent and just exposes methods.'''

    import json
    import os.path

    args = process_command_line(argv)

    com_dict = {}

    for f in args.files:
        com = calc_seed(f)
        com_dict[process_filename(os.path.basename(f),
                                  args.excise)] = com

    json_out = json.dumps(com_dict, sort_keys=True,
                          indent=4, separators=(',', ': '))

    print json_out

    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
