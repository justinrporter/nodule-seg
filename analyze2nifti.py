'''Convert analyze images to NiFTi images, since ITK has depricated support
for ANALYZE .img/.hdr formats.'''

import sys
import argparse


def process_command_line(argv):
    '''Parse the command line and do a first-pass on processing them into a
    format appropriate for the rest of the script.'''
    parser = argparse.ArgumentParser()

    parser.add_argument("fnames", nargs="+",
                        help="The arguments the script operates on.")

    args = parser.parse_args(argv[1:])

    return args


def convert(fname):
    '''convert fname from the input ANALYZE format into a NiFTi formatted
    image'''
    import medpy.io

    image, header = medpy.io.load(fname)

    if fname.find(".img"):
        ext = ".img"
    elif fname.find(".hdr"):
        ext = ".hdr"
    else:
        raise IOError("The file "+fname+" didn't have an appropriate file" +
                      "extension('hdr' or 'img')")

    new_fname = fname.rstrip(ext) + ".NiFTi"

    medpy.io.save(image, new_fname, header )


def main(argv=None):
    args = process_command_line(argv)

    return 1

if __name__ == "__main__":
    exit_status = main(sys.argv)
    sys.exit(exit_status)
