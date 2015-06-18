import sys
import argparse


def process_command_line(argv):
    '''Parse the command line and do a first-pass on processing them into a
    format appropriate for the rest of the script.'''

    parser = argparse.ArgumentParser()

    parser.add_argument("--automatic", nargs="+",
                        help="The files to take as automatic segmentation.")
    parser.add_argument("--manual", nargs="+",
                        help="The files tot ake as manual segmentations.")

    args = parser.parse_args(argv[1:])

    assert len(args.automatic) == len(args.manual)

    args.files = zip(args.automatic, args.manual)

    return args


def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's silent and just exposes methods.'''
    config = process_command_line(argv)

    import medpy.io
    import numpy as np

    print "xor,", "auto - manual"

    for (fauto, fmanual) in config.files:
        (auto, manual) = (medpy.io.load(fauto)[0], medpy.io.load(fmanual)[0])

        xor = np.sum(np.logical_xor(auto, manual))/float(auto.size)
        summed_diff = np.sum(auto - manual)/float(auto.size)

        print (float(xor), float(summed_diff))

    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
