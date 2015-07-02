import sys
import argparse
import os
import medpy.io
import compare_segmentations


def process_command_line(argv):
    '''Parse the command line and do a first-pass on processing them into a
    format appropriate for the rest of the script.'''

    parser = argparse.ArgumentParser(formatter_class=argparse.
                                     ArgumentDefaultsHelpFormatter)

    parser.add_argument("labels", nargs="+",
                        help="The images the script operates on.")
    parser.add_argument("--path", default=os.getcwd(),
                        help="Output path")
    parser.add_argument("--outpath", default=None,
                        help="The path to place the output images")
    parser.add_argument("--thresholds", nargs="+", default=[2.0/3], type=float,
                        help="A list of agreement thresholds to try")

    args = parser.parse_args(argv[1:])

    print args

    return args


def compute_union(images, threshold):
    import numpy as np

    consensus = np.zeros(images[0].shape)

    n_img = 0
    for img in images:
        if 1e4 < np.count_nonzero(img) < 1e6:
            consensus += (img != 0)
            n_img += 1

    if n_img == 0:
        raise ValueError("No image in had an acceptable size.")

    consensus = consensus >= (threshold * n_img)

    if not (1e3 < np.count_nonzero(consensus) < 1e7):
        print consensus.shape
        raise ValueError("Consensus image had unacceptable size " +
                         str(np.count_nonzero(consensus)))

    return consensus


def label_swap(inname, new_label="consensus"):
    ext = inname[inname.rfind('.'):]
    return inname[:inname.rfind('-')]+"-"+new_label+ext


def build_image(images, headers, img_group, threshold):
    try:
        consensus = compute_union(images, threshold)
    except ValueError as exc:
        print exc, "images:", img_group
        return

    medpy.io.save(consensus,
                  label_swap(img_group[0], "consensus"),
                  headers[0])


def run_thresholds(images, thresholds, manual_name):
    results = {}

    for threshold in thresholds:
        # pylint: disable=W0612
        (manual, hdr) = medpy.io.load(manual_name)

        consensus = compute_union(images, threshold)

        stats = compare_segmentations.segmentation_stats(consensus,
                                                         manual)

        results[threshold] = stats

    return results


def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's silent and just exposes methods.'''
    args = process_command_line(argv)

    from os import listdir
    from os.path import isfile, join

    img_groups = {}
    for f in [f for f in listdir(args.path) if isfile(join(args.path, f))]:
        if True in [l in f for l in args.labels]:
            abspath = os.path.join(args.path, f)
            img_groups.setdefault(f.split('-')[0], []).append(abspath)

    results = {}

    for key in img_groups:
        (images, headers) = zip(*[medpy.io.load(fname) for fname
                                  in img_groups[key]])

        arb_img_name = img_groups[key][0]

        if len(args.thresholds) == 1:
            build_image(images, headers, img_groups[key], args.thresholds[0])
            print label_swap(arb_img_name, "")
        else:
            try:
                stats = run_thresholds(images,
                                       args.thresholds,
                                       label_swap(arb_img_name, "1-label"))
            except ValueError:
                print "failed at ", label_swap(arb_img_name, "")

            results_key = arb_img_name.split('-')[0]
            results_key = results_key[0:results_key.rfind('/')]
            results[arb_img_name.split('-')[0]] = stats
            print label_swap(arb_img_name, "")

    if results:
        import json
        with open("union-results.json", 'w') as f:
            json_out = json.dumps(results, sort_keys=True,
                                  indent=4, separators=(',', ': '))
            f.write(json_out)

    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
