import sys
import argparse
import os
import re


def process_command_line(argv):
    '''Parse the command line and do a first-pass on processing them into a
    format appropriate for the rest of the script.'''

    parser = argparse.ArgumentParser(formatter_class=argparse.
                                     ArgumentDefaultsHelpFormatter)

    parser.add_argument("labels", nargs="+",
                        help="The images the script operates on.")
    parser.add_argument("--path", default=os.getcwd(),
                        help="Output path")

    args = parser.parse_args(argv[1:])

    return args


def compute_union(images):
    import numpy as np

    consensus = np.zeros(images[0].shape)

    n_img = 0
    for img in images:
        if 1e4 < np.count_nonzero(img) < 1e6:
            consensus += (img != 0)
            n_img += 1

    if n_img == 0:
        raise ValueError("No image in had an acceptable size.")

    consensus = consensus >= (2/3.0) * n_img

    if not (1e3 < np.count_nonzero(consensus) < 1e7):
        raise ValueError("Consensus image had unacceptable size")

    return consensus


def outname(inname):
    ext = inname[inname.rfind('.'):]
    return inname[:inname.rfind('-')]+"-consensus"+ext


def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's silent and just exposes methods.'''
    args = process_command_line(argv)

    import medpy.io
    from os import listdir
    from os.path import isfile, join

    img_groups = {}
    for f in [f for f in listdir(args.path) if isfile(join(args.path, f))]:
        if True in [l in f for l in args.labels]:
            abspath = os.path.join(args.path, f)
            img_groups.setdefault(f.split('-')[0], []).append(abspath)

    for key in img_groups:
        (images, headers) = zip(*[medpy.io.load(fname) for fname
                                  in img_groups[key]])

        try:
            consensus = compute_union(images)
        except ValueError as exc:
            print exc, "images:", img_groups[key]
            continue

        medpy.io.save(consensus, outname(img_groups[key][0]), headers[0])
        print outname(img_groups[key][0])

    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
