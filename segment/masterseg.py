import sys
import argparse
import os
import datetime
import json

import sitkstrats
import SimpleITK as sitk  # pylint: disable=F0401
import numpy as np
import lungseg

import dicom2nifti


def process_command_line(argv):
    '''Parse the command line and do a first-pass on processing them into a
    format appropriate for the rest of the script.'''

    parser = argparse.ArgumentParser(formatter_class=argparse.
                                     ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        "images", nargs="+",
        help="The dicom directories to operate on.")
    parser.add_argument(
        "--nseeds", type=int, default=10,
        help="The number of randomly placed seeds to produce.")
    parser.add_argument(
        '--media_root', default="media_root/",
        help="The directory to store temporary and intermediate media output")

    args = parser.parse_args(argv[1:])
    args.media_root = os.path.abspath(args.media_root)
    args.images = [os.path.abspath(image) for image in args.images]

    return args


def segmentation_too_big(segmentation, organ, threshold=0.05):

    seg_size = np.count_nonzero(sitk.GetArrayFromImage(segmentation))
    organ_size = np.count_nonzero(sitk.GetArrayFromImage(organ))

    return seg_size > threshold*organ_size


def set_label(fname, label, labsep='-'):
    '''Set the label (a string addition of labsep + label) for this filename.
    '''
    ext = fname[fname.rfind('.'):]
    fname = fname[:fname.rfind('.')]+labsep+label+ext
    return fname


def seed_dep_seg(img, seed):
    '''Run the seed-dependent segmentation for a particular image.'''

    (seed_dep_img, info) = sitkstrats.confidence_connected(img,
                                                           {'seed': seed})
    info['size'] = np.count_nonzero(sitk.GetArrayFromImage(seed_dep_img))

    return (seed_dep_img, info)


def mediadir_log((img, opts), mediadir, sha):

    label = opts['algorithm']
    out_fname = os.path.join(mediadir, label, sha+'.nii')

    sitkstrats.write(img, out_fname)

    opts['file'] = out_fname

    return (img, opts)


def conf_connect_strat(img, sha, seeds, root_dir):
    info = {}

    (seed_indep_img, indep_info) = mediadir_log(sitkstrats.curvature_flow(img),
                                                root_dir, sha)

    for seed in seeds:
        seed_name = "-".join([str(k) for k in seed])
        dep_root_dir = os.path.dirname(indep_info['file'])

        (seed_img, seed_info) = seed_dep_seg(seed_indep_img, seed)
        (seed_img, seed_info) = mediadir_log((seed_img, seed_info),
                                             dep_root_dir, sha)

        info[seed_name] = {'seed-independent': indep_info,
                           'seed-dependent': seed_info,
                           'seed': seed}

    return info


def run_img(img, sha, args, root_dir):  # pylint: disable=C0111
    '''Run the entire protocol on a particular image starting with sha hash'''
    img_info = {}

    lung_img, lung_info = mediadir_log(sitkstrats.segment_lung(img),
                                       root_dir, sha)
    img_info['lungseg'] = lung_info

    # seeds = lungseg.get_seeds(lung_img, args.nseeds)['medpy_indexed']

    seeds = [(171, 252, 96)]

    img_info['conf_connect'] = conf_connect_strat(img, sha, seeds,
                                                  root_dir)

    return img_info


class DateTimeEncoder(json.JSONEncoder):  # pylint: disable=C0111

    def default(self, obj):  # pylint: disable=E0202
        if isinstance(obj, datetime.datetime):
            return str(obj)
        elif isinstance(obj, datetime.timedelta):
            return str(obj)

        return json.JSONEncoder.default(self, obj)


def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's sislent and just exposes methods.'''
    args = process_command_line(argv)

    run_info = {}

    for img in args.images:
        basename = os.path.basename(img)
        sha = basename[:basename.rfind('.')]

        run_info[sha] = run_img(sitkstrats.read(img), sha, args,
                                args.media_root)

    with open("masterseg-run.json", 'w') as f:
        json_out = json.dumps(run_info, sort_keys=True,
                              indent=4, separators=(',', ': '),
                              cls=DateTimeEncoder)
        f.write(json_out)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
