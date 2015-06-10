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
    parser.add_argument("--path", type=str, default="",
                        help="A directory to dump the output in. Default is " +
                        "the directory of the original file.")

    args = parser.parse_args(argv[1:])

    return args


def convert(fname, path):
    '''convert fname from the input ANALYZE format into a NifTi formatted
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

    new_fname = fname.rstrip(ext) + ".nii"

    if path:
        # path determines where we should save
        import os.path
        new_fname = os.path.join(path, os.path.basename(new_fname))

    print "Saving", new_fname
    medpy.io.save(image, new_fname, header)


def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's silent and just exposes methods.'''

    args = process_command_line(argv)

    for fname in args.fnames:
        convert(fname, args.path)

    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
