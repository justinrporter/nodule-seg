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


def segmentation_stats(auto, manual):
    import numpy as np

    size = float(np.count_nonzero(manual))

    xor = np.count_nonzero(np.logical_xor(auto, manual))
    auto_size = np.count_nonzero(auto)
    dice_index = 2*np.count_nonzero(np.logical_or(auto, manual)) / \
        float(np.count_nonzero(auto)+np.count_nonzero(manual))

    norm_xor = xor / size
    norm_diff = auto_size / size

    return {'dice_index': dice_index,
            'auto_size': auto_size,
            'norm_xor': norm_xor,
            'norm_diff': norm_diff}


def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's silent and just exposes methods.'''
    config = process_command_line(argv)

    import medpy.io
    from medpy.core.exceptions import ImageLoadingError
    import os.path

    hdr = ", ".join(["file", "xor", "size_auto/size_manual", "abs_size",
                     "dice index"])
    print hdr

    for (fauto, fmanual) in config.files:
        try:
            (auto, manual) = (medpy.io.load(fauto)[0],
                              medpy.io.load(fmanual)[0])
        except ImageLoadingError as exc:
            sys.stderr.write("Skipping "+str(exc)+"\n")
            continue

        try:
            stats_dict = segmentation_stats(auto, manual)
        except ValueError:
            sys.stderr.write(" ".join(["Skipping", fauto, "since it differs",
                                       "in size from the manual image",
                                       fmanual, "(", str(auto.size), "vs",
                                       str(manual.size), ")"])+"\n")
            continue

        out = " ".join([str(stats_dict[i]) for i in ['norm_xor',
                                                     'norm_diff',
                                                     'auto_size',
                                                     'dice_index']])

        print os.path.basename(fauto), out

    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
