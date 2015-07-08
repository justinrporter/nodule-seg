import sys
import argparse
import os
import datetime
import json

import sitkstrats
import SimpleITK as sitk  # pylint: disable=F0401
import numpy as np
import lungseg


def process_command_line(argv):
    '''Parse the command line and do a first-pass on processing them into a
    format appropriate for the rest of the script.'''

    parser = argparse.ArgumentParser(formatter_class=argparse.
                                     ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        "--dicomdirs", nargs="+",
        help="The dicom directories to operate on.")
    parser.add_argument(
        "--nseeds", type=int, default=10,
        help="The number of randomly placed seeds to produce.")
    parser.add_argument(
        '--media_root', default="media_root/",
        help="The directory to store temporary and intermediate media output")

    args = parser.parse_args(argv[1:])
    args.media_root = os.path.abspath(args.media_root)
    args.dicomdirs = [os.path.abspath(dicomdir) for dicomdir in args.dicomdirs]

    return args


def segmentation_too_big(segmentation, organ, threshold=0.05):

    seg_size = np.count_nonzero(sitk.GetArrayFromImage(segmentation))
    organ_size = np.count_nonzero(sitk.GetArrayFromImage(organ))

    return seg_size > threshold*organ_size



def convert_to_nii(dicom_in, nifti_dir):
    '''Convert the given dicom directory (dicom_in) into a nifti formatted
    image and place it in nifti_dir using an md5 hash of its contents.
    Returns the absolute path of the output file'''
    try:
        os.makedirs(nifti_dir)
    except OSError:
        # no need to do anything if the directory already exists.
        pass

    sha = dicom_hash(dicom_in)

    outname = os.path.join(nifti_dir, sha+".nii")
    lungseg.dicom_to_nii(dicom_in, outname)

    return sha


def set_label(fname, label, labsep='-'):
    '''Set the label (a string addition of labsep + label) for this filename.
    '''
    ext = fname[fname.rfind('.'):]
    fname = fname[:fname.rfind('.')]+labsep+label+ext
    return fname


def seed_dep_seg(img, seed, seg_info, seed_name):
    '''Run the seed-dependent segmentation for a particular image.'''
    (seed_dep_img, info) = sitkstrats.confidence_connected(img,
                                                           {'seed': seed})
    seg_info['segmentation'] = info
    seg_info['segmentation']['size'] = np.count_nonzero(
        sitk.GetArrayFromImage(seed_dep_img))

    return seed_dep_img


def run_img(sha, args):  # pylint: disable=C0111
    '''Run the entire protocol on a particular image starting with sha hash'''
    img_info = {}

    input_img = sitkstrats.read(os.path.join(args.media_root,
                                             'init', sha+".nii"))

    lung_img = lungseg.lungseg(input_img)

    sitkstrats.write(lung_img,
                     os.path.join(os.path.join(args.media_root, 'lungseg'),
                                  sha+'.nii'))
    seeds = lungseg.get_seeds(lung_img, args.nseeds)

    seed_list = [(171, 252, 96)]
    seed_list.extend(seeds['medpy_indexed'])

    (seed_indep_img, info) = sitkstrats.curvature_flow(input_img)
    img_info['seed-independant'] = info

    sitkstrats.write(seed_indep_img,
                     os.path.join(args.media_root, info['algorithm'],
                                  sha+".nii"))

    img_info['segmentations'] = {}

    for seed in seed_list:
        seed_name = "-".join([str(k) for k in seed])

        seg_info = img_info['segmentations'].setdefault(
            seed_name, {"seed-strategy": "random"})

        seed_dep_img = seed_dep_seg(
            seed_indep_img, seed, seg_info, seed_name)

        out_f = os.path.join(args.media_root, info['algorithm'],
                             set_label(sha+".nii", seed_name))
        sitkstrats.write(seed_dep_img, out_f)
        seg_info['file'] = out_f

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

    for dicomdir in args.dicomdirs:
        nii_dir = os.path.join(args.media_root, 'init')
        sha = convert_to_nii(os.path.abspath(dicomdir), nii_dir)
        run_info[sha] = run_img(sha, args)
        run_info[sha]['file'] = dicomdir

    with open("masterseg-run.json", 'w') as f:
        json_out = json.dumps(run_info, sort_keys=True,
                              indent=4, separators=(',', ': '),
                              cls=DateTimeEncoder)
        f.write(json_out)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
